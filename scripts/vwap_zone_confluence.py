"""VWAP and supply/demand as confluence gates on the profile+flow plans.

Two layers added on top of what already exists, each a different claim:

  VWAP      session-anchored, from the synthetic traded-value volume. Two
            opposite gates are tested rather than one, because "trade with
            VWAP" and "fade VWAP" are both widely taught and cannot both be
            right: vwap_trend takes longs only above it, vwap_revert only
            below.
  ZONES     supply and demand from zones.py -- a run of quiet candles that a
            large candle leaves in a hurry, live until price trades back
            through. The gate is not "price is in a zone" but "is there room":
            a long whose target sits beyond the nearest live supply has
            nowhere to go, and that is the testable version.

THE SAMPLE COST IS THE POINT. Every gate removes trades, and this project has
measured five times now that the removal costs more than the selectivity buys.
So every row carries the trades remaining, and the control is matched to that
count -- a gate that cuts 46 trades to 12 has to beat what random reaches at
12, not what it reaches at 46.
"""
from __future__ import annotations
import datetime as dt
import itertools, json, os, statistics, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import vp_of_pure as P
import zones as Z
from india_options import SPEC
from nifty_compound_sl import run, summary, CAP0
from nifty_sept_atm import RRS, HOLDS, EXPIRY, random_plans
from vp_confluence import combine, MODES
from vp_options import signals_for


def session_vwap(bars):
    """Anchored at each session open, from traded value. Causal by definition:
    bar i's VWAP includes bar i and nothing after it."""
    out = [None] * len(bars)
    cpv = cv = 0.0
    day = None
    for i, b in enumerate(bars):
        d = dt.datetime.utcfromtimestamp(b["t"]).date()
        if d != day:
            cpv = cv = 0.0
            day = d
        v = b["v"] or 0
        cpv += (b["h"] + b["l"] + b["c"]) / 3.0 * v
        cv += v
        out[i] = cpv / cv if cv > 0 else None
    return out


def gate(plan, bars, vwap, zn, mode, target_mult=3.0):
    """Return a copy of the plan with non-qualifying signals removed."""
    if mode == "none":
        return plan
    out = [None] * len(plan)
    for i, p in enumerate(plan):
        if p is None:
            continue
        sd, stop = p[0], p[1]
        c = bars[i]["c"]
        if mode in ("vwap_trend", "vwap_revert", "vwap+zone"):
            v = vwap[i]
            if v is None:
                continue
            above = c > v
            if mode == "vwap_revert":
                if (sd > 0) == above:
                    continue
            else:
                if (sd > 0) != above:
                    continue
        if mode in ("zone", "vwap+zone"):
            if stop is None:
                continue
            need = abs(c - stop) * target_mult      # how far the target sits
            r = Z.room(zn, i, c, sd)
            if r is not None and r < need:          # blocked before the target
                continue
        out[i] = p
    return out


GATES = ("none", "vwap_trend", "vwap_revert", "zone", "vwap+zone")

# A gate that leaves eight trades has not been tested, it has been described.
# The earlier version of this script allowed eight and the H1 baseline winner
# became a nine-trade cell reading 51.89x, against 31.16x for the thirty-five
# trade cell the stricter run had found. The threshold is the result.
MIN_N = 20


def main():
    d = sys.argv[1]
    sl = float(sys.argv[2]) if len(sys.argv) > 2 else 0.05
    vix = {}
    for b in json.load(open(os.path.join(d, "live", "INDIAVIX.json"))):
        k = str(dt.datetime.utcfromtimestamp(b["t"]).date())
        if k not in vix:
            vix[k] = b["c"]
    spec = SPEC["NIFTY"]
    print(f"NIFTY 50 ATM options, Rs {CAP0:,.0f}, {sl:.0%} compounding stop")
    print(f"VWAP + supply/demand confluence on the profile+flow plans\n")

    for path, yr, name in ((os.path.join(d, "live", "NIFTY_wv.json"), None,
                            "M5 - 59 sessions"),
                           (os.path.join(d, "yr", "NIFTY_h1_wv.json"), 2026,
                            "H1 - all of 2026")):
        bars = json.load(open(path))
        lo, hi = 0, len(bars)
        if yr:
            lo = hi = None
            for i, b in enumerate(bars):
                if dt.datetime.utcfromtimestamp(b["t"]).year == yr:
                    if lo is None:
                        lo = i
                    hi = i + 1
        st = P.state(bars)
        vw = session_vwap(bars)
        zn = Z.find_zones(bars)
        names = ["dva_edge_fade"] + list(P.REGISTRY)
        sigs = {nm: signals_for(st, nm) for nm in names}
        plans = dict(sigs)
        for m in MODES:
            plans[m] = combine(sigs, st["n"], m)
        grid = list(itertools.product(plans.keys(), EXPIRY, RRS, HOLDS))
        live = sum(1 for z in zn if z["broken"] is None)
        print(f"===== {name} =====   {len(zn)} zones found, {live} never broken")
        print(f"{'gate':<13}{'best plan':<19}{'n':>5}{'kept%':>7}{'final Rs':>14}"
              f"{'x':>7}{'PF':>7}{'maxDD%':>8}{'cells+':>8}"
              f"{'RANDOM med':>16}{'pct':>6}")
        base_n = None
        for g in GATES:
            rows = []
            for (nm, eo, rr, hold) in grid:
                pl = gate(plans[nm], bars, vw, zn, g, rr)
                tr, use, capped, breach, eq, raw, eq_raw = run(
                    st, pl, vix, spec, rr, hold, eo, lo, hi, sl)
                if len(tr) >= MIN_N:
                    rows.append(dict(plan=nm, **summary(tr, eq)))
            if not rows:
                print(f"{g:<13}  every cell fell below {MIN_N} trades")
                continue
            rows.sort(key=lambda r: -r["final"])
            b = rows[0]
            if g == "none":
                base_n = b["n"]
            pos = sum(1 for r in rows if r["final"] > CAP0)
            keep = 100.0 * b["n"] / base_n if base_n else 100.0
            # control matched to THIS gate's trade count
            ctl = []
            for draw in range(15):
                best_r = None
                for nm in plans:
                    rl = random_plans(st, plans[nm], lo, hi, 1,
                                      seed=90000 * draw + hash((nm, g)) % 953)
                    if not rl:
                        continue
                    rp = gate(rl[0], bars, vw, zn, g, 3.0)
                    for (eo, rr, hold) in itertools.product(EXPIRY, RRS, HOLDS):
                        tr, _, _, _, eq, _, _ = run(st, rp, vix, spec, rr,
                                                    hold, eo, lo, hi, sl)
                        if len(tr) >= MIN_N:
                            best_r = eq if best_r is None else max(best_r, eq)
                if best_r:
                    ctl.append(best_r)
            cs = f"{statistics.median(ctl):,.0f}" if ctl else "-"
            rank = (100.0 * sum(1 for c in ctl if c < b["final"]) / len(ctl)
                    if ctl else float("nan"))
            print(f"{g:<13}{b['plan']:<19}{b['n']:>5}{keep:>7.0f}"
                  f"{b['final']:>14,.0f}{b['final']/CAP0:>7.2f}{b['pf']:>7.2f}"
                  f"{b['dd']:>8.1f}{pos:>4}/{len(rows):<4}{cs:>16}{rank:>6.0f}")
        print()


if __name__ == "__main__":
    main()
