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
from .pricing import bs_call, bs_put
from .signals import OptionSignal
from .adapters.sim import SimFeed
from .adapters.limitsim import LimitGateway
from .costs import NSE_MEMBER, BSE_MEMBER, NSE_RETAIL, FLAT_25, BY_VENUE

SPOTS = {"NIFTY": 23_200.0, "BANKNIFTY": 52_000.0, "SENSEX": 76_000.0}


class Cfg:
    """One point in the sweep."""
    __slots__ = ("edge_ticks", "spread_frac", "capture", "orders_per_sec",
                 "min_gap_us", "max_strikes", "each_side", "fee", "seconds",
                 "capital", "goal", "passive", "max_book_age_us", "hz", "seed",
                 "premium_band")

    def __init__(self, edge_ticks=1.0, spread_frac=0.55, capture=0.60,
                 orders_per_sec=25.0, min_gap_us=1_000, max_strikes=8,
                 each_side=6, fee=25.0, seconds=20.0, capital=500_000.0,
                 goal=0.0, passive=False, max_book_age_us=50_000, hz=200,
                 seed=0, premium_band=(0.0, 1e9)):
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
        self.premium_band = premium_band

    def clone(self, **kw) -> "Cfg":
        d = {k: getattr(self, k) for k in Cfg.__slots__}
        d.update(kw)
        return Cfg(**d)


# ── the floor ──────────────────────────────────────────────────────────────
def print_breakeven(fee: float = 0.0, capture: float = 0.60) -> None:
    """The floor, for an exchange-member seat with zero brokerage.

    With brokerage gone the cost is almost entirely proportional to premium, so
    the break-even is a percentage, identical across indices, and lot size
    drops out of it completely. What decides the hurdle is how expensive the
    option is -- which makes it a choice, not a constant.
    """
    m, b = NSE_MEMBER, BSE_MEMBER
    print("BREAK-EVEN FLOOR  (statutory stack, zero brokerage, exchange member)")
    print(f"  NSE round trip {m.round_trip_frac()*100:.4f}% of premium   "
          f"BSE {b.round_trip_frac()*100:.4f}%")
    print("  Lot size does NOT appear. A flat per-lot fee made SENSEX worst")
    print("  because its lot is smallest; a proportional one makes the")
    print("  EXPENSIVE option worst, whatever the lot.")
    print()
    print(f"  {'premium':>9}{'Rs/unit':>10}{'break-even ticks':>18}"
          f"{'entry edge ticks':>18}   {'typical of':<28}")
    notes = {10: "far OTM weekly", 50: "OTM", 100: "NIFTY near-ATM",
             150: "NIFTY ATM weekly", 250: "", 400: "BANKNIFTY ATM",
             500: "SENSEX ATM", 20: "deep OTM"}
    for pr in (10, 20, 50, 100, 150, 250, 400, 500):
        t = m.breakeven_ticks(pr)
        print(f"  {pr:>9,}{m.round_trip_frac()*pr:>10.3f}{t:>18.2f}"
              f"{t/capture:>18.2f}   {notes.get(pr,''):<28}")
    print()
    print("  Where it goes, one NIFTY lot (65) at premium 150:")
    tot = 0.0
    for n, v, sh in m.breakdown(150.0, 65):
        if v > 0.001:
            print(f"    {n:<26}{v:>9.2f}{sh*100:>8.1f}%")
        tot += v
    print(f"    {'TOTAL round trip':<26}{tot:>9.2f}")
    print("  STT alone is 63% of it and is not negotiable at any seat. Zero")
    print("  brokerage removed the flat part; the part that scales with size")
    print("  is untouched.")
    print()


