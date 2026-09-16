"""Directional micro-scalp: buy the move, take 1-2 index points, limit only.

This is a different trade from the one the rest of this package was built for,
and the difference is not a parameter. Lag capture does not need a forecast --
the quote is wrong against a value you can compute, and you take it. This needs
a forecast: you are buying direction and waiting for the index to go your way.

That changes what has to be true. An index oscillating 5 points inside a candle
is VOLATILITY, not edge. If you buy direction at random on a symmetric
oscillation you win half the time, and half of a symmetric payoff minus costs
is a loss. So the only question that matters here is the hit rate the costs
demand, and whether any signal clears it.

The arithmetic runs in index points, because that is the unit the target is set
in. An option with delta d moves d rupees of premium per index point, so:

    break-even points = (statutory cost + spread) / delta

with statutory cost = 0.2383% x premium. Both terms are per unit of premium,
and dividing by delta converts them into the index move that pays for them.

Two forces pull in opposite directions as delta falls:
  * cost in points falls, because premium falls faster than delta does
  * tick granularity bites, because a 1-point move at delta 0.10 is 0.10 of
    premium -- two ticks -- and you cannot capture a fraction of a tick
"""
from __future__ import annotations
from .costs import NSE_MEMBER, BSE_MEMBER, CostModel
from .instruments import NIFTY, BANKNIFTY, SENSEX, Spec
from .pricing import (bs_call, bs_delta_call, bs_theta_call, norm_cdf)


def strike_for_delta(spot: float, target_delta: float, t: float, iv: float,
                     step: float) -> tuple[float, float, float]:
    """Nearest listed strike to a target call delta -> (strike, delta, premium)."""
    best = None
    for i in range(-80, 81):
        k = round(spot / step) * step + i * step
        if k <= 0:
            continue
        d = bs_delta_call(spot, k, t, iv)
        err = abs(d - target_delta)
        if best is None or err < best[0]:
            best = (err, k, d, bs_call(spot, k, t, iv))
    _, k, d, p = best
    return k, d, p


def breakeven_points(premium: float, delta: float, spread_ticks: float,
                     cost: CostModel = NSE_MEMBER, tick: float = 0.05,
                     cross: bool = True) -> dict:
    """Index points a round trip must move before it pays for itself.

    `cross=True` assumes marketable limits both ways, so the full spread is
    paid. `cross=False` assumes both legs rest and get filled at their own
    price -- which is the market-making case, and carries adverse selection
    this function does not attempt to price.
    """
    if delta <= 0.0:
        return dict(points=float("inf"), stat=0.0, spread=0.0)
    stat = cost.round_trip_frac() * premium          # rupees per unit
    sprd = spread_ticks * tick if cross else 0.0
    total = stat + sprd
    return dict(points=total / delta,
                stat_points=stat / delta,
                spread_points=sprd / delta,
                rupees_per_unit=total,
                ticks_per_point=delta / tick)


def required_hit_rate(delta: float, premium: float, target_pts: float,
                      stop_pts: float, spread_ticks: float,
                      cost: CostModel = NSE_MEMBER, tick: float = 0.05,
                      cross: bool = True) -> float:
    """p such that p*win = (1-p)*loss. Costs are paid on BOTH outcomes."""
    c = breakeven_points(premium, delta, spread_ticks, cost, tick, cross)
    C = c["rupees_per_unit"]
    win = delta * target_pts - C
    loss = delta * stop_pts + C
    if win <= 0.0:
        return float("inf")          # target cannot cover its own costs
    return loss / (win + loss)


def theta_drag_points(spot: float, strike: float, t_years: float, iv: float,
                      delta: float, hold_s: float) -> float:
    """Index points of decay charged for holding `hold_s` seconds."""
    if delta <= 0.0:
        return 0.0
    th_year = bs_theta_call(spot, strike, t_years, iv)       # negative
    per_s = -th_year / (365.0 * 24.0 * 3600.0)
    return per_s * hold_s / delta


def random_walk_hit_rate(target_pts: float, stop_pts: float) -> float:
    """P(target before stop) for a driftless walk: the baseline to beat.

    A required hit rate means nothing on its own. 68.7% sounds hard or easy
    depending on what chance already gives you, and for a symmetric walk with
    barriers at T and S that is S/(T+S) -- so a 2-point target with a 1-point
    stop hits one third of the time before you have any view at all. The number
    that matters is the gap between the two.
    """
    if target_pts <= 0 or stop_pts <= 0:
        return 0.0
    return stop_pts / (target_pts + stop_pts)


