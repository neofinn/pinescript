"""The profile+flow setups and the confluence rules, on Indian indices.

Underlying first, options second. Trading the index means futures or options,
so cost here is one futures spread crossed each way, in index points, per
index -- BANKNIFTY's book is several points wide where NIFTY's is a quarter
point, and charging them the same would flatter the wider one.

The volume is synthetic (see india_volume.py) and agrees with the index ETF's
real volume to within 0.05% of price on the POC. That is two witnesses
agreeing, not a calibration against truth, and it is about a tenth of a typical
session's range -- so these levels are indicative, not precise.
"""
from __future__ import annotations
import json, os, statistics, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import india_volume as IV
import vp_of_pure as P
from vp_confluence import combine, MODES
from vp_of_run import pf, rank, DRAWS
from vp_options import signals_for

# one futures spread each way, index points
COST = {"NIFTY": 0.50, "BANKNIFTY": 4.00, "SENSEX": 4.00}
IDX = ("NIFTY", "BANKNIFTY", "SENSEX")


def execute(st, plan, cost, lo, hi):
    """Entry next open, profile stop, target at TWICE the stop distance.

    Every plan gets the same 1:2 here, including the ones that carry a profile
    target of their own. Mixing target rules across plans would mean the
    comparison measured the exit as much as the signal, and 1:2 is the frame
    the rest of this thread uses.
    """
    bars, ses, n = st["bars"], st["ses"], st["n"]
    hi = n if hi is None else hi
    trades, risks, pos, geo, amb = [], [], None, 0, 0
    for i in range(lo, min(hi, n - 1)):
        b = bars[i]
        if pos is not None:
            sd = pos["side"]
            hit_s = b["l"] <= pos["stop"] if sd > 0 else b["h"] >= pos["stop"]
            hit_t = b["h"] >= pos["targ"] if sd > 0 else b["l"] <= pos["targ"]
            px = None
            if hit_s and hit_t:
                amb += 1
                px = pos["stop"]
            elif hit_s:
                px = pos["stop"]
            elif hit_t:
                px = pos["targ"]
            elif ses[i] != pos["ses"]:
                px = b["c"]
            if px is not None:
                trades.append(sd * (px - pos["entry"]) - cost)
                pos = None
        if pos is None and plan[i] is not None:
            sd, stop = plan[i][0], plan[i][1]
            e = bars[i + 1]["o"]
            if stop is None or sd * (e - stop) <= 0:
                geo += 1
                continue
            r = abs(e - stop)
            risks.append(r)
            pos = dict(side=sd, entry=e, stop=stop, targ=e + sd * 2.0 * r,
                       ses=ses[i + 1])
    return trades, geo, risks, amb


def pools_for(st, plans, win, syms, cost, tag, draws=DRAWS):
    """Random timing and direction, the plan's own stop distances."""
    import random
    out = {}
    for s in syms:
        a, b = win[s]
        tr, _, risks, _ = execute(st[s], plans[s], cost[s], a, b)
        if not tr or not risks:
            continue
        rng = random.Random(abs(hash((tag, s))) % 10 ** 6)
        span = list(range(a, min(b, st[s]["n"]) - 1))
        draw = []
        for _ in range(draws):
            rp = [None] * st[s]["n"]
            for i in span:
                sd = rng.choice((-1, 1))
                c = st[s]["bars"][i]["c"]
                rp[i] = (sd, c - sd * risks[rng.randrange(len(risks))], None)
            t, _, _, _ = execute(st[s], rp, cost[s], a, b)
            rng.shuffle(t)
            draw.append(t)
        out[s] = draw
    return out