def print_rate_reality(target_ops: float, fee: float,
                       signal_per_contract_per_s: float) -> None:
    """Member-seat version. The retail broker quota no longer applies.

    Kite Connect's 10/sec, 400/min and 5,000/day were the binding constraint on
    a customer API and they are gone at member level. What replaces them is not
    a published number: NSE configures a message rate per session per member,
    with colocation LAN sessions allowed the configured rate plus 10%. That
    figure comes from your own connectivity agreement, so it is an input here
    rather than something this module can assert.
    """
    m = NSE_MEMBER
    print("RATE CEILING  (exchange-member seat)")
    print("  Retail broker caps (10/s, 400/min, 5,000/day) no longer apply.")
    print("  NSE sets a message rate PER SESSION PER MEMBER; colocation LAN")
    print("  sessions get the configured rate +10%. That number is in your")
    print("  connectivity agreement -- this lab cannot look it up for you.")
    print()
    print("  Still live at member level:")
    print("    * order-to-trade ratio penalties fall on the MEMBER. SEBI's")
    print("      2026-02-04 revision exempts option orders within +/-40% of")
    print("      LTP or +/-Rs20, whichever is higher, so at-the-touch orders")
    print("      are outside the framework. A passive book that cancels most")
    print("      of what it quotes is the case to check, not this one.")
    print("    * every algo needs its exchange-approved unique identifier.")
    print()
    print(f"  What {int(target_ops)}/s costs per second at a 150 premium, "
          f"one NIFTY lot per order:")
    rt = m.round_trip_frac() * 150.0 * 65
    print(f"    cost per round trip   {rt:>10,.2f}")
    print(f"    at {int(target_ops/2)} round trips/sec "
          f"{rt*target_ops/2:>13,.0f} /sec   "
          f"{rt*target_ops/2*60:>12,.0f} /min")
    print(f"    gross needed to break even: "
          f"{rt*target_ops/2:,.0f}/sec")
    print()
    print("  Contracts needed to SUPPLY that rate, measured on this driver:")
    print("    30 contracts -> 22 orders/s    126 -> 60/s")
    print("    78 contracts -> 43 orders/s    246 -> 140/s")
    print(f"    roughly {signal_per_contract_per_s:.2f} orders/sec per contract, "
          f"near enough linear.")
    n = target_ops / signal_per_contract_per_s if signal_per_contract_per_s else 0
    print(f"    -> {int(target_ops)}/s needs about {n:,.0f} contracts: "
          f"{n/3:,.0f} per index,")
    print(f"       ~{n/3/2:,.0f} strikes each counting calls and puts. "
          f"That is roughly")
    print("       what the default each_side=6 already watches.")
    print()


