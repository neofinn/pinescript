"""Does this setup pay? Three questions, in the order they can kill it.

The arrangement being modelled: exchange-grade feed and order access rented
from a member on a FLAT MONTHLY FEE, zero brokerage. That structure changes the
answer to "should we trade more, smaller" from no to yes, and it is worth being
precise about why.

  net = lot x SUM over trades of ( edge_i - c x premium_i )  -  monthly_fee

where c is the statutory round-trip fraction (0.2383% on NSE). There is no
fixed per-ORDER term at all. So:

  * Trade count multiplies whatever the average per-trade margin is. It is
    neither a cost driver nor a benefit in itself -- doubling the rate doubles
    gross and doubles cost, and the sign of the result is unchanged.
  * A trade contributes if and only if its edge clears c x its own premium.
    That test is per-trade and independent of every other trade.
  * The monthly fee is sunk. It does not enter the per-trade decision at all.
    It only sets a minimum total volume, and at HFT rates that minimum is
    reached in seconds.

Under retail per-order pricing, "more trades, smaller returns" is fatal: the
flat fee per order does not shrink with the edge. Under a flat monthly fee it
is simply neutral, and the whole question collapses back onto whether each
small return clears its own proportional hurdle.

Which leaves latency as the thing that decides it -- and latency is measured
against a lag that this project has never measured. See lag_probe.py.
"""
from __future__ import annotations
from .costs import NSE_MEMBER, BSE_MEMBER, CostModel
from .instruments import NIFTY, BANKNIFTY, SENSEX


def trade_net(premium: float, capture_ticks: float, lot: int,
              cost: CostModel = NSE_MEMBER, tick: float = 0.05) -> dict:
    """One round trip: what it earns, what it pays, what is left."""
    gross = capture_ticks * tick * lot
    c = cost.round_trip_frac() * premium * lot
    return dict(gross=gross, cost=c, net=gross - c,
                breakeven_ticks=cost.breakeven_ticks(premium, tick))


def monthly_breakeven(monthly_fee: float, net_per_trip: float,
                      trading_days: int = 21) -> dict:
    """The fee is sunk, so it buys a volume requirement, not a per-trade one."""
    if net_per_trip <= 0.0:
        return dict(viable=False, trips_month=float("inf"),
                    trips_day=float("inf"), seconds_at_20rt=float("inf"))
    trips = monthly_fee / net_per_trip
    return dict(viable=True, trips_month=trips, trips_day=trips / trading_days,
                seconds_at_20rt=trips / trading_days / 20.0)


def latency_verdict(lag_ms: float, loop_ms: float) -> tuple[str, float]:
    """The lag is the entire budget. Your loop has to fit inside it.

    The trade is to reach the stale quote before its maker reprices. If the
    round trip from seeing the underlying move to the order resting at the
    exchange is longer than the lag, you arrive after the reprice every time --
    and the only fills you still get are the ones where you were wrong. That is
    not a reduced edge, it is an inverted one: adverse selection is what is
    left when the speed advantage goes.
    """
    if lag_ms <= 0.0:
        return "NO LAG TO CAPTURE", float("inf")
    used = loop_ms / lag_ms
    if used >= 1.0:
        return "INVERTED -- you are the slow side", used
    if used >= 0.6:
        return "marginal -- most of the edge is spent getting there", used
    if used >= 0.3:
        return "workable", used
    return "comfortable", used


def report(monthly_fee: float, lag_ms: float, loop_ms: float,
           premium: float = 150.0, capture_ticks: float = 10.0) -> str:
    out = []
    a = out.append
    a("VIABILITY  (flat monthly fee, zero brokerage, member-routed)")
    a("")
    a("1. THE PER-TRADE TEST -- the only test a single trade has to pass")
    a(f"   {'index':<11}{'lot':>5}{'premium':>9}{'capture':>9}"
      f"{'gross':>9}{'cost':>9}{'net':>9}{'b/e ticks':>11}")
    for spec, cost in ((NIFTY, NSE_MEMBER), (BANKNIFTY, NSE_MEMBER),
                       (SENSEX, BSE_MEMBER)):
        r = trade_net(premium, capture_ticks, spec.lot, cost)
        a(f"   {spec.symbol:<11}{spec.lot:>5}{premium:>9,.0f}"
          f"{capture_ticks:>9.1f}{r['gross']:>9,.2f}{r['cost']:>9,.2f}"
          f"{r['net']:>9,.2f}{r['breakeven_ticks']:>11.1f}")
    a("   No fixed per-order term appears. Trade count multiplies this row;")
    a("   it does not change its sign.")
    a("")

    a("2. THE MONTHLY FEE -- sunk, so it buys a volume floor, nothing else")
    r = trade_net(premium, capture_ticks, NIFTY.lot, NSE_MEMBER)
    for fee in (25_000.0, 50_000.0, 100_000.0, 250_000.0):
        b = monthly_breakeven(fee, r["net"])
        if not b["viable"]:
            a(f"   {fee:>10,.0f}/month   never: the trade itself loses money")
            continue
        a(f"   {fee:>10,.0f}/month -> {b['trips_month']:>9,.0f} round trips, "
          f"{b['trips_day']:>7,.0f}/day, {b['seconds_at_20rt']:>6,.0f}s "
          f"at 20 round trips/sec")
    a(f"   (at premium {premium:,.0f}, capture {capture_ticks:.0f} ticks, "
      f"net {r['net']:,.2f} per round trip)")
    a("   At HFT rates the fee is covered in the first minute of the month.")
    a("   It is not the constraint. Row 1 is.")
    a("")

    a("3. LATENCY -- the one that decides it")
    a(f"   lag being captured   {lag_ms:>8.1f} ms   <- MEASURE THIS "
      f"(hft.lag_probe)")
    a(f"   your loop            {loop_ms:>8.1f} ms   "
      f"feed wire + decode + compute + order wire + ack")
    v, used = latency_verdict(lag_ms, loop_ms)
    a(f"   budget consumed      {used*100:>8.0f} %   {v}")
    a("")
    a(f"   {'your loop':>12}  {'used':>5}  {'verdict':<45}")
    for lm in (0.2, 0.5, 1.0, 2.0, 5.0, 10.0, 25.0):
        vv, uu = latency_verdict(lag_ms, lm)
        a(f"   {str(round(lm,1)) + 'ms':>12}  {uu*100:>4.0f}%  {vv:<45}")
    a("")
    a("   Compute is not the problem: tick-to-signal measures 15.6us, which is")
    a("   0.0156ms. The wire is the problem, both ways.")
    return "\n".join(out)


def main() -> int:
    import argparse
    p = argparse.ArgumentParser(description="Is this setup viable?")
    p.add_argument("--monthly-fee", type=float, default=50_000.0)
    p.add_argument("--lag-ms", type=float, default=10.0,
                   help="MEASURE with hft.lag_probe; the default is an "
                        "assumption this project has never verified")
    p.add_argument("--loop-ms", type=float, default=2.0,
                   help="your feed-to-order round trip, measured end to end")
    p.add_argument("--premium", type=float, default=150.0)
    p.add_argument("--capture", type=float, default=10.0,
                   help="ticks captured per round trip")
    a = p.parse_args()
    print(report(a.monthly_fee, a.lag_ms, a.loop_ms, a.premium, a.capture))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
