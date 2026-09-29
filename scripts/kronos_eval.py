"""Score Kronos, forecast skill BEFORE trading.

The order is the point. A trading backtest on a forecast conflates two
questions -- is the forecast informative, and is the trading rule any good --
and when the answer comes back negative you cannot tell which failed. So:

  STEP 1  Does the forecast beat the trivial baselines?
          * directional accuracy against ALWAYS PREDICTING THE MAJORITY
            DIRECTION, not against 50%. On a drifting sample the majority
            class already beats a coin, and a model that merely learned "up"
            would look skilful against the wrong baseline.
          * information coefficient -- the rank correlation between predicted
            and realised return, which is what the forecast would have to
            carry for any rule built on it to work.
          * a bootstrap interval on that IC, because one number from 456
            overlapping-free forecasts is not an estimate.

  STEP 2  Only if step 1 survives: turn it into trades.

If the IC interval covers zero, no threshold, no position sizing and no
confluence rule can rescue it, and running the backtest anyway would just be
generating a number to be fooled by.
"""
from __future__ import annotations
import json, os, random, statistics, sys


def load(d, syms):
    out = {}
    for s in syms:
        p = os.path.join(d, f"{s}.json")
        if os.path.exists(p):
            rows = json.load(open(p))
            if rows:
                out[s] = rows
    return out


def rets(rows):
    """Predicted and realised horizon return, plus the naive persistence one."""
    pr, ar = [], []
    for r in rows:
        last = r["last_close"]
        pr.append((r["p_close"][-1] - last) / last)
        ar.append((r["a_close"][-1] - last) / last)
    return pr, ar


def spearman(a, b):
    def rank(v):
        o = sorted(range(len(v)), key=lambda i: v[i])
        out = [0.0] * len(v)
        i = 0
        while i < len(o):
            j = i
            while j + 1 < len(o) and v[o[j + 1]] == v[o[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1
            for k in range(i, j + 1):
                out[o[k]] = avg
            i = j + 1
        return out
    ra, rb = rank(a), rank(b)
    n = len(a)
    ma, mb = sum(ra) / n, sum(rb) / n
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    den = (sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb)) ** 0.5
    return num / den if den else 0.0


def pearson(a, b):
    n = len(a)
    ma, mb = sum(a) / n, sum(b) / n
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    den = (sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b)) ** 0.5
    return num / den if den else 0.0


def boot_ci(a, b, fn, draws=2000, seed=3):
    rng = random.Random(seed)
    n = len(a)
    out = []
    for _ in range(draws):
        idx = [rng.randrange(n) for _ in range(n)]
        out.append(fn([a[i] for i in idx], [b[i] for i in idx]))
    out.sort()
    return out[int(draws * 0.025)], out[int(draws * 0.975)]


def hit_ci(k, n, z=1.96):
    """Wilson interval for a hit rate. Normal approximation is unreliable at
    the sample sizes a CPU forecast run can afford."""
    if n == 0:
        return 0.0, 0.0
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / d
    return c - h, c + h


def skill(label, rows):
    pr, ar = rets(rows)
    n = len(pr)
    up = sum(1 for x in ar if x > 0) / n
    majority = max(up, 1 - up)
    hit = sum(1 for p, a in zip(pr, ar) if (p > 0) == (a > 0)) / n
    ic = spearman(pr, ar)
    pc = pearson(pr, ar)
    lo, hi = boot_ci(pr, ar, spearman)
    # accuracy of the model's own predicted RANGE, a separate claim from
    # direction and the one a stop would depend on
    cover = sum(1 for r in rows
                if r["a_high"] <= r["p_high"] and r["a_low"] >= r["p_low"]) / n
    return dict(label=label, n=n, up=up * 100, majority=majority * 100,
                hit=hit * 100, ic=ic, pearson=pc, lo=lo, hi=hi,
                cover=cover * 100,
                pred_sd=statistics.pstdev(pr) * 100,
                act_sd=statistics.pstdev(ar) * 100)


SET_A = ["SPY", "QQQ"]
SET_B = ["GOOGL", "IWM"]


def main():
    d = sys.argv[1]
    data = load(d, SET_A + SET_B)
    if not data:
        print("no forecasts yet")
        return
    print(f"{'instrument':<12}{'n':>5}{'up%':>7}{'majority%':>11}{'hit%':>7}"
          f"{'IC':>8}{'IC 95% CI':>20}{'range hit%':>12}")
    allp, alla = [], []
    for s, rows in data.items():
        r = skill(s, rows)
        pr, ar = rets(rows)
        allp += pr
        alla += ar
        ci = f"[{r['lo']:+.3f}, {r['hi']:+.3f}]"
        print(f"{s:<12}{r['n']:>5}{r['up']:>7.1f}{r['majority']:>11.1f}"
              f"{r['hit']:>7.1f}{r['ic']:>8.3f}{ci:>20}{r['cover']:>12.1f}")
    if len(allp) > 20:
        ic = spearman(allp, alla)
        lo, hi = boot_ci(allp, alla, spearman)
        up = sum(1 for x in alla if x > 0) / len(alla)
        hit = sum(1 for p, a in zip(allp, alla) if (p > 0) == (a > 0)) / len(alla)
        print(f"\n{'POOLED':<12}{len(allp):>5}{up * 100:>7.1f}"
              f"{max(up, 1 - up) * 100:>11.1f}{hit * 100:>7.1f}{ic:>8.3f}"
              f"{f'[{lo:+.3f}, {hi:+.3f}]':>20}")
        print(f"\npredicted move sd {statistics.pstdev(allp) * 100:.3f}%  vs  "
              f"realised {statistics.pstdev(alla) * 100:.3f}%")
        k = sum(1 for p, a in zip(allp, alla) if (p > 0) == (a > 0))
        hlo, hhi = hit_ci(k, len(alla))
        maj = max(up, 1 - up)
        print(f"directional hit {hit * 100:.1f}%  95% CI "
              f"[{hlo * 100:.1f}%, {hhi * 100:.1f}%]   "
              f"majority-class baseline {maj * 100:.1f}%")
        beats = hlo > maj
        print(f"  beats the majority baseline: {'YES' if beats else 'NO'} "
              f"(the interval {'excludes' if beats else 'includes'} it)")
        verdict = ("informative" if lo > 0 else
                   "NOT distinguishable from zero")
        print(f"information coefficient is {verdict}")


if __name__ == "__main__":
    main()
