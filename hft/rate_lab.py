"""Throughput lab: what a target order rate costs, measured on a clock we own.

Run it with HFT_VIRTUAL_CLOCK=1. Without that the driver does not control time,
the token bucket and the staleness guards refill against scheduler jitter, and
the same configuration with the same seeds returns a different answer every
time -- measured here at a 4.7x spread in net, which is larger than any
parameter effect this sweep is trying to find.

THE FLOOR, which no amount of speed moves:

    breakeven_edge_per_unit = round_trip_fee / lot_size

Every round trip pays two fixed per-lot fees. That cost does not shrink when
the edge does, so the capture a trade must produce to be worth sending is the
same number whether you send one order a minute or forty a second. Raising the
rate does not lower the floor; it only means paying it more often.

The counter-intuitive part is which contract is worst. SENSEX has the SMALLEST
lot, so its fixed fee is spread over the fewest units, so it needs the MOST
ticks of edge per trade -- the opposite of the intuition that a small lot is a
cheap lot.

What the sweeps add to the arithmetic is two things it cannot settle: where the
throttle actually binds (a rate target is meaningless if signal supply, not the
rate limiter, is holding it down, and the fix for each is different), and what
lowering the entry bar does to gross-per-fill, since a looser bar admits more
trades AND worse ones.
"""
from __future__ import annotations
import argparse
import os
import statistics

if os.environ.get("HFT_VIRTUAL_CLOCK") != "1":     # must precede hft imports
    os.environ["HFT_VIRTUAL_CLOCK"] = "1"

from . import clock
from .clock import now_ns
from .instruments import NIFTY, BANKNIFTY, SENSEX
from .multi import MultiEngine, IndexLeg
from .orders import OrderStore, OrdType, OrdState, price_for
from .risk import RiskGate, Reject
from .session import Phase
from .signals import OptionSignal
from .adapters.sim import SimFeed
from .adapters.limitsim import LimitGateway

SPOTS = {"NIFTY": 23_200.0, "BANKNIFTY": 52_000.0, "SENSEX": 76_000.0}


class Cfg:
    """One point in the sweep."""
    __slots__ = ("edge_ticks", "spread_frac", "capture", "orders_per_sec",
                 "min_gap_us", "max_strikes", "each_side", "fee", "seconds",
                 "capital", "goal", "passive", "max_book_age_us", "hz", "seed")

    def __init__(self, edge_ticks=1.0, spread_frac=0.55, capture=0.60,
                 orders_per_sec=25.0, min_gap_us=1_000, max_strikes=8,
                 each_side=6, fee=25.0, seconds=20.0, capital=500_000.0,
                 goal=0.0, passive=False, max_book_age_us=50_000, hz=200,
                 seed=0):
        self.edge_ticks = edge_ticks
        self.spread_frac = spread_frac
        self.capture = capture
        self.orders_per_sec = orders_per_sec
        self.min_gap_us = min_gap_us
        self.max_strikes = max_strikes
        self.each_side = each_side
        self.fee = fee
        self.seconds = seconds
        self.capital = capital
        self.goal = goal
        self.passive = passive
        self.max_book_age_us = max_book_age_us
        self.hz = hz
        self.seed = seed

    def clone(self, **kw) -> "Cfg":
        d = {k: getattr(self, k) for k in Cfg.__slots__}
        d.update(kw)
        return Cfg(**d)


# ── the floor ──────────────────────────────────────────────────────────────
def breakeven_table(fee_per_lot: float, capture: float, tick: float = 0.05):
    rows = []
    rt = fee_per_lot * 2.0
    for s in (NIFTY, BANKNIFTY, SENSEX):
        per_unit = rt / s.lot                  # rupees of price move needed
        ticks_captured = per_unit / tick
        # capture_frac of the ENTRY edge is what gets taken, so the entry edge
        # has to exceed the capture by that factor
        entry_ticks = ticks_captured / capture if capture > 0 else float("inf")
        rows.append((s.symbol, s.lot, rt, per_unit, ticks_captured, entry_ticks))
    return rows


