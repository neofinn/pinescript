"""The ratio z-score finds SPX bottoms. Does the DOW have anything to do with it?

A local bottom is defined with the future: SPX is the lowest close within +/-k
bars. Any signal that fires after a sharp DROP will score well on that, because
a sharp drop mechanically puts you near the low of the surrounding window. So
the ratio's apparent skill has to be compared against the simplest possible
"SPX just fell" signal, which uses no Dow data at all.
"""
import json, os, random, statistics, sys
sys.path.insert(0, "/home/user/pinescript/scripts")
from index_overlap import is_bottom, fwd
SC = "/tmp/claude-0/-home-user-pinescript/6b4bb2fe-c45d-5f96-b3e4-1392c689d1fc/scratchpad"
I = os.path.join(SC, "idx")
L = lambda f: json.load(open(os.path.join(I, f + ".json")))
def align(sfx):
    a, b = L("SPX_" + sfx), L("DJI_" + sfx)
    m = {x["t"]: x["c"] for x in b}
    p = [(x["c"], m[x["t"]]) for x in a if x["t"] in m]
    return [x[0] for x in p], [x[1] for x in p]

def zs(xs, w):
    n = len(xs); z = [None]*n
    for i in range(w, n):
        seg = xs[i-w:i]
        mu = statistics.mean(seg); sd = statistics.pstdev(seg)
        z[i] = (xs[i]-mu)/sd if sd else 0.0
    return z

rng = random.Random(21)
def score(s, idx, k, n):
    cr = [i for i in idx if k <= i < n-k]
    if len(cr) < 15: return None
    pool = list(range(k, n-k))
    hit = sum(1 for i in cr if is_bottom(s, i, k))/len(cr)
    fm = statistics.mean(fwd(s, i, k) for i in cr)
    bh, bf = [], []
    for _ in range(400):
        smp = rng.sample(pool, len(cr))
        bh.append(sum(1 for i in smp if is_bottom(s, i, k))/len(cr))
        bf.append(statistics.mean(fwd(s, i, k) for i in smp))
    bh.sort(); bf.sort()
    return (len(cr), hit, bh[200], 100*sum(1 for x in bh if x < hit)/400,
            fm, bf[200], 100*sum(1 for x in bf if x < fm)/400)

print("Signals compared at z < -2, k = 30. 400 random-time draws each.\n")
print(f"  {'timeframe':<11}{'w':>5}  {'signal':<22}{'n':>6}{'bottom%':>9}"
      f"{'random%':>9}{'pct':>6}{'fwd bps':>10}{'rand':>9}{'pct':>6}")
for lab, sfx in [("1-minute","m1"), ("5-minute","m5"), ("1-hour","h1"), ("daily","d")]:
    s, d = align(sfx); n = len(s)
    for w in (60, 240):
        if w >= n//3: continue
        ratio = [x/y for x, y in zip(s, d)]
        zr, zsx, zdj = zs(ratio, w), zs(s, w), zs(d, w)
        for name, z in [("SPX/DJI ratio z<-2", zr),
                        ("SPX alone z<-2  (no Dow)", zsx),
                        ("DJI alone z<-2", zdj)]:
            idx = [i for i in range(w, n) if z[i] is not None and z[i] < -2]
            r = score(s, idx, 30, n)
            if not r: continue
            print(f"  {lab:<11}{w:>5}  {name:<22}{r[0]:>6}{100*r[1]:>8.1f}%"
                  f"{100*r[2]:>8.1f}%{r[3]:>6.0f}{r[4]:>10.2f}{r[5]:>9.2f}{r[6]:>6.0f}")
        print()
