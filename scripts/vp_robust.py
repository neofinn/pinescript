"""Three ways the surviving cell can still be nothing.

1. CONCENTRATION. A profit factor above 1 on a negative median trade is being
   carried by a handful of outliers. Dropping the best 1% of trades -- from the
   strategy AND from every control draw, so the comparison stays fair -- says
   whether the edge is the distribution or the tail.
2. BREADTH. Ten instruments. An effect should appear in most of them, not in
   two. A result that lives in one name is that name's news flow.
3. PARAMETERS. Bin count and value-area percentage are arbitrary. A real
   effect degrades smoothly as they move; a fitted one spikes at the value
   that was tried first and collapses either side.
"""
from __future__ import annotations
import json, os, statistics, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import volume_profile as vp
import vp_signals as S
from intraday_lab import run, score, COST
from vp_test import enrich, random_pool, pct_rank, pf, SYMS


def trim(trades, frac=0.01):
    """Drop the best `frac` of trades. Losers are left alone on purpose: the
    question is whether the winners are a tail, not whether the risk is."""
    if not trades:
        return trades
    k = max(1, int(len(trades) * frac))
    return sorted(trades)[:-k]


def cell(ctx, sigs, win, pools, trim_frac=0.0):
    pooled, targets = [], {}
    for s in SYMS:
        a, b = win[s]
        tr, _ = run(ctx[s], sigs[s], stop_atr=2.0, rr=1.5,
                    cost_abs=COST.get(s, 0.02), max_hold=36, lo=a, hi=b)
        pooled += tr; targets[s] = len(tr)
    if len(pooled) < 20:
        return None
    strat = trim(pooled, trim_frac) if trim_frac else pooled
    dist = []
    draws = len(next(iter(pools.values())))
    for d in range(draws):
        tr = []
        for s in SYMS:
            tr += pools[s][d][:targets[s]]
        if len(tr) < 20:
            continue
        dist.append(pf(trim(tr, trim_frac) if trim_frac else tr))
    if len(dist) < 10:
        return None
    dist.sort()
    return dict(n=len(strat), pf=pf(strat), c95=dist[int(len(dist) * 0.95)],
                pct=pct_rank(pf(strat), dist),
                med=statistics.median(strat), targets=targets, pooled=pooled)


def build_sig(raw, ctx, nbins, va_pct):
    out = {}
    for s in SYMS:
        _, vah, val = vp.developing(raw[s], nbins, va_pct=va_pct)
        x = dict(ctx[s]); x["dvah"], x["dval"] = vah, val
        out[s] = S.dva_edge_fade(x)
    return out


def main():
    data = sys.argv[1]
    ctx, raw = {}, {}
    for s in SYMS:
        raw[s] = json.load(open(os.path.join(data, f"{s}.json")))
        ctx[s] = enrich(raw[s])
    split = {s: ctx[s]["n"] // 2 for s in SYMS}
    W = {"IS": {s: (0, split[s]) for s in SYMS},
         "OOS": {s: (split[s], ctx[s]["n"]) for s in SYMS}}
    pools = {}
    for tag in ("IS", "OOS"):
        for s in SYMS:
            a, b = W[tag][s]
            pools[(tag, s)] = random_pool(ctx[s], COST.get(s, 0.02), a, b,
                                          seed=abs(hash((tag, s))) % 10**6)
    P = {tag: {s: pools[(tag, s)] for s in SYMS} for tag in ("IS", "OOS")}

    base = build_sig(raw, ctx, 60, 0.70)

    print("== 1. concentration: drop the best 1% of trades ==")
    print(f"{'trim':<8}{'win':<5}{'n':>6}{'PF':>8}{'ctl95':>8}{'ratio':>8}{'pct':>7}{'med':>9}")
    for frac, lab in ((0.0, "none"), (0.01, "top1%")):
        for tag in ("IS", "OOS"):
            r = cell(ctx, base, W[tag], P[tag], frac)
            print(f"{lab:<8}{tag:<5}{r['n']:>6}{r['pf']:>8.3f}{r['c95']:>8.3f}"
                  f"{r['pf']/r['c95']:>8.3f}{r['pct']:>7.1f}{r['med']:>9.4f}")

    print("\n== 2. breadth: the same cell, one instrument at a time ==")
    print(f"{'sym':<6}{'IS n':>6}{'IS PF':>8}{'IS pct':>8}{'OOS n':>7}{'OOS PF':>8}{'OOS pct':>9}")
    both = 0
    for s in SYMS:
        line = [s]
        ok = 0
        for tag in ("IS", "OOS"):
            a, b = W[tag][s]
            tr, _ = run(ctx[s], base[s], stop_atr=2.0, rr=1.5,
                        cost_abs=COST.get(s, 0.02), max_hold=36, lo=a, hi=b)
            dist = sorted(pf(p[:len(tr)]) for p in P[tag][s] if len(p[:len(tr)]) >= 10)
            pc = pct_rank(pf(tr), dist) if dist else float("nan")
            line += [len(tr), pf(tr), pc]
            if pc >= 50: ok += 1
        both += (ok == 2)
        print(f"{line[0]:<6}{line[1]:>6}{line[2]:>8.3f}{line[3]:>8.1f}"
              f"{line[4]:>7}{line[5]:>8.3f}{line[6]:>9.1f}")
    print(f"\nabove the control MEDIAN in both halves: {both}/10 names")

    print("\n== 3. parameters: bins x value-area % ==")
    print(f"{'bins':>5}{'va%':>6}{'IS n':>7}{'IS PF':>8}{'IS pct':>8}"
          f"{'OOS n':>7}{'OOS PF':>8}{'OOS pct':>8}")
    for nb in (30, 45, 60, 90, 120):
        for va in (0.60, 0.70, 0.80):
            sg = build_sig(raw, ctx, nb, va)
            o = []
            for tag in ("IS", "OOS"):
                r = cell(ctx, sg, W[tag], P[tag])
                o += [r["n"], r["pf"], r["pct"]]
            print(f"{nb:>5}{va:>6.2f}{o[0]:>7}{o[1]:>8.3f}{o[2]:>8.1f}"
                  f"{o[3]:>7}{o[4]:>8.3f}{o[5]:>8.1f}", flush=True)


if __name__ == "__main__":
    main()