def print_breakeven(fee: float, capture: float) -> None:
    print("BREAK-EVEN FLOOR  (arithmetic; no simulator involved)")
    print(f"  round-trip fee {fee*2:,.0f} per lot ({fee:,.0f} x 2 fills)   "
          f"capture_frac {capture}")
    print(f"  {'index':<11}{'lot':>5}{'RT fee':>9}{'Rs/unit':>10}"
          f"{'ticks to capture':>18}{'entry edge ticks':>18}")
    for sym, lot, rt, per_unit, cap_t, ent_t in breakeven_table(fee, capture):
        print(f"  {sym:<11}{lot:>5}{rt:>9,.0f}{per_unit:>10.3f}"
              f"{cap_t:>18.1f}{ent_t:>18.1f}")
    print("  A trade capturing fewer ticks than the last column loses money at")
    print("  ANY order rate. Sending more of them loses money faster.")
    print()


# ── build ──────────────────────────────────────────────────────────────────
def make_leg(spec, base_token, t_years, iv, cfg):
    spot = SPOTS[spec.symbol]
    atm = round(spot / spec.strike_step) * spec.strike_step
    contracts, sigs = [], []
    tok = base_token + 1
    for i in range(-cfg.each_side, cfg.each_side + 1):
        k = atm + i * spec.strike_step
        for is_call in (True, False):
            contracts.append(dict(token=tok, strike=k, is_call=is_call))
            sigs.append(OptionSignal(tok, k, is_call, iv, spec.lot, spec.tick,
                                     min_edge_ticks=cfg.edge_ticks,
                                     spread_frac=cfg.spread_frac,
                                     max_book_age_us=cfg.max_book_age_us))
            tok += 1
    leg = IndexLeg(spec, base_token, sigs, t_years, 1, cfg.max_strikes)
    leg.exits.capture_frac = cfg.capture
    feed = SimFeed(base_token, contracts, spot, t_years, iv, tick=spec.tick,
                   lag_ms=spec.expected_lag_ms, hz=cfg.hz,
                   seed=base_token + cfg.seed)
    return leg, feed


