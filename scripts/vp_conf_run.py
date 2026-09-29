"""Confluence against the best single setup, on the same windows and control."""
from __future__ import annotations
import datetime as dt
import json, os, statistics, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import vp_of_pure as P
from vp_confluence import combine, MODES
from vp_options import (BASE, CONTRACT, SYMS, control, month_window,
                        run_options, signals_for, stats)


def cell(st, vols, plans, win, label, quiet=False):
    allt, counts = [], {}
    for sym, _ in SYMS:
        lo, hi = win[sym]
        if lo is None:
            continue
        tr, _ = run_options(st[sym], plans[sym], vols[sym], dict(BASE),
                            lo, hi, CONTRACT[sym])
        counts[sym] = len(tr)
        for t in tr:
            t["sym"] = sym
        allt += tr
    allt.sort(key=lambda t: t["t_in"])
    s = stats(allt, BASE["equity"])
    if s is None:
        print(f"{label:<22}  no trades")
        return None
    dists = []
    for sym, _ in SYMS:
        lo, hi = win[sym]
        if lo is None or counts.get(sym, 0) < 5:
            continue
        d = control(st[sym], plans[sym], vols[sym], dict(BASE), CONTRACT[sym],
                    counts[sym], lo, hi, seed=abs(hash((label, sym))) % 10 ** 6)
        if d:
            dists.append(d)
    c95 = pct = float("nan")
    if dists:
        merged = sorted(sum(v) / len(v) for v in zip(*dists))
        c95 = merged[int(len(merged) * 0.95)]
        pct = 100.0 * sum(1 for v in merged if v < s["pf"]) / len(merged)
    if not quiet:
        print(f"{label:<22}{s['n']:>6}{s['pf']:>8.3f}{s['win']:>7.1f}"
              f"{s['net']:>11,.0f}{s['final']:>11,.0f}{s['dd']:>8.1f}"
              f"{s['med']:>8,.0f}{c95:>7.2f}{pct:>6.1f}", flush=True)
    return dict(label=label, c95=c95, pct=pct, **s)


def main():
    data, voldir = sys.argv[1], sys.argv[2]
    st, vols = {}, {}
    for sym, vx in SYMS:
        st[sym] = P.state(json.load(open(os.path.join(data, f"{sym}.json"))))
        vols[sym] = json.load(open(os.path.join(voldir, f"{vx}.json")))
    names = ["dva_edge_fade"] + list(P.REGISTRY)
    sigs = {s: {nm: signals_for(st[s], nm) for nm in names} for s in st}

    windows = {"August only": {s: month_window(st[s]["bars"], 2026, 8)
                               for s, _ in SYMS},
               "Jul-Sep": {s: (0, st[s]["n"]) for s, _ in SYMS}}

    for wlab, win in windows.items():
        print(f"\n===== {wlab} =====")
        print(f"{'plan':<22}{'n':>6}{'PF':>8}{'win%':>7}{'net $':>11}"
              f"{'final $':>11}{'maxDD%':>8}{'med $':>8}{'ctl95':>7}{'pct':>6}")
        # the singles, as the thing confluence has to beat
        for nm in ("naked_poc_flow", "dva_edge_fade"):
            cell(st, vols, {s: sigs[s][nm] for s in st}, win, nm)
        for m in MODES:
            plans = {s: combine(sigs[s], st[s]["n"], m) for s in st}
            cell(st, vols, plans, win, m)
        # robustness: whose stop the combined trade inherits
        for m in ("conf2", "conf2_distinct"):
            plans = {s: combine(sigs[s], st[s]["n"], m, "tightest")
                     for s in st}
            cell(st, vols, plans, win, m + " (tight stop)")


if __name__ == "__main__":
    main()
