"""Three indices at once, on the simulator.

Each index gets its own simulated feed with its own lag, because they do not
reprice at the same speed -- a BANKNIFTY option quote trails further than a
NIFTY one, and SENSEX further still. Running them on one shared lag would hide
exactly the difference the per-index exit policy exists to handle.
"""
from __future__ import annotations
import argparse, asyncio
from .clock import now_ns
from .instruments import NIFTY, BANKNIFTY, SENSEX, capital_split
from .multi import MultiEngine, IndexLeg
from .risk import RiskGate
from .session import Phase
from .signals import OptionSignal
from .adapters.sim import SimFeed, SimGateway

SPOTS = {"NIFTY": 23_200.0, "BANKNIFTY": 52_000.0, "SENSEX": 76_000.0}


def make_leg(spec, base_token: int, t_years: float, iv: float,
             max_strikes: int, edge_ticks: float):
    spot = SPOTS[spec.symbol]
    atm = round(spot / spec.strike_step) * spec.strike_step
    contracts, sigs = [], []
    tok = base_token + 1
    for i in range(-spec.strikes_each_side, spec.strikes_each_side + 1):
        k = atm + i * spec.strike_step
        for is_call in (True, False):
            contracts.append(dict(token=tok, strike=k, is_call=is_call))
            sigs.append(OptionSignal(tok, k, is_call, iv, spec.lot, spec.tick,
                                     min_edge_ticks=edge_ticks))
            tok += 1
    leg = IndexLeg(spec, base_token, sigs, t_years, 1, max_strikes)
    feed = SimFeed(base_token, contracts, spot, t_years, iv, tick=spec.tick,
                   lag_ms=spec.expected_lag_ms, seed=base_token)
    return leg, feed


async def main_async(a) -> int:
    specs = [s for s in (NIFTY, BANKNIFTY, SENSEX)]
    split = capital_split(a.capital, specs, SPOTS)
    T, IV = 3.0 / 365.0, 0.14

    legs, feeds = [], []
    base = 100_000
    for s in specs:
        leg, feed = make_leg(s, base, T, IV, a.max_strikes, a.edge_ticks)
        legs.append(leg); feeds.append(feed)
        base += 100_000

    risk = RiskGate(max_pos_lots=1,                       # per contract
                    max_net_delta=a.max_delta,
                    max_order_value=a.capital * 0.10,
                    max_orders=a.max_orders,
                    max_daily_loss=a.capital * a.loss_pct / 100.0,
                    orders_per_sec=a.orders_per_sec,
                    min_gap_us=a.min_gap_us,
                    profit_goal=a.capital * a.goal_pct / 100.0)
    eng = MultiEngine(legs, risk)
    for f in feeds:
        f.set_handler(eng.on_tick)
    gws = [SimGateway(f, fill_prob=a.fill_prob) for f in feeds]

    print(f"{'='*72}")
    print(f"THREE INDICES  capital {a.capital:,.0f}   "
          f"goal +{risk.profit_goal:,.0f}   loss -{risk.max_daily_loss:,.0f}")
    print(f"{'='*72}")
    for s in specs:
        notional = s.lot * SPOTS[s.symbol]
        print(f"  {s.symbol:<11}{s.venue}  lot {s.lot:<4} step {s.strike_step:<6.0f} "
              f"lag {s.expected_lag_ms:>4.0f}ms  notional/lot {notional:>10,.0f}  "
              f"budget {split[s.symbol]:>9,.0f}")
    print(f"\n  one lot per strike, at most {a.max_strikes} strikes open per index")
    print(f"  per-contract gap {a.min_gap_us}us, broker cap {a.orders_per_sec}/s\n")

    eng.enter(); eng.set_phase(Phase.ACTIVE)

    async def drain():
        while True:
            for (sym, tok, side, lots, px, kind) in eng.drain():
                gw = gws[[s.symbol for s in specs].index(sym)]
                await gw.send(tok, side, lots, px)
            eng.maintenance()
            await asyncio.sleep(0.002)

    d = asyncio.create_task(drain())
    try:
        await asyncio.gather(*(f.run(a.seconds) for f in feeds))
    finally:
        await asyncio.sleep(0.05)
        eng.set_phase(Phase.FLATTEN)
        await asyncio.sleep(0.10)
        d.cancel()
        eng.leave()

    print(eng.stats())
    fills = sum(len(g.fills) for g in gws)
    rej = sum(g.rejected for g in gws)
    print(f"\n  venue fills={fills} pulled={rej}  realised={risk.realised:+,.0f}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="NIFTY + BANKNIFTY + SENSEX")
    p.add_argument("--capital", type=float, default=500_000.0)
    p.add_argument("--seconds", type=float, default=8.0)
    p.add_argument("--max-strikes", type=int, default=8)
    p.add_argument("--edge-ticks", type=float, default=2.0)
    p.add_argument("--fill-prob", type=float, default=0.70)
    p.add_argument("--orders-per-sec", type=float, default=25.0)
    p.add_argument("--min-gap-us", type=int, default=1_000)
    p.add_argument("--max-orders", type=int, default=2_000)
    p.add_argument("--max-delta", type=float, default=600.0)
    p.add_argument("--goal-pct", type=float, default=1.0)
    p.add_argument("--loss-pct", type=float, default=2.0)
    return asyncio.run(main_async(p.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
