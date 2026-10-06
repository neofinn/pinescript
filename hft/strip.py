"""Buy every option out to 30 delta in one direction, and let them move.

This is a convexity trade, not a scalp, and it fails or succeeds on one ratio.
Every option decays, and every option earns by the underlying moving. The
question of whether holding a strip of them pays is therefore:

    points_per_day_to_stand_still = theta_per_day / delta

That number is the index move per day the position needs just to break even on
decay, before any profit. Its behaviour across the chain is the whole story,
and it is the opposite of the intuition that draws people to cheap options:

  * an ATM option has the LARGEST theta in rupees, but also the largest delta,
    and the ratio is at its best there
  * a 0.30 delta option decays less in rupees but far less again in delta, and
    needs a BIGGER daily move to stand still
  * a 0.05 delta option is cheap precisely because it is unlikely to matter,
    and needs the biggest move of all

So "buy everything out to 30 delta" is a deliberate selection of the worst
theta-to-delta ratios on the board. That is not automatically wrong -- it is
what buying convexity costs, and a large enough move pays for it many times
over -- but it means the trade is a bet on the SIZE of the move, not on its
direction. Sizing it as a directional trade misreads what was bought.

Cost note: the statutory stack is proportional to premium and carries no
per-order term, so an eight-leg strip pays the same 0.2383% as one leg of the
same value. Leg count is free here. Decay is not.
"""
from __future__ import annotations
from dataclasses import dataclass

from .costs import CostModel, NSE_MEMBER
from .instruments import NIFTY, Spec
from .pricing import (bs_call, bs_put, bs_delta_call, bs_delta_put,
                      bs_gamma, bs_theta_call, bs_theta_put)


@dataclass
class Leg:
    strike: float
    is_call: bool
    premium: float
    delta: float
    gamma: float
    theta_day: float          # negative


def build_strip(spot: float, t_years: float, iv: float, spec: Spec,
                max_delta: float = 0.30, min_delta: float = 0.02,
                is_call: bool = True) -> list[Leg]:
    """Every listed strike whose delta falls in [min_delta, max_delta]."""
    legs = []
    atm = round(spot / spec.strike_step) * spec.strike_step
    rng = range(0, 120) if is_call else range(-120, 1)
    for i in rng:
        k = atm + i * spec.strike_step
        if k <= 0:
            continue
        d = (bs_delta_call(spot, k, t_years, iv) if is_call
             else bs_delta_put(spot, k, t_years, iv))
        ad = abs(d)
        if not (min_delta <= ad <= max_delta):
            continue
        p = (bs_call(spot, k, t_years, iv) if is_call
             else bs_put(spot, k, t_years, iv))
        th = (bs_theta_call(spot, k, t_years, iv) if is_call
              else bs_theta_put(spot, k, t_years, iv)) / 365.0
        legs.append(Leg(k, is_call, p, d, bs_gamma(spot, k, t_years, iv), th))
    legs.sort(key=lambda l: -abs(l.delta))
    return legs


def actual_decay(legs: list[Leg], spot: float, t_years: float, iv: float,
                 days: float, lot: int, lots_per_leg: int = 1) -> float:
    """Decay by revaluation, which is what you actually lose.

    BS theta is an instantaneous derivative and it overstates discrete decay
    badly near expiry -- on the 23,800 leg above it prints -2.95 per day
    against a premium of 2.75, which would have the option worth less than
    nothing by tomorrow. Revaluing the position at t-days is the honest
    version, and it is what section 3 uses.
    """
    now = value_at(legs, spot, 0.0, t_years, 0.0, iv, lot, lots_per_leg)
    later = value_at(legs, spot, 0.0, t_years, days, iv, lot, lots_per_leg)
    return later - now


def leg_decay(leg: Leg, spot: float, t_years: float, iv: float,
              days: float) -> float:
    t2 = max(t_years - days / 365.0, 1e-6)
    f = bs_call if leg.is_call else bs_put
    return f(spot, leg.strike, t2, iv) - f(spot, leg.strike, t_years, iv)


