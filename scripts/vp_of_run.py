"""Execution and test for the profile+flow strategies.

The exit is level-based, so the control has to be too. Randomising the entry
while keeping an ATR stop would compare two different machines. Here every
control entry borrows a (stop distance, target distance) pair from the
strategy's OWN realised entries in the same window, so the risk geometry is
identical and the only thing randomised is when to trade and which way.

That isolates the question actually being asked: does the pair of layers pick
better moments and directions than chance, given the same exits.
"""
from __future__ import annotations
import json, os, random, statistics, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vp_of_pure as P
from intraday_lab import COST

SET_A = "SPY QQQ NVDA TSLA AAPL AMD MSFT INTC META AMZN".split()
SET_B = "GOOGL AVGO IWM PLTR MU COIN NFLX MSTR SMCI XLF".split()
DRAWS = 300


def execute(s, plan, cost, lo, hi, tie="stop"):
    """plan[i] = (side, stop, target) or None. Entry at bar i+1's open.

    Geometry is checked at entry, not assumed: a stop on the wrong side of the
    fill, or a target already passed by the opening print, is a trade that
    cannot be taken as described. Those are counted and dropped rather than
    quietly resolved in the strategy's favour.
    """
    bars, ses, n = s["bars"], s["ses"], s["n"]
    hi = n if hi is None else hi
    trades, geo, risks, pos, ambig = [], 0, [], None, 0
    for i in range(lo, min(hi, n - 1)):
        if pos is not None:
            b = bars[i]
            sd = pos["side"]
            hit_s = b["l"] <= pos["stop"] if sd > 0 else b["h"] >= pos["stop"]
            hit_t = b["h"] >= pos["targ"] if sd > 0 else b["l"] <= pos["targ"]
            px = None
            if hit_s and hit_t:
                ambig += 1
                px = pos["stop"] if tie == "stop" else pos["targ"]
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
            sd, stop, targ = plan[i]
            e = bars[i + 1]["o"]
            if stop is None or targ is None:
                geo += 1; continue
            if sd * (e - stop) <= 0 or sd * (targ - e) <= 0:
                geo += 1; continue
            risks.append((abs(e - stop), abs(targ - e)))
            pos = dict(side=sd, entry=e, stop=stop, targ=targ,
                       ses=ses[i + 1])
    return trades, geo, risks, ambig


def control(s, risks, count, cost, lo, hi, seed, draws=DRAWS):
    """Random timing and direction, the strategy's own risk geometry."""
    if count < 5 or not risks:
        return None
    rng = random.Random(seed)
    span = list(range(lo, min(hi, s["n"] - 1)))
    out = []
    for _ in range(draws):
        plan = [None] * s["n"]
        for i in span:
            sd = rng.choice((-1, 1))
            sdist, tdist = risks[rng.randrange(len(risks))]
            c = s["bars"][i]["c"]
            plan[i] = (sd, c - sd * sdist, c + sd * tdist)
        tr, _, _, _ = execute(s, plan, cost, lo, hi)
        rng.shuffle(tr)
        tr = tr[:count]
        if len(tr) < count:
            continue
        w = sum(t for t in tr if t > 0); l = -sum(t for t in tr if t <= 0)
        out.append((w / l) if l else float("inf"))
    if len(out) < draws // 3:
        return None
    out.sort()
    return out


def pf(t):
    w = sum(x for x in t if x > 0); l = -sum(x for x in t if x <= 0)
    return (w / l) if l else float("inf")


def rank(v, dist):
    return 100.0 * sum(1 for x in dist if x < v) / len(dist)


def cell(states, sigs, windows, syms, pools):
    pooled, targets, geo, amb = [], {}, 0, 0
    for s in syms:
        a, b = windows[s]
        tr, g, _, am = execute(states[s], sigs[s], COST.get(s, 0.02), a, b)
        pooled += tr; targets[s] = len(tr); geo += g; amb += am
    if len(pooled) < 20:
        return None
    dist = []
    for d in range(DRAWS):
        t = []
        ok = True
        for s in syms:
            p = pools.get(s)
            if p is None or d >= len(p):
                ok = False; break
            t += p[d][:targets[s]]
        if ok and len(t) >= 20:
            dist.append(pf(t))
    if len(dist) < 20:
        return None
    dist.sort()
    return dict(n=len(pooled), pf=pf(pooled), c95=dist[int(len(dist) * 0.95)],
                pct=rank(pf(pooled), dist), med=statistics.median(pooled),
                geo=geo, amb=amb,
                win=100.0 * sum(1 for t in pooled if t > 0) / len(pooled))


def pools_for(states, sigs, windows, syms, tag):
    out = {}
    for s in syms:
        a, b = windows[s]
        tr, _, risks, _ = execute(states[s], sigs[s], COST.get(s, 0.02), a, b)
        if not tr or not risks:
            continue
        rng = random.Random(abs(hash((tag, s))) % 10 ** 6)
        span = list(range(a, min(b, states[s]["n"]) - 1))
        draws = []
        for _ in range(DRAWS):
            plan = [None] * states[s]["n"]
            for i in span:
                sd = rng.choice((-1, 1))
                sdist, tdist = risks[rng.randrange(len(risks))]
                c = states[s]["bars"][i]["c"]
                plan[i] = (sd, c - sd * sdist, c + sd * tdist)
            t, _, _, _ = execute(states[s], plan, COST.get(s, 0.02), a, b)
            rng.shuffle(t)
            draws.append(t)
        out[s] = draws
    return out


def main():
    dirA, dirB = sys.argv[1], sys.argv[2]
    st = {}
    for d, syms in ((dirA, SET_A), (dirB, SET_B)):
        for s in syms:
            st[s] = P.state(json.load(open(os.path.join(d, f"{s}.json"))))
        print(f"  state built for {os.path.basename(d)}", file=sys.stderr, flush=True)

    spl = {s: st[s]["n"] // 2 for s in SET_A}
    W = {"A-IS": (SET_A, {s: (0, spl[s]) for s in SET_A}),
         "A-OOS": (SET_A, {s: (spl[s], st[s]["n"]) for s in SET_A}),
         "B-ALL": (SET_B, {s: (0, st[s]["n"]) for s in SET_B})}

    print(f"{'signal':<22}{'window':<8}{'n':>6}{'PF':>8}{'win%':>7}{'ctl95':>8}"
          f"{'ratio':>8}{'pct':>7}{'med':>9}{'drop':>6}{'tie':>5}")
    rows = []
    for name, fn in P.REGISTRY.items():
        sigs = {s: [fn(st[s], i) for i in range(st[s]["n"])] for s in st}
        for tag, (syms, wins) in W.items():
            pools = pools_for(st, sigs, wins, syms, tag + name)
            r = cell(st, sigs, wins, syms, pools)
            if r is None:
                print(f"{name:<22}{tag:<8}  too few trades for a matched control")
                continue
            r.update(sig=name, window=tag)
            rows.append(r)
            print(f"{name:<22}{tag:<8}{r['n']:>6}{r['pf']:>8.3f}{r['win']:>7.1f}"
                  f"{r['c95']:>8.3f}{r['pf']/r['c95']:>8.3f}{r['pct']:>7.1f}"
                  f"{r['med']:>9.4f}{r['geo']:>6}{r['amb']:>5}", flush=True)
    json.dump(rows, open(os.path.join(dirA, "vp_of_rows.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
