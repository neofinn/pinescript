import json, os, random, statistics, sys
sys.path.insert(0, "/home/user/pinescript/scripts")
from index_overlap import crossings, is_bottom, fwd
SC = "/tmp/claude-0/-home-user-pinescript/6b4bb2fe-c45d-5f96-b3e4-1392c689d1fc/scratchpad"
I = os.path.join(SC, "idx")
L = lambda f: json.load(open(os.path.join(I, f + ".json")))
def align(sfx):
    a, b = L("SPX_" + sfx), L("DJI_" + sfx)
    m = {x["t"]: x["c"] for x in b}
    p = [(x["t"], x["c"], m[x["t"]]) for x in a if x["t"] in m]
    return [x[0] for x in p], [x[1] for x in p], [x[2] for x in p]

print("=" * 76)
print("3.  CROSSING RATE vs CHART RESOLUTION  (what 1-second would do)")
print("=" * 76)
print("  Crossings of the two auto-scaled lines, at a fixed 240-bar window,")
print("  expressed per hour of market time.\n")
print(f"  {'bars':<10}{'bar secs':>10}{'bars':>8}{'crossings':>11}{'per hour':>10}{'one every':>14}")
for lab, sfx, secs in [("1-minute","m1",60), ("5-minute","m5",300),
                       ("1-hour","h1",3600), ("daily","d",23400)]:
    t, s, d = align(sfx)
    c = crossings(s, d, 240)
    hours = len(s) * secs / 3600.0
    per_h = len(c) / hours
    gap = len(s) / max(len(c), 1) * secs
    unit = f"{gap:,.0f} sec" if gap < 3600 else f"{gap/3600:,.1f} hours"
    print(f"  {lab:<10}{secs:>10,}{len(s):>8,}{len(c):>11,}{per_h:>10.2f}{unit:>14}")
print("\n  The finer the bar, the more often they cross -- the rate is a property")
print("  of the sampling, not of the market. Extrapolating the 1m->5m->1h slope,")
print("  a 1-second chart crosses roughly every 10-20 SECONDS of market time.")
print("  Something that happens every 15 seconds is adjacent to every bottom in")
print("  the session. It is also adjacent to every top, and to everything else.")

print("\n" + "=" * 76)
print("4.  THE STEELMAN: the SPX/DJI RATIO, which has no scaling freedom")
print("=" * 76)
print("  The ratio is the one version of this idea that a chart cannot distort.")
print("  Tested as a bottom-caller the same way: 400 random-time draws.\n")
rng = random.Random(9)
print(f"  {'timeframe':<11}{'signal':<26}{'n':>6}{'bottom%':>9}{'random%':>9}{'pct':>6}"
      f"{'fwd bps':>9}{'rand':>8}{'pct':>6}")
for lab, sfx in [("1-minute","m1"), ("5-minute","m5"), ("1-hour","h1"), ("daily","d")]:
    t, s, d = align(sfx)
    ratio = [x / y for x, y in zip(s, d)]
    n = len(ratio)
    for w in (60, 240):
        if w >= n // 3: continue
        ma, z = [None]*n, [None]*n
        for i in range(w, n):
            seg = ratio[i-w:i]
            mu = statistics.mean(seg); sd = statistics.pstdev(seg)
            ma[i] = mu
            z[i] = (ratio[i]-mu)/sd if sd else 0.0
        sigs = {
            f"ratio crosses its {w}MA": [i for i in range(w+1, n)
                if ma[i] and ma[i-1] and (ratio[i-1]-ma[i-1])*(ratio[i]-ma[i]) < 0],
            f"ratio z<-2 ({w}b)": [i for i in range(w, n) if z[i] is not None and z[i] < -2],
            f"ratio z>+2 ({w}b)": [i for i in range(w, n) if z[i] is not None and z[i] > 2],
        }
        for name, idx in sigs.items():
            for k in (30,):
                cr = [i for i in idx if k <= i < n-k]
                if len(cr) < 15: continue
                pool = list(range(k, n-k))
                hit = sum(1 for i in cr if is_bottom(s, i, k))/len(cr)
                fm = statistics.mean(fwd(s, i, k) for i in cr)
                bh, bf = [], []
                for _ in range(400):
                    smp = rng.sample(pool, len(cr))
                    bh.append(sum(1 for i in smp if is_bottom(s, i, k))/len(cr))
                    bf.append(statistics.mean(fwd(s, i, k) for i in smp))
                bh.sort(); bf.sort()
                ph = 100*sum(1 for x in bh if x < hit)/400
                pf = 100*sum(1 for x in bf if x < fm)/400
                print(f"  {lab:<11}{name:<26}{len(cr):>6}{100*hit:>8.1f}%"
                      f"{100*bh[200]:>8.1f}%{ph:>6.0f}{fm:>9.2f}{bf[200]:>8.2f}{pf:>6.0f}")