def totals(legs: list[Leg], lot: int, lots_per_leg: int = 1) -> dict:
    prem = sum(l.premium for l in legs) * lot * lots_per_leg
    dlt = sum(l.delta for l in legs) * lot * lots_per_leg
    gam = sum(l.gamma for l in legs) * lot * lots_per_leg
    th = sum(l.theta_day for l in legs) * lot * lots_per_leg
    dlt_u = sum(l.delta for l in legs)
    th_u = sum(l.theta_day for l in legs)
    return dict(legs=len(legs), premium=prem, delta=dlt, gamma=gam,
                theta_day=th,
                points_per_day=(-th_u / dlt_u) if dlt_u else float("inf"),
                delta_units=dlt_u)


def value_at(legs: list[Leg], spot0: float, move_pts: float, t_years: float,
             days_elapsed: float, iv: float, lot: int,
             lots_per_leg: int = 1) -> float:
    s = spot0 + move_pts
    t = max(t_years - days_elapsed / 365.0, 1e-6)
    v = 0.0
    for l in legs:
        v += (bs_call(s, l.strike, t, iv) if l.is_call
              else bs_put(s, l.strike, t, iv))
    return v * lot * lots_per_leg


def report(spot: float = 23_200.0, days: float = 3.0, iv: float = 0.14,
           spec: Spec = NIFTY, capital: float = 500_000.0,
           deploy: float = 0.5, max_delta: float = 0.30,
           cost: CostModel = NSE_MEMBER) -> str:
    t = days / 365.0
    out = []
    a = out.append
    legs = build_strip(spot, t, iv, spec, max_delta=max_delta)
    if not legs:
        return "no strikes in that delta band"

    a(f"OTM STRIP  {spec.symbol} {spot:,.0f}  {days:.0f}d  IV {iv:.0%}  "
      f"lot {spec.lot}  all calls with delta <= {max_delta}")
    a("")
    a("1. THE LEGS   (decay measured by revaluation, not by BS theta)")
    a(f"   {'strike':>9}{'delta':>8}{'premium':>10}{'1-day loss':>12}"
      f"{'% of prem':>11}{'pts/day to stand still':>25}")
    for l in legs:
        dec = leg_decay(l, spot, t, iv, 1.0)
        ppd = -dec / l.delta if l.delta else float("inf")
        a(f"   {l.strike:>9,.0f}{l.delta:>8.3f}{l.premium:>10.2f}"
          f"{dec:>12.2f}{-dec/l.premium*100:>10.0f}%{ppd:>25.1f}")
    katm = round(spot / spec.strike_step) * spec.strike_step
    d_atm = bs_delta_call(spot, katm, t, iv)
    p_atm = bs_call(spot, katm, t, iv)
    th_atm = bs_theta_call(spot, katm, t, iv) / 365.0
    atm_leg0 = Leg(katm, True, p_atm, d_atm, bs_gamma(spot, katm, t, iv), th_atm)
    dec_atm = leg_decay(atm_leg0, spot, t, iv, 1.0)
    a(f"   {'-- ATM --':>9}{d_atm:>8.3f}{p_atm:>10.2f}{dec_atm:>12.2f}"
      f"{-dec_atm/p_atm*100:>10.0f}%{-dec_atm/d_atm:>25.1f}")
    a("   The last column is the point of this table. It RISES as you go out:")
    a("   cheap options are cheap because they are unlikely to matter, and")
    a("   they need the biggest daily move just to stand still. Buying the")
    a("   whole band out to 30 delta selects the worst ratios on the board.")
    a("")

    tot = totals(legs, spec.lot)
    per_strip = tot["premium"]
    n = int(capital * deploy / per_strip) if per_strip > 0 else 0
    n = max(n, 1)
    T = totals(legs, spec.lot, n)
    a(f"2. THE POSITION  ({capital:,.0f} capital, {deploy:.0%} deployed)")
    a(f"   one strip = {tot['legs']} legs, {per_strip:,.0f} outlay")
    a(f"   {n} lots per leg -> {T['premium']:,.0f} outlaid "
      f"({T['premium']/capital*100:.0f}% of capital)")
    a(f"   net delta {T['delta']:>12,.1f}  (moves Rs{T['delta']:,.0f} "
      f"per index point)")
    a(f"   theta/day {T['theta_day']:>12,.0f}  "
      f"({-T['theta_day']/capital*100:.1f}% of capital PER DAY)")
    a(f"   the position needs {T['points_per_day']:.1f} index points per day "
      f"just to stand still")
    a(f"   statutory cost round trip "
      f"{cost.round_trip_frac()*T['premium']:>10,.0f}")
    a("")

    a("3. HOLDING IN MINUTES -- the scale this is actually traded on")
    a("   A day's decay spread over the 375-minute session (conservative: it")
    a("   treats all of the calendar day's decay as landing during trading).")
    a(f"   {'hold':>8}{'decay Rs':>12}{'per minute':>12}"
      f"{'points needed in your direction':>34}")
    for mins in (1, 5, 15, 30, 60, 375):
        dd = actual_decay(legs, spot, t, iv, mins / 375.0, spec.lot, n)
        need = -dd / T["delta"] if T["delta"] else float("inf")
        a(f"   {mins:>6}m{dd:>12,.0f}{dd/mins:>12,.0f}{need:>34.2f}")
    a("   At a 5-minute hold the bar is small. At a full day it is not. The")
    a("   'let them move' instruction is the whole risk: this position is")
    a("   fine for minutes and ruinous overnight.")
    a("")

    a("4. WHAT IT PAYS  (P&L in rupees, net of the round trip)")
    a("   rows: index move. columns: days held. Decay is charged either way.")
    c = cost.round_trip_frac() * T["premium"]
    holds = [0.0, 0.5, 1.0, 2.0]
    a(f"   {'move':>8}" + "".join(f"{f'{h:g}d':>13}" for h in holds))
    for mv in (-100, -50, -25, 0, 25, 50, 100, 200, 300):
        cells = []
        for h in holds:
            v = value_at(legs, spot, float(mv), t, h, iv, spec.lot, n)
            cells.append(f"{v - T['premium'] - c:>+13,.0f}")
        a(f"   {mv:>+7,}p" + "".join(cells))
    a("")

    a("5. THE SAME MONEY IN ONE ATM STRIKE")
    a("   Convexity is only worth buying if it beats the simple thing.")
    atm_leg = [Leg(katm, True, p_atm, d_atm, bs_gamma(spot, katm, t, iv), th_atm)]
    n_atm = max(int(capital * deploy / (p_atm * spec.lot)), 1)
    Ta = totals(atm_leg, spec.lot, n_atm)
    ca = cost.round_trip_frac() * Ta["premium"]
    a(f"   {n_atm} ATM lots = {Ta['premium']:,.0f} outlaid, "
      f"delta {Ta['delta']:,.1f}, theta/day {Ta['theta_day']:,.0f}")
    a(f"   needs {Ta['points_per_day']:.1f} points/day to stand still "
      f"(strip needs {T['points_per_day']:.1f})")
    a("")
    a(f"   {'move':>8}{'STRIP 0d':>14}{'ATM 0d':>14}{'STRIP 1d':>14}"
      f"{'ATM 1d':>14}")
    for mv in (-100, -50, 0, 50, 100, 200, 300, 500):
        s0 = value_at(legs, spot, float(mv), t, 0.0, iv, spec.lot, n) - T["premium"] - c
        a0 = value_at(atm_leg, spot, float(mv), t, 0.0, iv, spec.lot, n_atm) - Ta["premium"] - ca
        s1 = value_at(legs, spot, float(mv), t, 1.0, iv, spec.lot, n) - T["premium"] - c
        a1 = value_at(atm_leg, spot, float(mv), t, 1.0, iv, spec.lot, n_atm) - Ta["premium"] - ca
        a(f"   {mv:>+7,}p{s0:>+14,.0f}{a0:>+14,.0f}{s1:>+14,.0f}{a1:>+14,.0f}")
    return "\n".join(out)


def main() -> int:
    import argparse
    from .instruments import ALL
    p = argparse.ArgumentParser(description="OTM strip economics")
    p.add_argument("--symbol", default="NIFTY", choices=sorted(ALL))
    p.add_argument("--spot", type=float, default=23_200.0)
    p.add_argument("--days", type=float, default=3.0)
    p.add_argument("--iv", type=float, default=0.14)
    p.add_argument("--capital", type=float, default=500_000.0)
    p.add_argument("--deploy", type=float, default=0.5)
    p.add_argument("--max-delta", type=float, default=0.30)
    a = p.parse_args()
    print(report(a.spot, a.days, a.iv, ALL[a.symbol], a.capital, a.deploy,
                 a.max_delta))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