def run_det(cfg: Cfg) -> dict:
    """Deterministic single-threaded driver. The clock only moves when we say."""
    assert clock.VIRTUAL is not None, "set HFT_VIRTUAL_CLOCK=1 before importing"
    clock.VIRTUAL.reset()

    specs = [NIFTY, BANKNIFTY, SENSEX]
    T, IV = 3.0 / 365.0, 0.14
    otype = OrdType.PASSIVE if cfg.passive else OrdType.MARKETABLE

    legs, feeds = [], []
    base = 100_000
    for s in specs:
        leg, feed = make_leg(s, base, T, IV, cfg)
        legs.append(leg); feeds.append(feed); base += 100_000

    risk = RiskGate(max_pos_lots=1, max_net_delta=1e9,
                    max_order_value=cfg.capital * 0.10, max_orders=10_000_000,
                    max_daily_loss=cfg.capital * 0.02,
                    orders_per_sec=cfg.orders_per_sec,
                    min_gap_us=cfg.min_gap_us, profit_goal=cfg.goal)
    eng = MultiEngine(legs, risk)
    store = OrderStore()
    gws = {s.symbol: LimitGateway(s.tick, store, fee_per_lot=cfg.fee,
                                  seed=i + 1 + cfg.seed)
           for i, s in enumerate(specs)}
    for f in feeds:
        f.set_handler(eng.on_tick)

    eng.enter(); eng.set_phase(Phase.ACTIVE)
    t0 = now_ns()
    dt_ns = int(1e9 / cfg.hz)
    steps = int(cfg.seconds * cfg.hz)

    def pump() -> None:
        for (sym, tok, side, lots, px, kind) in eng.drain():
            leg = eng.legs[sym]
            bk = leg.books.get(tok)
            sig = leg.signals.get(tok)
            if bk is None or not bk.fresh:
                continue
            theo = sig.last_theo if sig else bk.mid
            lim = price_for(otype, side, bk.bid, bk.ask, theo, leg.spec.tick, 1.0)
            o = store.new(tok, sym, side, lots, lim, otype)
            gws[sym].submit(o, bk.bid, bk.ask)
            if o.state is OrdState.FILLED:
                eng.on_fill(sym, tok, side, o.filled, o.avg_px)
            elif not o.live:
                eng.on_no_fill(sym, tok)
        if otype is OrdType.PASSIVE:
            for o in store.all_live():
                leg = eng.legs[o.symbol]
                bk = leg.books.get(o.token)
                if bk is None or not bk.fresh:
                    continue
                before = o.filled
                gws[o.symbol].on_book(o, bk.bid, bk.ask, traded_lots=2,
                                      micro_delta=bk.micro_delta)
                if o.filled > before:
                    eng.on_fill(o.symbol, o.token, o.side,
                                o.filled - before, o.avg_px)
                if o.live and o.age_ns() > 250_000_000:
                    gws[o.symbol].cancel(o)
                    eng.on_no_fill(o.symbol, o.token)
        store.sweep()

    for _ in range(steps):
        clock.VIRTUAL.advance(dt_ns)
        for f in feeds:
            f.step()
        pump()

    eng.set_phase(Phase.FLATTEN)
    for _ in range(20):                        # let open positions exit
        clock.VIRTUAL.advance(dt_ns)
        for f in feeds:
            f.step()
        pump()
    for o in store.all_live():
        gws[o.symbol].cancel(o)
    eng.leave()

    elapsed = (now_ns() - t0) / 1e9            # virtual seconds
    fees = sum(g.fees_paid for g in gws.values())
    fills = sum(g.passive_fills + g.marketable_fills for g in gws.values())
    trades = sum(eng.trades_by_symbol.values())
    rej = risk.reject_counts
    return dict(
        edge_ticks=cfg.edge_ticks, spread_frac=cfg.spread_frac,
        ops_target=cfg.orders_per_sec, min_gap_us=cfg.min_gap_us,
        max_strikes=cfg.max_strikes, each_side=cfg.each_side,
        contracts=cfg.each_side * 2 * 2 * 3 + 3, fee=cfg.fee,
        elapsed=elapsed, ticks=eng._ticks,
        orders=risk.orders_sent, fills=fills, trades=trades,
        ops=risk.orders_sent / elapsed if elapsed else 0.0,
        tps=trades / elapsed if elapsed else 0.0,
        gross=risk.realised, fees=fees, net=risk.realised - fees,
        gross_per_fill=risk.realised / fills if fills else 0.0,
        fee_share=fees / risk.realised if risk.realised > 0 else float("inf"),
        rate_limit=rej[Reject.RATE_LIMIT], pos_limit=rej[Reject.POSITION_LIMIT],
        killed=risk.killed,
        per_symbol={k: (eng.trades_by_symbol.get(k, 0),
                        eng.pnl_by_symbol.get(k, 0.0)) for k in eng.legs},
    )


def repeat(cfg: Cfg, n: int) -> dict:
    """Same config, n different market draws. One run tells you nothing."""
    runs = [run_det(cfg.clone(seed=i * 101)) for i in range(n)]
    out = dict(runs[0])
    for k in ("ops", "tps", "orders", "fills", "trades", "gross", "fees",
              "net", "gross_per_fill"):
        out[k] = statistics.mean(r[k] for r in runs)
    out["net_sd"] = statistics.pstdev([r["net"] for r in runs]) if n > 1 else 0.0
    out["net_lo"] = min(r["net"] for r in runs)
    out["net_hi"] = max(r["net"] for r in runs)
    out["n"] = n
    out["wins"] = sum(1 for r in runs if r["net"] > 0)
    return out


# ── reporting ──────────────────────────────────────────────────────────────
HDR = (f"{'sprd':>5} {'tgt/s':>6} {'gap_us':>7} {'strk':>5} {'ctr':>4} | "
       f"{'ord/s':>6} {'trd/s':>6} {'orders':>7} {'fills':>6} | "
       f"{'gross':>10} {'fees':>9} {'NET':>10} {'sd':>8} {'w':>4} "
       f"{'g/fill':>7} {'fee%':>5}")


