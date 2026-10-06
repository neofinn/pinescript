"""Volume profile + orderflow, tested the same way everything else here was.

Protocol, fixed before the run:
  * ten highest dollar-volume US names, 5m bars, the last ~60 sessions
  * IS = first half, OOS = second half, spent once
  * stop 2.0 ATR, target 1.5R, session exit, max hold 36 bars (3 hours)
    -- 2.0 ATR because at 0.75 ATR a third of exits had stop and target inside
    the same bar, where OHLC cannot say which came first
  * cost = one spread crossed each way, in CASH, per instrument
  * every cell scored against a random control MATCHED TO ITS OWN TRADE COUNT,
    because a filter that cuts 300 trades to 30 buys variance, and variance
    alone produces high profit factors
"""
from __future__ import annotations
import json, os, random, statistics, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import volume_profile as vp
import vp_signals as S
from intraday_lab import context, run, score, COST
from orderflow import classify

SYMS = "SPY QQQ NVDA TSLA AAPL AMD MSFT INTC META AMZN".split()
NBINS = 60
DRAWS = 300


def enrich(bars):
    """Base context plus every profile level, all causal."""
    x = context(bars)
    x["ppoc"], x["pvah"], x["pval"] = vp.prior_levels(bars, NBINS)
    x["dpoc"], x["dvah"], x["dval"] = vp.developing(bars, NBINS)
    x["npoc"] = vp.naked_pocs(bars, NBINS)
    # prior-session low-volume nodes, carried across the day like the VA edges
    n = len(bars)
    plvn = [[] for _ in range(n)]
    prev = None
    for idxs in vp.sessions_of(bars):
        if prev is not None:
            for i in idxs:
                plvn[i] = prev
        p = vp.build([bars[j] for j in idxs], NBINS)
        prev = p.get("lvn", [])
    x["plvn"] = plvn
    # bar-level tick rule. Coarse -- it tracks the 1-minute aggregate at
    # r = 0.68, not 1.0 -- so it is a proxy and is labelled as one.
    imb = [None] * n
    for i, b in enumerate(bars):
        bu, se = classify(b)
        v = (b["v"] or 0)
        imb[i] = (bu - se) / v if v > 0 else None
    x["imb"] = imb
    return x


def random_pool(x, cost, lo, hi, seed, draws=DRAWS):
    """Cached random trade lists for one instrument-window.

    Built ONCE and reused by every cell, which is not just a speed trick: it
    means each cell is compared against the same null, so two cells differing
    by one filter differ by the filter and not by control noise.

    Entries are armed on EVERY bar and the executor takes whichever it can fit;
    that is the densest a random trader can be under this execution, and it
    sets the ceiling on the trade count any matched control can reach.
    """
    rng = random.Random(seed)
    span = range(lo, min(hi, x["n"] - 1))
    pools = []
    for _ in range(draws):
        sig = [0] * x["n"]
        for i in span:
            sig[i] = rng.choice((-1, 1))
        tr, _ = run(x, sig, stop_atr=2.0, rr=1.5, cost_abs=cost,
                    max_hold=36, lo=lo, hi=hi)
        rng.shuffle(tr)          # truncation must not favour early sessions
        pools.append(tr)
    return pools


def pf(trades):
    w = sum(t for t in trades if t > 0)
    l = -sum(t for t in trades if t <= 0)
    return (w / l) if l else float("inf")


def pooled_control(pools, targets):
    """Pooled random PF distribution at the cell's exact per-name counts.

    Returns (p50, p95, pct_of_target_reached). The last one is the honest
    caveat: when a signal fires more often than non-overlapping execution
    allows, no random control can match its count, and the comparison is
    against the densest random achievable, which FLATTERS the signal.
    """
    draws = len(next(iter(pools.values())))
    out, reach = [], []
    for d in range(draws):
        tr, want, got = [], 0, 0
        for s, want_n in targets.items():
            part = pools[s][d][:want_n]
            tr += part; want += want_n; got += len(part)
        if len(tr) < 5:
            continue
        out.append(pf(tr)); reach.append(got / want if want else 1.0)
    if len(out) < 10:
        return None
    out.sort()
    fin = [v for v in out if v != float("inf")]
    return (statistics.median(fin) if fin else float("inf"),
            out[int(len(out) * 0.95)],
            statistics.median(reach), out)


def pct_rank(value, dist):
    return 100.0 * sum(1 for v in dist if v < value) / len(dist)


def main():
    data = sys.argv[1]
    ctx = {}
    for s in SYMS:
        bars = json.load(open(os.path.join(data, f"{s}.json")))
        ctx[s] = enrich(bars)
        print(f"  built {s} {len(bars)} bars", file=sys.stderr, flush=True)

    split = {s: ctx[s]["n"] // 2 for s in SYMS}
    win = {"IS": {s: (0, split[s]) for s in SYMS},
           "OOS": {s: (split[s], ctx[s]["n"]) for s in SYMS}}

    pools = {}
    for tag in ("IS", "OOS"):
        for s in SYMS:
            a, b = win[tag][s]
            pools[(tag, s)] = random_pool(ctx[s], COST.get(s, 0.02), a, b,
                                          seed=abs(hash((tag, s))) % 10**6)
        print(f"  control pool {tag} built", file=sys.stderr, flush=True)

    rows = []
    for name, fn in S.REGISTRY.items():
        base = {s: fn(ctx[s]) for s in SYMS}
        for gname, gate in S.GATES.items():
            for tag in ("IS", "OOS"):
                pooled, targets = [], {}
                for s in SYMS:
                    x = ctx[s]; a, b = win[tag][s]
                    sig = base[s] if gname == "none" else gate(base[s], x["imb"])
                    tr, _ = run(x, sig, stop_atr=2.0, rr=1.5,
                                cost_abs=COST.get(s, 0.02), max_hold=36,
                                lo=a, hi=b)
                    pooled += tr; targets[s] = len(tr)
                if len(pooled) < 10:
                    continue
                sc = score(pooled)
                c = pooled_control({s: pools[(tag, s)] for s in SYMS}, targets)
                if c is None:
                    continue
                c50, c95, reach, dist = c
                rows.append(dict(sig=name, gate=gname, win=tag, n=sc["n"],
                                 pf=sc["pf"], hit=sc["win"], net=sc["net"],
                                 med=sc["med"], c50=c50, c95=c95,
                                 reach=reach, pct=pct_rank(sc["pf"], dist),
                                 ratio=sc["pf"] / c95 if c95 else None))
                r = rows[-1]
                flag = "" if reach > 0.98 else f"  <-- control only reached {reach:.0%} of n"
                print(f"{name:<18}{gname:<8}{tag:<4}{sc['n']:>6}"
                      f"{sc['pf']:>8.3f}{sc['win']:>7.1f}{c50:>8.3f}"
                      f"{c95:>8.3f}{r['ratio']:>8.3f}{r['pct']:>7.1f}"
                      f"{sc['med']:>9.4f}{flag}", flush=True)
    json.dump(rows, open(os.path.join(data, "vp_rows.json"), "w"), indent=1)


if __name__ == "__main__":
    print(f"{'signal':<18}{'gate':<8}{'win':<4}{'n':>6}{'PF':>8}{'win%':>7}"
          f"{'ctl50':>8}{'ctl95':>8}{'ratio':>8}{'pct':>7}{'med':>9}")
    main()
