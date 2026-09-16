"""Three indices, limit orders only, with a stated profit goal.

Nothing sends a market order. Every order is either a marketable limit capped at
the touch, or a passive quote that rests. Passive orders are advanced against
each tick through the queue model rather than assumed filled.
"""
from __future__ import annotations
import argparse, asyncio
from .clock import now_ns
from .instruments import NIFTY, BANKNIFTY, SENSEX, capital_split
from .multi import MultiEngine, IndexLeg
from .orders import OrderStore, OrdType, OrdState, price_for
from .risk import RiskGate
from .session import Phase
from .signals import OptionSignal
from .adapters.sim import SimFeed
from .adapters.limitsim import LimitGateway

SPOTS = {"NIFTY": 23_200.0, "BANKNIFTY": 52_000.0, "SENSEX": 76_000.0}


def make_leg(spec, base_token, t_years, iv, max_strikes, edge_ticks):
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
    specs = [NIFTY, BANKNIFTY, SENSEX]
    split = capital_split(a.capital, specs, SPOTS)
    T, IV = 3.0 / 365.0, 0.14
    otype = OrdType.PASSIVE if a.passive else OrdType.MARKETABLE

    legs, feeds = [], []
    base = 100_000
    for s in specs:
        leg, feed = make_leg(s, base, T, IV, a.max_strikes, a.edge_ticks)
        legs.append(leg); feeds.append(feed); base += 100_000

    risk = RiskGate(max_pos_lots=1, max_net_delta=a.max_delta,
                    max_order_value=a.capital * 0.10, max_orders=a.max_orders,
                    max_daily_loss=a.capital * a.loss_pct / 100.0,
                    orders_per_sec=a.orders_per_sec, min_gap_us=a.min_gap_us,
                    profit_goal=a.goal)
    eng = MultiEngine(legs, risk)
    store = OrderStore()
    gws = {s.symbol: LimitGateway(s.tick, store, adverse_bias=a.adverse_bias,
                                  rebate_per_lot=a.rebate, seed=i + 1)
           for i, s in enumerate(specs)}
    for f in feeds:
        f.set_handler(eng.on_tick)

    print(f"{'='*74}")
    print(f"LIMIT ORDERS ONLY   {otype.name}   capital {a.capital:,.0f}")
    print(f"GOAL +{a.goal:,.0f}   LOSS -{risk.max_daily_loss:,.0f}")
    print(f"{'='*74}")
    for s in specs:
        print(f"  {s.symbol:<11}{s.venue}  lot {s.lot:<4} budget {split[s.symbol]:>9,.0f}")
    print()

    eng.enter(); eng.set_phase(Phase.ACTIVE)

    async def work():
        while True:
            for (sym, tok, side, lots, px, kind) in eng.drain():
                leg = eng.legs[sym]
                bk = leg.books.get(tok)
                sig = leg.signals.get(tok)
                if bk is None or not bk.fresh:
                    continue
                theo = sig.last_theo if sig else bk.mid
                lim = price_for(otype, side, bk.bid, bk.ask, theo,
                                leg.spec.tick, a.improve)
                o = store.new(tok, sym, side, lots, lim, otype)
                gws[sym].submit(o, bk.bid, bk.ask)
                if o.state is OrdState.FILLED:
                    eng.on_fill(sym, tok, side, o.filled, o.avg_px)
                elif not o.live:
                    eng.on_no_fill(sym, tok)
            # advance every resting order against its current book
            if otype is OrdType.PASSIVE:
                for o in store.all_live():
                    leg = eng.legs[o.symbol]
                    bk = leg.books.get(o.token)
                    if bk is None or not bk.fresh:
                        continue
                    before = o.filled
                    gws[o.symbol].on_book(o, bk.bid, bk.ask,
                                          traded_lots=2, micro_delta=bk.micro_delta)
                    if o.filled > before:
                        eng.on_fill(o.symbol, o.token, o.side,
                                    o.filled - before, o.avg_px)
                    # a quote that the market has walked away from is stale;
                    # leaving it out is how a maker accumulates the wrong side
                    if o.live and o.age_ns() > a.requote_ms * 1_000_000:
                        gws[o.symbol].cancel(o)
                        eng.on_no_fill(o.symbol, o.token)
            store.sweep()
            eng.maintenance()
            await asyncio.sleep(0.002)

    w = asyncio.create_task(work())
    try:
        await asyncio.gather(*(f.run(a.seconds) for f in feeds))
    finally:
        await asyncio.sleep(0.05)
        eng.set_phase(Phase.FLATTEN)
        await asyncio.sleep(0.10)
        for o in store.all_live():
            gws[o.symbol].cancel(o)
        w.cancel(); eng.leave()

    print(eng.stats())
    print()
    for s in specs:
        print(f"  {s.symbol:<11}{gws[s.symbol].summary()}")
    tot_fees = sum(g.fees_paid for g in gws.values())
    print(f"\n  realised {risk.realised:+,.0f}   fees {tot_fees:,.0f}   "
          f"NET {risk.realised - tot_fees:+,.0f}")
    print(f"  goal {a.goal:,.0f} -> {'REACHED' if risk.goal_hit else 'NOT reached'}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Limit-order-only, three indices")
    p.add_argument("--capital", type=float, default=500_000.0)
    p.add_argument("--goal", type=float, default=50_000.0)
    p.add_argument("--loss-pct", type=float, default=2.0)
    p.add_argument("--seconds", type=float, default=45.0)
    p.add_argument("--passive", action="store_true",
                   help="rest and earn the spread instead of crossing it")
    p.add_argument("--improve", type=float, default=1.0,
                   help="ticks to improve a passive quote by")
    p.add_argument("--requote-ms", type=float, default=250.0)
    p.add_argument("--adverse-bias", type=float, default=0.65)
    p.add_argument("--rebate", type=float, default=0.0)
    p.add_argument("--max-strikes", type=int, default=8)
    p.add_argument("--edge-ticks", type=float, default=2.0)
    p.add_argument("--orders-per-sec", type=float, default=25.0)
    p.add_argument("--min-gap-us", type=int, default=1_000)
    p.add_argument("--max-orders", type=int, default=5_000)
    p.add_argument("--max-delta", type=float, default=600.0)
    return asyncio.run(main_async(p.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
