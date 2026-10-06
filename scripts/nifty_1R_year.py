"""1R fixed risk, maximum reward, on every bar of 2026 that exists.

A YEAR OF FIVE-MINUTE DATA DOES NOT EXIST HERE, and that is a data fact rather
than a choice. Yahoo serves 5m for 60 days only -- 1y, 6mo, 3mo and 90d all
return HTTP errors at that granularity, checked rather than assumed -- and the
NSE endpoints that would carry more return 403 from this container. So:

  M5   the whole 5m window available: 59 sessions, Jul 8 - Sep 29 2026
  H1   the whole of 2026: 171 sessions, Jan 1 - Sep 11

The hourly run is the closest thing to the year you asked for, and it is a
better test than the 5m one for exactly that reason -- 171 sessions can support
a 160-cell search in a way 20 sessions cannot.

1R means a FIXED risk unit per trade, not compounding, so results are in R
multiples and the arithmetic cannot run away with itself the way 100%-risk
compounding did. Total R is the honest scoreboard: it is what the strategy
earned per unit risked, independent of account size.

The maximum over a grid is reported next to what the same grid yields on random
entries, because a maximum without that is a statement about the grid.
"""
from __future__ import annotations
import datetime as dt
import itertools, json, os, random, statistics, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import vp_of_pure as P
from india_options import SPEC
from nifty_sept_atm import run, stats, random_plans, EQUITY, RISK, RRS, HOLDS, EXPIRY
from vp_confluence import combine, MODES
from vp_options import signals_for


def window_year(bars, year):
    lo = hi = None
    for i, b in enumerate(bars):
        if dt.datetime.utcfromtimestamp(b["t"]).year == year:
            if lo is None:
                lo = i
            hi = i + 1
    return lo, hi


def build(bars):
    st = P.state(bars)
    names = ["dva_edge_fade"] + list(P.REGISTRY)
    sigs = {nm: signals_for(st, nm) for nm in names}
    plans = dict(sigs)
    for m in MODES:
        plans[m] = combine(sigs, st["n"], m)
    return st, plans


def evaluate(label, bars, lo, hi, vix, spec, draws=30):
    st, plans = build(bars)
    grid = list(itertools.product(plans.keys(), EXPIRY, RRS, HOLDS))
    rows = []
    for (nm, eo, rr, hold) in grid:
        tr = run(st, plans[nm], vix, spec, rr, hold, eo, lo, hi)
        s = stats(tr)
        if s and s["n"] >= 10:
            rows.append(dict(plan=nm, expiry_only=eo, rr=rr, hold=hold,
                             R=s["net"] / RISK, **s))
    if not rows:
        print(f"{label}: no cell reached 10 trades")
        return None
    rows.sort(key=lambda r: -r["net"])
    ses = len({dt.datetime.utcfromtimestamp(b["t"]).date()
               for b in bars[lo:hi]})
    print(f"\n===== {label} — {ses} sessions, {hi - lo} bars, "
          f"{len(rows)}/{len(grid)} cells with >=10 trades =====")
    print(f"{'#':<3}{'plan':<19}{'expiry':<8}{'RR':>4}{'hold':>6}{'n':>5}"
          f"{'net Rs':>12}{'total R':>9}{'PF':>7}{'win%':>6}{'maxDD%':>8}")
    for k, r in enumerate(rows[:8]):
        print(f"{k+1:<3}{r['plan']:<19}{'expiry' if r['expiry_only'] else 'weekly':<8}"
              f"{r['rr']:>4.1f}{('none' if r['hold'] > 1000 else str(r['hold'])):>6}"
              f"{r['n']:>5}{r['net']:>12,.0f}{r['R']:>9.1f}{r['pf']:>7.2f}"
              f"{r['win']:>6.1f}{r['dd']:>8.1f}")
    pos = sum(1 for r in rows if r["net"] > 0)
    print(f"  profitable cells {pos}/{len(rows)}   "
          f"median cell {statistics.median(r['net'] for r in rows):,.0f} Rs "
          f"({statistics.median(r['R'] for r in rows):+.1f} R)")

    best = rows[0]
    maxes = []
    for draw in range(draws):
        rp_by_plan = {}
        for nm in plans:
            rl = random_plans(st, plans[nm], lo, hi, 1,
                              seed=7000 * draw + hash(nm) % 991)
            if rl:
                rp_by_plan[nm] = rl[0]
        cell = []
        for (nm, eo, rr, hold) in grid:
            rp = rp_by_plan.get(nm)
            if rp is None:
                continue
            s = stats(run(st, rp, vix, spec, rr, hold, eo, lo, hi))
            if s and s["n"] >= 10:
                cell.append(s["net"])
        if cell:
            maxes.append(max(cell))
    if maxes:
        maxes.sort()
        beat = 100.0 * sum(1 for m in maxes if m < best["net"]) / len(maxes)
        print(f"  RANDOM best-of-grid ({len(maxes)} draws, breadth matched): "
              f"median {statistics.median(maxes):,.0f} Rs "
              f"({statistics.median(maxes) / RISK:+.1f} R), "
              f"max {maxes[-1]:,.0f}")
        print(f"  the strategy's best sits at the {beat:.0f}th percentile "
              f"of random's best")
    return rows


def main():
    d = sys.argv[1]
    vix = {}
    for b in json.load(open(os.path.join(d, "INDIAVIX.json"))):
        k = str(dt.datetime.utcfromtimestamp(b["t"]).date())
        if k not in vix:
            vix[k] = b["c"]
    spec = SPEC["NIFTY"]
    print(f"NIFTY 50 ATM options, 1R = Rs {RISK:,.0f} fixed per trade "
          f"(no compounding), capital Rs {EQUITY:,.0f}")

    out = {}
    m5 = json.load(open(os.path.join(d, "NIFTY_wv.json")))
    out["m5"] = evaluate("M5 — the whole 5m window that exists", m5, 0, len(m5),
                         vix, spec)
    h1p = os.path.join(d, "..", "yr", "NIFTY_h1_wv.json")
    if os.path.exists(h1p):
        h1 = json.load(open(h1p))
        lo, hi = window_year(h1, 2026)
        out["h1"] = evaluate("H1 — all of 2026", h1, lo, hi, vix, spec)
    json.dump({k: v[:20] if v else None for k, v in out.items()},
              open(os.path.join(d, "nifty_1R_year.json"), "w"), indent=1,
              default=str)


if __name__ == "__main__":
    main()
