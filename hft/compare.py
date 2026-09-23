"""Three strategies, identical index paths, identical capital and signal.

The only honest way to ask "which one makes most" when none of them has seen a
real feed is to give them the same market and the same directional signal, and
vary how good that signal is. What separates them then is structure, not luck.

  A. CANDLE SCALP  -- the no-stop rules: read the open, TP 1-2 points, trail,
     flip on retracement, punch in as many orders as the window allows.
  B. DIRECTIONAL SCALP -- 2-point target, 1-point stop, one position at a time.
  C. OTM STRIP -- buy every call out to 30 delta at the open, hold the window,
     close. One round trip, no re-entries.

The result is decided by a quantity that is easy to miss: how many times each
one pays the toll. A pays it ~20 times per candle, B a few, C exactly once.
"""
from __future__ import annotations
import random

from .candle_scalp import Rules, path, run_candle
from .costs import NSE_MEMBER
from .instruments import NIFTY
from .scalp import strike_for_delta, breakeven_points
from .strip import build_strip, totals, value_at

SPOT, DAYS, IV = 23_200.0, 3.0, 0.14
T = DAYS / 365.0
CAPITAL, DEPLOY = 500_000.0, 0.5
WINDOW_S = 300.0
STEPS_PER_S = 2.0


def _strip_setup():
    legs = build_strip(SPOT, T, IV, NIFTY, max_delta=0.30)
    one = totals(legs, NIFTY.lot)
    n = max(int(CAPITAL * DEPLOY / one["premium"]), 1)
    tot = totals(legs, NIFTY.lot, n)
    cost = NSE_MEMBER.round_trip_frac() * tot["premium"]
    return legs, n, tot, cost


def _scalp_setup():
    k, d, prem = strike_for_delta(SPOT, 0.45, T, IV, NIFTY.strike_step)
    be = breakeven_points(prem, d, 2.0, NSE_MEMBER)
    lots = max(int(CAPITAL * DEPLOY / (prem * NIFTY.lot)), 1)
    return d, prem, be["points"], lots


def run_window(px: list[float], rules_a: Rules, rules_b: Rules,
               strip, scalp) -> dict:
    """One candle. All three see the same path and read the same open."""
    legs, n_strip, tot, strip_cost = strip
    delta45, prem45, be_pts, lots45 = scalp
    rs_per_point = delta45 * NIFTY.lot * lots45

    a = run_candle(px, rules_a, be_pts, STEPS_PER_S)
    b = run_candle(px, rules_b, be_pts, STEPS_PER_S)

    # C: read the same open, buy the strip, hold the window, close
    open_i = int(rules_a.open_ticks_s * STEPS_PER_S)
    move0 = px[open_i] if open_i < len(px) else 0.0
    if abs(move0) < rules_a.open_min_points:
        c_pnl = 0.0
    else:
        final = px[-1] - px[open_i]
        # a short direction is the mirrored strip; the arithmetic is symmetric
        signed = final if move0 > 0 else -final
        held_days = (WINDOW_S - rules_a.open_ticks_s) / 375.0 / 60.0
        v0 = value_at(legs, SPOT, 0.0, T, 0.0, IV, NIFTY.lot, n_strip)
        v1 = value_at(legs, SPOT, signed, T, held_days, IV, NIFTY.lot, n_strip)
        c_pnl = v1 - v0 - strip_cost

    return dict(a=a.pnl_points * rs_per_point, a_entries=a.entries,
                b=b.pnl_points * rs_per_point, b_entries=b.entries,
                c=c_pnl)


def compare(n_candles: int = 4_000, range_pts: float = 32.0,
            drifts=(0.0, 2.0, 5.0, 10.0, 20.0), seed: int = 11) -> str:
    strip = _strip_setup()
    scalp = _scalp_setup()
    legs, n_strip, tot, strip_cost = strip
    delta45, prem45, be_pts, lots45 = scalp

    rules_a = Rules(tp_points=1.0, arm_points=1.0, trail_points=0.5,
                    lock_points=0.2, retrace_points=2.0, max_entries=40)
    rules_b = Rules(tp_points=2.0, stop_points=1.0, arm_points=2.0,
                    trail_points=0.5, lock_points=0.2, retrace_points=99.0,
                    max_entries=3)

    out, a = [], None
    a = out.append
    a(f"THREE STRATEGIES, SAME PATHS  ({n_candles:,} five-minute candles, "
      f"{range_pts:.0f}-point range)")
    a(f"capital {CAPITAL:,.0f}, {DEPLOY:.0%} deployed, same open-direction "
      f"signal for all three")
    a(f"  A candle scalp   no stop, TP 1pt, trail, flip, up to 40 entries   "
      f"cost {be_pts:.2f} pts/trip")
    a(f"  B directional    TP 2pt / stop 1pt, max 3 entries")
    a(f"  C OTM strip      {len(legs)} legs to 30 delta, {n_strip} lots each, "
      f"{tot['premium']:,.0f} outlay, ONE trip")
    a("")
    a(f"   {'drift':>7}{'A entries':>11}{'A mean':>12}{'B entries':>11}"
      f"{'B mean':>12}{'C mean':>12}{'winner':>10}")
    rows = []
    for dr in drifts:
        rng = random.Random(seed)
        n = int(WINDOW_S * STEPS_PER_S)
        sa = sb = sc = 0.0
        ea = eb = 0
        for _ in range(n_candles):
            px = path(n, range_pts / 1.5958, rng, dr)
            r = run_window(px, rules_a, rules_b, strip, scalp)
            sa += r["a"]; sb += r["b"]; sc += r["c"]
            ea += r["a_entries"]; eb += r["b_entries"]
        ma, mb, mc = sa / n_candles, sb / n_candles, sc / n_candles
        win = max((ma, "A"), (mb, "B"), (mc, "C"))[1]
        rows.append((dr, ma, mb, mc))
        a(f"   {dr:>6.0f}p{ea/n_candles:>11.1f}{ma:>+12,.0f}"
          f"{eb/n_candles:>11.1f}{mb:>+12,.0f}{mc:>+12,.0f}{win:>10}")
    a("")
    a("   'drift' is the directional edge: points the candle travels, on")
    a("   average, in the direction the open pointed. Zero drift is no signal.")
    a("")
    first = {k: None for k in "ABC"}
    for dr, ma, mb, mc in rows:
        for k, v in (("A", ma), ("B", mb), ("C", mc)):
            if first[k] is None and v > 0:
                first[k] = dr
    a("   Drift at which each first turns positive:")
    for k in "ABC":
        v = first[k]
        a(f"     {k}: {'never in this range' if v is None else f'{v:.0f} points'}")
    a("   That gap is the whole result, and it is not about signal quality --")
    a("   all three see the SAME signal. It is how many times each pays the")
    a("   toll: A about 20 times a candle, B up to 3, C exactly once.")
    return "\n".join(out)


def main() -> int:
    import argparse
    p = argparse.ArgumentParser(description="Compare the three strategies")
    p.add_argument("--candles", type=int, default=4_000)
    p.add_argument("--range", type=float, default=32.0)
    a = p.parse_args()
    print(compare(a.candles, a.range))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