# ── build ──────────────────────────────────────────────────────────────────
def make_leg(spec, base_token, t_years, iv, cfg):
    spot = SPOTS[spec.symbol]
    atm = round(spot / spec.strike_step) * spec.strike_step
    contracts, sigs = [], []
    tok = base_token + 1
    lo, hi = cfg.premium_band
    for i in range(-cfg.each_side, cfg.each_side + 1):
        k = atm + i * spec.strike_step
        for is_call in (True, False):
            # Under a proportional cost the hurdle is a fixed % of premium, so
            # WHICH contracts you watch is a cost decision, not just a breadth
            # one. Band by premium rather than by strike offset: a 50-point
            # NIFTY step and a 100-point SENSEX step are not comparable, but
            # "options worth 40 to 120 rupees" is.
            prem = (bs_call(spot, k, t_years, iv) if is_call
                    else bs_put(spot, k, t_years, iv))
            if not (lo <= prem <= hi):
                tok += 1
                continue
            contracts.append(dict(token=tok, strike=k, is_call=is_call))
            sigs.append(OptionSignal(tok, k, is_call, iv, spec.lot, spec.tick,
                                     min_edge_ticks=cfg.edge_ticks,
                                     spread_frac=cfg.spread_frac,
                                     max_book_age_us=cfg.max_book_age_us))
            tok += 1
    if not contracts:                     # band matched nothing on this index
        contracts.append(dict(token=tok, strike=atm, is_call=True))
        sigs.append(OptionSignal(tok, atm, True, iv, spec.lot, spec.tick,
                                 min_edge_ticks=1e9))
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
    # fee_per_lot=0: cost is charged in MultiEngine._close off both legs
    # actual fill prices, because it is a fraction of premium, not flat.
    gws = {s.symbol: LimitGateway(s.tick, store, fee_per_lot=0.0,
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
    fees = eng.costs
    fills = sum(g.passive_fills + g.marketable_fills for g in gws.values())
    trades = sum(eng.trades_by_symbol.values())
    rej = risk.reject_counts
    return dict(
        edge_ticks=cfg.edge_ticks, spread_frac=cfg.spread_frac,
        ops_target=cfg.orders_per_sec, min_gap_us=cfg.min_gap_us,
        max_strikes=cfg.max_strikes, each_side=cfg.each_side,
        contracts=sum(len(l.signals) for l in legs), fee=cfg.fee,
        elapsed=elapsed, ticks=eng._ticks,
        orders=risk.orders_sent, fills=fills, trades=trades,
        ops=risk.orders_sent / elapsed if elapsed else 0.0,
        tps=trades / elapsed if elapsed else 0.0,
        gross=eng.gross, fees=fees, net=eng.gross - fees,
        gross_per_fill=eng.gross / fills if fills else 0.0,
        fee_share=fees / eng.gross if eng.gross > 0 else float("inf"),
        avg_premium=eng.premium_sum / eng.premium_n if eng.premium_n else 0.0,
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
              "net", "gross_per_fill", "avg_premium"):
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
       f"{'gross':>10} {'costs':>9} {'NET':>10} {'sd':>8} {'w':>4} "
       f"{'prem':>6} {'g/trade':>8} {'cost%':>6}")


def row(r: dict) -> str:
    fs = "inf" if r["fee_share"] == float("inf") else f"{r['fee_share']*100:.0f}"
    return (f"{r['spread_frac']:>5.2f} {r['ops_target']:>6.0f} "
            f"{r['min_gap_us']:>7} {r['max_strikes']:>5} {r['contracts']:>4} | "
            f"{r['ops']:>6.1f} {r['tps']:>6.1f} {r['orders']:>7.0f} "
            f"{r['fills']:>6.0f} | {r['gross']:>+10,.0f} {r['fees']:>9,.0f} "
            f"{r['net']:>+10,.0f} {r.get('net_sd',0):>8,.0f} "
            f"{r.get('wins',0):>2}/{r.get('n',1):<1} "
            f"{r.get('avg_premium',0):>6.0f} "
            f"{r['gross']/r['trades'] if r['trades'] else 0:>8,.0f} {fs:>6}")


def sweep(args) -> int:
    n = args.repeats
    print_breakeven(args.fee, args.capture)
    print_rate_reality(args.target_ops, args.fee, args.supply_per_contract)
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

    print("SWEEP D -- which PREMIUM band pays, now that cost scales with it.")
    print("  Break-even ticks = 0.2383% x premium / tick. A 500-rupee option")
    print("  must move 23.8 ticks to cover a round trip; a 50-rupee one, 2.4.")
    print("  The counter-force is that cheap options have proportionally the")
    print("  widest spreads, so this is an optimum, not a slope.")
    print(HDR)
    for lo, hi in ((0, 25), (25, 60), (60, 120), (120, 250), (250, 1e9),
                   (0, 1e9)):
        r = repeat(base.clone(spread_frac=0.55, orders_per_sec=1000.0,
                              min_gap_us=200, max_strikes=60, each_side=20,
                              premium_band=(lo, hi)), n)
        lbl = f"{lo:.0f}-{'inf' if hi > 1e8 else f'{hi:.0f}'}"
        print(f"{lbl:>10}  " + row(r)[10:], flush=True)
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
    p.add_argument("--target-ops", type=float, default=40.0)
    p.add_argument("--supply-per-contract", type=float, default=0.55,
                   help="orders/sec per contract watched, measured on this "
                        "driver: 30 contracts -> 22/s, 78 -> 43/s, 246 -> 140/s")
    return sweep(p.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