def edge_table(spot: float, t: float, iv: float, spec: Spec,
               spread_ticks: float, cost: CostModel,
               combos=((1.0, 1.0), (2.0, 1.0), (2.0, 2.0), (3.0, 1.5),
                       (5.0, 2.5)), cross: bool = True) -> list:
    k, d, prem = strike_for_delta(spot, 0.45, t, iv, spec.strike_step)
    rows = []
    for T, S in combos:
        need = required_hit_rate(d, prem, T, S, spread_ticks, cost,
                                 cross=cross)
        base = random_walk_hit_rate(T, S)
        rows.append(dict(target=T, stop=S, need=need, base=base,
                         gap=(need - base) if need != float("inf") else float("inf"),
                         delta=d, premium=prem, strike=k))
    return rows


def report(spot: float = 23_200.0, days: float = 3.0, iv: float = 0.14,
           spec: Spec = NIFTY, spread_ticks: float = 2.0,
           targets=(1.0, 2.0, 3.0, 5.0), hold_s: float = 30.0,
           cost: CostModel = NSE_MEMBER, capital: float = 500_000.0,
           deploy: float = 0.5) -> str:
    t = days / 365.0
    out = []
    a = out.append
    a(f"DIRECTIONAL SCALP  {spec.symbol} {spot:,.0f}  {days:.0f}d to expiry  "
      f"IV {iv:.0%}  lot {spec.lot}")
    a("")
    a("1. BREAK-EVEN IN INDEX POINTS, by delta")
    a(f"   marketable limit crosses a {spread_ticks:.0f}-tick spread both ways; "
      f"passive pays none")
    a(f"   {'delta':>7}{'strike':>9}{'premium':>9}{'stat':>8}{'spread':>8}"
      f"{'CROSS':>8}{'PASSIVE':>9}{'ticks/pt':>10}")
    rows = []
    for td in (0.70, 0.60, 0.50, 0.45, 0.40, 0.30, 0.20, 0.10, 0.05):
        k, d, p = strike_for_delta(spot, td, t, iv, spec.strike_step)
        bc = breakeven_points(p, d, spread_ticks, cost, cross=True)
        bp = breakeven_points(p, d, spread_ticks, cost, cross=False)
        rows.append((d, k, p, bc, bp))
        a(f"   {d:>7.3f}{k:>9,.0f}{p:>9,.2f}{bc['stat_points']:>8.2f}"
          f"{bc['spread_points']:>8.2f}{bc['points']:>8.2f}"
          f"{bp['points']:>9.2f}{bc['ticks_per_point']:>10.1f}")
    best = min(rows, key=lambda r: r[3]["points"])
    a(f"   Minimum at delta {best[0]:.2f} ({best[3]['points']:.2f} points). "
      f"The curve is flat from")
    a("   0.30 to 0.60 and rises sharply below 0.20: statutory cost in points")
    a("   FALLS as delta falls, but spread cost in points RISES faster. Your")
    a("   0.40-0.50 band is the optimum, and it is the optimum for that reason.")
    a("   Below ~1 tick per point the target is finer than the price grid.")
    a("")
    a("2. WHAT THE TARGET HAS TO BEAT (delta 0.45, marketable)")
    a(f"   {'target':>8}{'stop':>7}{'required':>11}{'by chance':>11}"
      f"{'EDGE NEEDED':>13}")
    for r in edge_table(spot, t, iv, spec, spread_ticks, cost, cross=True):
        need = "never" if r["need"] == float("inf") else f"{r['need']*100:.1f}%"
        gap = "-" if r["gap"] == float("inf") else f"+{r['gap']*100:.1f}pp"
        a(f"   {r['target']:>7.1f}p{r['stop']:>6.1f}p{need:>11}"
          f"{r['base']*100:>10.1f}%{gap:>13}")
    a("   'by chance' is a driftless walk hitting the target before the stop,")
    a("   S/(T+S). The gap is the directional edge you must actually supply.")
    a("")
    a("3. SAME, RESTING PASSIVE (no spread paid)")
    a(f"   {'target':>8}{'stop':>7}{'required':>11}{'by chance':>11}"
      f"{'EDGE NEEDED':>13}")
    for r in edge_table(spot, t, iv, spec, spread_ticks, cost, cross=False):
        need = "never" if r["need"] == float("inf") else f"{r['need']*100:.1f}%"
        gap = "-" if r["gap"] == float("inf") else f"+{r['gap']*100:.1f}pp"
        a(f"   {r['target']:>7.1f}p{r['stop']:>6.1f}p{need:>11}"
          f"{r['base']*100:>10.1f}%{gap:>13}")
    a("   Cheaper, and it fights the trade: a resting BID fills when sellers")
    a("   hit it, which is when price is going DOWN. You cannot both buy the")
    a("   direction and wait to be hit -- passive fills select for the trades")
    a("   that go against you. Marketable limit (capped price, crosses now) is")
    a("   the version compatible with a directional entry.")
    a("")
    a("4. SPREAD SENSITIVITY at delta 0.45 -- the number to verify on your feed")
    k45, d45, p45 = strike_for_delta(spot, 0.45, t, iv, spec.strike_step)
    a(f"   {'spread':>9}{'break-even pts':>16}{'need @2p/1p stop':>19}")
    for st in (0.0, 1.0, 2.0, 4.0, 8.0):
        b = breakeven_points(p45, d45, st, cost, cross=True)
        h = required_hit_rate(d45, p45, 2.0, 1.0, st, cost)
        hs = "never" if h == float("inf") else f"{h*100:.1f}%"
        a(f"   {st:>6.0f} tk{b['points']:>16.2f}{hs:>19}")
    a("")
    a(f"5. THETA, charged on both winners and losers ({hold_s:.0f}s hold)")
    a(f"   {'delta':>7}{'theta/day':>11}{'pts per hold':>14}"
      f"{'% of a 2pt target':>19}")
    for d, k, p, bc, bp in rows[:6]:
        th_day = -bs_theta_call(spot, k, t, iv) / 365.0
        pts = theta_drag_points(spot, k, t, iv, d, hold_s)
        a(f"   {d:>7.3f}{th_day:>11,.2f}{pts:>14.3f}{pts/2.0*100:>18.1f}%")
    a("   Negligible per trade at these hold times. It stops being negligible")
    a("   if a trade sits waiting for its target.")
    a("")
    a(f"6. SIZING at {capital:,.0f} capital, {deploy:.0%} deployed")
    prem_rs = p45 * spec.lot
    lots = int(capital * deploy / prem_rs) if prem_rs > 0 else 0
    a(f"   delta {d45:.2f} strike {k45:,.0f} premium {p45:,.2f} "
      f"-> {prem_rs:,.0f} per lot")
    a(f"   {lots} lots = {lots*prem_rs:,.0f} outlaid")
    a(f"   {'target':>8}{'stop':>7}{'nominal R:R':>13}{'win Rs':>11}"
      f"{'loss Rs':>11}{'REAL R:R':>10}")
    for T, S in ((1.0, 1.0), (2.0, 1.0), (2.0, 2.0), (3.0, 1.5), (5.0, 2.5)):
        C = breakeven_points(p45, d45, spread_ticks, cost)["rupees_per_unit"]
        win = (d45 * T - C) * spec.lot * lots
        loss = (d45 * S + C) * spec.lot * lots
        a(f"   {T:>7.1f}p{S:>6.1f}p{T/S:>12.2f}:1{win:>11,.0f}"
          f"{-loss:>11,.0f}{win/loss if loss else 0:>9.2f}:1")
    a("   Look at the last column. Costs are charged on BOTH outcomes, so they")
    a("   are subtracted from the win AND added to the loss. A nominal 2:1")
    a("   target-to-stop is a 0.72:1 reward-to-risk once that lands. The ratio")
    a("   you set is not the ratio you get, and the gap widens as the target")
    a("   shrinks.")
    a("   A 1-point stop is inside the noise this strategy is built on: an")
    a("   index oscillating 5 points a candle will take it constantly. Sizing")
    a("   here is capital-bound, not risk-bound, which is the trap -- the stop")
    a("   being tiny lets you carry far more lots than the signal justifies.")
    return "\n".join(out)


def main() -> int:
    import argparse
    from .instruments import ALL
    p = argparse.ArgumentParser(description="Directional scalp economics")
    p.add_argument("--symbol", default="NIFTY", choices=sorted(ALL))
    p.add_argument("--spot", type=float, default=23_200.0)
    p.add_argument("--days", type=float, default=3.0)
    p.add_argument("--iv", type=float, default=0.14)
    p.add_argument("--spread-ticks", type=float, default=2.0)
    p.add_argument("--hold-s", type=float, default=30.0)
    p.add_argument("--capital", type=float, default=500_000.0)
    p.add_argument("--deploy", type=float, default=0.5)
    a = p.parse_args()
    spec = ALL[a.symbol]
    cost = BSE_MEMBER if spec.venue == "BSE" else NSE_MEMBER
    print(report(a.spot, a.days, a.iv, spec, a.spread_ticks,
                 hold_s=a.hold_s, cost=cost, capital=a.capital,
                 deploy=a.deploy))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