def cell(st, plans, win, syms, pools, label, cost):
    pooled, targets, geo = [], {}, 0
    for s in syms:
        a, b = win[s]
        tr, g, _, _ = execute(st[s], plans[s], cost[s], a, b)
        pooled += tr
        targets[s] = len(tr)
        geo += g
    if len(pooled) < 20:
        print(f"{label:<24}  too few trades")
        return None
    dist = []
    for d in range(DRAWS):
        t = []
        for s in syms:
            p = pools.get(s)
            if p is None or d >= len(p):
                t = []
                break
            t += p[d][:targets[s]]
        if len(t) >= 20:
            dist.append(pf(t))
    if len(dist) < 20:
        print(f"{label:<24}  no matched control")
        return None
    dist.sort()
    c95 = dist[int(len(dist) * 0.95)]
    v = pf(pooled)
    wins = 100.0 * sum(1 for x in pooled if x > 0) / len(pooled)
    print(f"{label:<24}{len(pooled):>6}{v:>8.3f}{wins:>7.1f}{c95:>8.3f}"
          f"{v / c95:>8.3f}{rank(v, dist):>7.1f}"
          f"{statistics.median(pooled):>9.2f}{sum(pooled):>10.0f}")
    return dict(label=label, n=len(pooled), pf=v, c95=c95,
                pct=rank(v, dist), net=sum(pooled))


def main():
    d = sys.argv[1]
    st = {}
    for ix in IDX:
        bars = IV.with_volume(d, ix)
        st[ix] = P.state(bars)
        print(f"  {ix:<10}{st[ix]['n']:>6} bars, "
              f"{len(set(x['t'] // 86400 for x in bars)):>3} sessions",
              file=sys.stderr)
    names = ["dva_edge_fade"] + list(P.REGISTRY)
    sigs = {ix: {nm: signals_for(st[ix], nm) for nm in names} for ix in IDX}

    spl = {ix: st[ix]["n"] // 2 for ix in IDX}
    windows = {
        "IS (first half)": {ix: (0, spl[ix]) for ix in IDX},
        "OOS (second half)": {ix: (spl[ix], st[ix]["n"]) for ix in IDX},
    }
    for wlab, win in windows.items():
        print(f"\n===== {wlab} — NIFTY + BANKNIFTY + SENSEX =====")
        print(f"{'plan':<24}{'n':>6}{'PF':>8}{'win%':>7}{'ctl95':>8}"
              f"{'ratio':>8}{'pct':>7}{'med pt':>9}{'net pt':>10}")
        pools = {}
        for nm in names:
            plans = {ix: sigs[ix][nm] for ix in IDX}
            for ix in IDX:
                pools[ix] = pools_for(st, plans, win, [ix], COST, wlab + nm)[ix]
            cell(st, plans, win, IDX, pools, nm, COST)
        for m in MODES:
            plans = {ix: combine(sigs[ix], st[ix]["n"], m) for ix in IDX}
            for ix in IDX:
                pools[ix] = pools_for(st, plans, win, [ix], COST, wlab + m)[ix]
            cell(st, plans, win, IDX, pools, m, COST)

    print("\n===== per index, full window, best two plans =====")
    full = {ix: (0, st[ix]["n"]) for ix in IDX}
    print(f"{'plan':<24}{'index':<11}{'n':>6}{'PF':>8}{'pct':>7}{'net pt':>10}")
    for nm in ("dva_edge_fade", "naked_poc_flow", "conf2_distinct"):
        plans = ({ix: sigs[ix][nm] for ix in IDX} if nm in names
                 else {ix: combine(sigs[ix], st[ix]["n"], nm) for ix in IDX})
        for ix in IDX:
            po = pools_for(st, plans, full, [ix], COST, "full" + nm)
            tr, _, _, _ = execute(st[ix], plans[ix], COST[ix], 0, st[ix]["n"])
            dist = sorted(pf(p[:len(tr)]) for p in po[ix]
                          if len(p[:len(tr)]) >= 10)
            print(f"{nm:<24}{ix:<11}{len(tr):>6}{pf(tr):>8.3f}"
                  f"{(rank(pf(tr), dist) if dist else float('nan')):>7.1f}"
                  f"{sum(tr):>10.0f}")


if __name__ == "__main__":
    main()