def row(r: dict) -> str:
    fs = "inf" if r["fee_share"] == float("inf") else f"{r['fee_share']*100:.0f}"
    return (f"{r['spread_frac']:>5.2f} {r['ops_target']:>6.0f} "
            f"{r['min_gap_us']:>7} {r['max_strikes']:>5} {r['contracts']:>4} | "
            f"{r['ops']:>6.1f} {r['tps']:>6.1f} {r['orders']:>7.0f} "
            f"{r['fills']:>6.0f} | {r['gross']:>+10,.0f} {r['fees']:>9,.0f} "
            f"{r['net']:>+10,.0f} {r.get('net_sd',0):>8,.0f} "
            f"{r.get('wins',0):>2}/{r.get('n',1):<1} "
            f"{r['gross_per_fill']:>7,.0f} {fs:>5}")


def sweep(args) -> int:
    n = args.repeats
    print_breakeven(args.fee, args.capture)
    print(f"Every row is the mean of {n} independent market draws. "
          f"'sd' is the spread across them,")
    print(f"'w' how many of the {n} were net positive. A difference smaller "
          f"than sd is not a difference.")
    print(f"Virtual clock: the same seed gives the same answer, every time.\n")

    base = Cfg(seconds=args.seconds, fee=args.fee, capture=args.capture,
               passive=args.passive, hz=args.hz)

    print("SWEEP A -- entry threshold.  Does admitting worse trades pay?")
    print("  (rate cap held wide open so the THRESHOLD is the only variable)")
    print(HDR)
    a = []
    for sf in (0.80, 0.55, 0.40, 0.30, 0.20, 0.10, 0.05):
        r = repeat(base.clone(spread_frac=sf, orders_per_sec=1000.0,
                              min_gap_us=200, max_strikes=26, each_side=6), n)
        a.append(r); print(row(r), flush=True)
    print()

    print("SWEEP B -- the rate cap itself, threshold held at the default 0.55.")
    print("  Does buying more orders per second buy more money?")
    print(HDR)
    for ops in (5, 10, 20, 40, 80, 160, 1000):
        r = repeat(base.clone(spread_frac=0.55, orders_per_sec=float(ops),
                              min_gap_us=200, max_strikes=26, each_side=6), n)
        print(row(r), flush=True)
    print()

    print("SWEEP C -- at a 40/s target, what is actually holding the rate down?")
    print(HDR)
    for gap, strikes, side in ((1_000, 8, 6), (200, 8, 6), (200, 26, 6),
                               (200, 26, 12), (200, 50, 20), (50, 50, 20)):
        r = repeat(base.clone(spread_frac=0.55, orders_per_sec=40.0,
                              min_gap_us=gap, max_strikes=strikes,
                              each_side=side), n)
        print(row(r), flush=True)
        print(f"      rejects: RATE_LIMIT={r['rate_limit']:,}  "
              f"POSITION_LIMIT={r['pos_limit']:,}", flush=True)
    print()

    print("SWEEP D -- the fee assumption, at the best rate found above.")
    print("  25/lot/fill is optimistic for retail. A flat Rs20 brokerage plus")
    print("  STT, exchange and GST on one NIFTY lot lands nearer 34.")
    print(HDR)
    for fee in (0.0, 10.0, 25.0, 34.0, 50.0):
        r = repeat(base.clone(spread_frac=0.55, orders_per_sec=1000.0,
                              min_gap_us=200, max_strikes=50, each_side=20,
                              fee=fee), n)
        print(row(r), flush=True)
    print()
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Order-rate vs edge crossover")
    p.add_argument("--seconds", type=float, default=15.0)
    p.add_argument("--repeats", type=int, default=5)
    p.add_argument("--hz", type=int, default=200)
    p.add_argument("--fee", type=float, default=25.0,
                   help="per-lot fee per FILL; a round trip is twice this")
    p.add_argument("--capture", type=float, default=0.60)
    p.add_argument("--passive", action="store_true")
    return sweep(p.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
