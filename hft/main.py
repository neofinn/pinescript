"""Runner. Drives the window, the feed and the order drain.

The order drain is deliberately separate from the tick path. Awaiting a network
send inside the tick callback would add the broker's round trip to the latency
of every subsequent tick, so signals are queued in the hot path and shipped by
this loop.

Run the simulator first and read the latency histogram. If tick->signal is not
comfortably inside your quote-lag assumption, the strategy is not fast enough to
take the lag it is aiming at and no amount of tuning the edge threshold fixes it.
"""
from __future__ import annotations
import argparse, asyncio, sys
from datetime import datetime

from .clock import now_ns
from .engine import Engine
from .risk import RiskGate
from .session import SessionWindow, Phase, IST
from .signals import OptionSignal
from .adapters.sim import SimFeed, SimGateway


def build_chain(spot: float, n_strikes: int = 5, step: float = 50.0,
                base_token: int = 1000) -> list[dict]:
    atm = round(spot / step) * step
    out = []
    tok = base_token
    for i in range(-n_strikes, n_strikes + 1):
        k = atm + i * step
        for is_call in (True, False):
            out.append(dict(token=tok, strike=k, is_call=is_call))
            tok += 1
    return out


async def run_sim(seconds: float, lag_ms: float, fill_prob: float,
                  min_edge_ticks: float) -> int:
    SPOT, IV, T = 25_000.0, 0.14, 3.0 / 365.0
    LOT, TICK = 75, 0.05
    U = 1

    contracts = build_chain(SPOT)
    feed = SimFeed(U, contracts, SPOT, T, IV, tick=TICK, lag_ms=lag_ms)
    gw = SimGateway(feed, fill_prob=fill_prob)
    # 200 delta is under two NIFTY lots. Sized for the instrument, not a
    # round number: 75 per lot at ~0.5 delta is 37 delta a lot.
    risk = RiskGate(max_pos_lots=10, max_orders=400, orders_per_sec=8.0,
                    max_net_delta=750.0)
    sigs = [OptionSignal(c["token"], c["strike"], c["is_call"], IV, LOT, TICK,
                         min_edge_ticks=min_edge_ticks)
            for c in contracts]
    win = SessionWindow(warmup_s=0, active_s=int(seconds), flatten_s=1)
    eng = Engine(U, sigs, risk, gw, win, T)
    feed.set_handler(eng.on_tick)

    eng.enter_window()
    eng.set_phase(Phase.ACTIVE)

    async def drain():
        while True:
            for (tok, side, lots, px) in eng.drain():
                await gw.send(tok, side, lots, px)
            await asyncio.sleep(0.002)

    d = asyncio.create_task(drain())
    try:
        await feed.run(seconds)
    finally:
        await asyncio.sleep(0.05)
        d.cancel()
        eng.set_phase(Phase.FLATTEN)
        await gw.cancel_all()
        await gw.flatten()
        eng.leave_window()

    from .pricing import bs_call, bs_put
    cash = 0.0
    fees = 0.0
    net: dict[int, int] = {}
    for f in gw.fills:
        # buying pays cash, selling receives it
        cash -= f["side"] * f["px"] * f["lots"] * LOT
        fees += f["fee"]
        net[f["token"]] = net.get(f["token"], 0) + f["side"] * f["lots"]
    # Mark the residual out at final fair value. A strategy that ends the window
    # holding inventory has not made money, it has an open position, and scoring
    # it on realised cash alone flatters exactly the runs that went wrong.
    bytok = {c["token"]: c for c in contracts}
    resid = 0.0
    open_lots = 0
    for tok, q_ in net.items():
        if not q_:
            continue
        c = bytok[tok]
        fv = (bs_call(feed.spot, c["strike"], T, IV) if c["is_call"]
              else bs_put(feed.spot, c["strike"], T, IV))
        resid += q_ * fv * LOT
        open_lots += abs(q_)
    gross = cash + resid
    print(f"\n{'='*66}\nSIMULATION  lag={lag_ms}ms  fill_prob={fill_prob}  "
          f"edge>={min_edge_ticks} ticks")
    print(f"{'='*66}")
    print(eng.stats())
    print(f"  fills={len(gw.fills)} rejected_by_venue={gw.rejected}")
    print(f"  gross={gross:+,.0f}  fees={fees:,.0f}  NET={gross - fees:+,.0f}"
          f"  (residual {open_lots} lots marked at fair value)")
    return gross - fees


async def sweep(seconds: float) -> int:
    """Where does this become viable? Two axes decide it.

    Quote lag is the edge: no lag, no trade. Fill probability is adverse
    selection: the takes that fail are the ones the maker pulled because they
    saw the move coming, so they are disproportionately the ones you wanted.
    A simulator that fills everything makes any latency-arb strategy look
    profitable, which is why fill_prob is the number to be honest about.
    """
    print(f"\n{'='*66}\nVIABILITY SWEEP  ({seconds}s each)\n{'='*66}")
    print(f"  {'':<22}" + "".join(f"{f'fill {p:.0%}':>14}" for p in (1.0, 0.85, 0.7, 0.5)))
    for lag in (0.0, 5.0, 12.0, 25.0):
        row = f"  quote lag {lag:>5.0f}ms   "
        for fp in (1.0, 0.85, 0.7, 0.5):
            import io, contextlib
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                net = await run_sim(seconds, lag, fp, 2.0)
            row += f"{net:>+14,.0f}"
        print(row)
    print("\n  net rupees. lag 0 is the control: with no stale quote to take,")
    print("  a non-zero result would mean the edge calculation is wrong.")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Opening-window options HFT")
    p.add_argument("--sim", action="store_true", help="run the simulator")
    p.add_argument("--seconds", type=float, default=10.0)
    p.add_argument("--lag-ms", type=float, default=12.0,
                   help="how far option quotes trail fair value")
    p.add_argument("--fill-prob", type=float, default=0.70)
    p.add_argument("--edge-ticks", type=float, default=2.0)
    p.add_argument("--sweep", action="store_true", help="lag x fill-probability grid")
    a = p.parse_args()
    if a.sweep:
        return asyncio.run(sweep(a.seconds))
    if a.sim:
        asyncio.run(run_sim(a.seconds, a.lag_ms, a.fill_prob, a.edge_ticks))
        return 0
    print("live mode needs a Feed and Gateway implementation; see adapters/base.py",
          file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
