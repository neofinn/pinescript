"""Grid + controls for the inside-bar breakdown short."""
from __future__ import annotations
import json, os, random, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from inside_bar_short import aggregate, setups, execute, shifted, price_matched, stats

GRID = [dict(rr=rr, stop_at=s, on_close=oc, valid_bars=vb)
        for rr in (1.5, 2.0, 3.0) for s in ("inside", "ref")
        for oc in (False, True) for vb in (3,)]
SEL = [dict(lookback=lb, size_max=sm) for lb in (20, 50) for sm in (1.0, 0.6)]


def control_r(bars, armed, kw, draws, seed=7):
    rng = random.Random(seed)
    out = []
    for d in range(draws):
        a2 = price_matched(bars, armed, rng)
        out.append(stats(execute(bars, a2, **kw))["tot_r"])
    return sorted(out)


def pct_of(v, dist):
    return 100.0 * sum(1 for x in dist if x < v) / len(dist)


def market(name, bars, cost_bps, draws=200, quiet=False):
    rows = []
    if not quiet:
        print(f"\n=== {name} — {len(bars)} bars ===")
        print(f"{'lb':>4}{'sz':>5}{'RR':>5}{'stop':>7}{'entry':>8}"
              f"{'n':>5}{'totR':>9}{'PF':>7}{'win%':>7}{'ctl med':>9}{'pct':>6}")
    for s in SEL:
        armed = setups(bars, s["lookback"], s["size_max"])
        for g in GRID:
            kw = dict(g, cost_bps=cost_bps)
            st = stats(execute(bars, armed, **kw))
            if st["n"] < 10:
                continue
            ctl = control_r(bars, armed, kw, draws)
            p = pct_of(st["tot_r"], ctl)
            med = ctl[len(ctl) // 2]
            rows.append(dict(market=name, **s, **g, **st, ctl_med=med, pct=p))
            if not quiet:
                print(f"{s['lookback']:>4}{s['size_max']:>5}{g['rr']:>5}"
                      f"{g['stop_at']:>7}{'close' if g['on_close'] else 'break':>8}"
                      f"{st['n']:>5}{st['tot_r']:>9.2f}{st['pf']:>7.2f}"
                      f"{st['win']:>7.1f}{med:>9.2f}{p:>6.0f}")
    return rows


def verdict(rows, label=""):
    if not rows:
        print("  no cell reached the 10-trade floor")
        return
    k = len(rows)
    best = max(r["pct"] for r in rows)
    exp = 100.0 * k / (k + 1)
    above = sum(1 for r in rows if r["pct"] >= 95)
    print(f"\n{label}{k} testable cells")
    print(f"  cells beating the 95th percentile of their own control: {above}/{k}")
    print(f"  expected best of {k} draws under the null: {exp:.1f}th; observed best: {best:.0f}")
    pos = sum(1 for r in rows if r["tot_r"] > 0)
    print(f"  cells with positive total R: {pos}/{k}")
