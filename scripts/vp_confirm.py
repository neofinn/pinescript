"""The two tests that decide it.

LAG-1 across the sweep. `dva_edge_fade` compares a bar's high against a value
area that bar's own volume helped place. No future data is used, so it is
legal -- but part of the signal may be a restatement of the bar's own range
rather than a property of the level. Recomputing the edge through bar i-1
removes that, and if the effect is real it should survive.

A SECOND CROSS-SECTION. Splitting 60 days in half and calling the back half
out-of-sample tests the second half of the same market. Ten DIFFERENT
instruments over the same dates is a different test: same regime, new names,
nothing about them used in choosing anything. The universe was fixed by dollar
volume rank 11-20 before the run, so it is not a search for names that agree.
"""
from __future__ import annotations
import json, os, statistics, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import volume_profile as vp
import vp_signals as S
from intraday_lab import context, run, score, COST
from vp_test import enrich, random_pool, pct_rank, pf
from vp_ablate import lag1
from vp_robust import trim

SET_A = "SPY QQQ NVDA TSLA AAPL AMD MSFT INTC META AMZN".split()
SET_B = "GOOGL AVGO IWM PLTR MU COIN NFLX MSTR SMCI XLF".split()


def sigs_for(raw, ctx, syms, nbins, va_pct, lag):
    out = {}
    for s in syms:
        _, vah, val = vp.developing(raw[s], nbins, va_pct=va_pct)
        if lag:
            vah, val = lag1(vah, val)
        x = dict(ctx[s]); x["dvah"], x["dval"] = vah, val
        out[s] = S.dva_edge_fade(x)
    return out


def cell(ctx, sigs, win, pools, syms, trim_frac=0.0):
    pooled, targets = [], {}
    for s in syms:
        a, b = win[s]
        tr, _ = run(ctx[s], sigs[s], stop_atr=2.0, rr=1.5,
                    cost_abs=COST.get(s, 0.02), max_hold=36, lo=a, hi=b)
        pooled += tr; targets[s] = len(tr)
    if len(pooled) < 20:
        return None
    strat = trim(pooled, trim_frac) if trim_frac else pooled
    dist = []
    for d in range(len(next(iter(pools.values())))):
        tr = []
        for s in syms:
            tr += pools[s][d][:targets[s]]
        if len(tr) >= 20:
            dist.append(pf(trim(tr, trim_frac) if trim_frac else tr))
    dist.sort()
    return dict(n=len(strat), pf=pf(strat), c95=dist[int(len(dist) * 0.95)],
                pct=pct_rank(pf(strat), dist), med=statistics.median(strat))


def load(data, syms):
    raw = {s: json.load(open(os.path.join(data, f"{s}.json"))) for s in syms}
    return raw, {s: enrich(raw[s]) for s in syms}


def main():
    dirA, dirB = sys.argv[1], sys.argv[2]
    rawA, ctxA = load(dirA, SET_A)
    rawB, ctxB = load(dirB, SET_B)

    splitA = {s: ctxA[s]["n"] // 2 for s in SET_A}
    WA = {"IS": {s: (0, splitA[s]) for s in SET_A},
          "OOS": {s: (splitA[s], ctxA[s]["n"]) for s in SET_A}}
    WB = {"ALL": {s: (0, ctxB[s]["n"]) for s in SET_B}}

    PA, PB = {}, {}
    for tag in ("IS", "OOS"):
        PA[tag] = {s: random_pool(ctxA[s], COST.get(s, 0.02), *WA[tag][s],
                                  seed=abs(hash((tag, s))) % 10**6) for s in SET_A}
    PB["ALL"] = {s: random_pool(ctxB[s], COST.get(s, 0.02), *WB["ALL"][s],
                                seed=abs(hash(("B", s))) % 10**6) for s in SET_B}

    print("== lag-1 across the parameter sweep (set A) ==")
    print(f"{'bins':>5}{'va%':>6}{'IS n':>7}{'IS PF':>8}{'IS pct':>8}"
          f"{'OOS n':>7}{'OOS PF':>8}{'OOS pct':>8}")
    for nb in (30, 45, 60, 90, 120):
        for va in (0.60, 0.70, 0.80):
            sg = sigs_for(rawA, ctxA, SET_A, nb, va, lag=True)
            o = []
            for tag in ("IS", "OOS"):
                r = cell(ctxA, sg, WA[tag], PA[tag], SET_A)
                o += [r["n"], r["pf"], r["pct"]]
            print(f"{nb:>5}{va:>6.2f}{o[0]:>7}{o[1]:>8.3f}{o[2]:>8.1f}"
                  f"{o[3]:>7}{o[4]:>8.3f}{o[5]:>8.1f}", flush=True)

    print("\n== second cross-section, ten different names, full 60 days ==")
    print(f"{'variant':<12}{'trim':<8}{'n':>6}{'PF':>8}{'ctl95':>8}"
          f"{'ratio':>8}{'pct':>7}{'med':>9}")
    for lag, lab in ((False, "as-tested"), (True, "lag-1")):
        sg = sigs_for(rawB, ctxB, SET_B, 60, 0.70, lag)
        for frac, tl in ((0.0, "none"), (0.01, "top1%")):
            r = cell(ctxB, sg, WB["ALL"], PB["ALL"], SET_B, frac)
            print(f"{lab:<12}{tl:<8}{r['n']:>6}{r['pf']:>8.3f}{r['c95']:>8.3f}"
                  f"{r['pf']/r['c95']:>8.3f}{r['pct']:>7.1f}{r['med']:>9.4f}",
                  flush=True)

    print(f"\n{'sym':<7}{'n':>6}{'PF':>8}{'pct':>8}")
    sg = sigs_for(rawB, ctxB, SET_B, 60, 0.70, lag=False)
    ok = 0
    for s in SET_B:
        a, b = WB["ALL"][s]
        tr, _ = run(ctxB[s], sg[s], stop_atr=2.0, rr=1.5,
                    cost_abs=COST.get(s, 0.02), max_hold=36, lo=a, hi=b)
        dist = sorted(pf(p[:len(tr)]) for p in PB["ALL"][s] if len(p[:len(tr)]) >= 10)
        pc = pct_rank(pf(tr), dist) if dist else float("nan")
        ok += pc >= 50
        print(f"{s:<7}{len(tr):>6}{pf(tr):>8.3f}{pc:>8.1f}")
    print(f"\nabove the control median: {ok}/10 names")


if __name__ == "__main__":
    main()
