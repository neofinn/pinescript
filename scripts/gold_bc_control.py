import json, os, sys, random, statistics, math
sys.path.insert(0, "/home/user/pinescript/scripts")
from break_close import run, arm, stats
from inside_bar_short import execute, price_matched
SC = "/tmp/claude-0/-home-user-pinescript/6b4bb2fe-c45d-5f96-b3e4-1392c689d1fc/scratchpad"
G = os.path.join(SC, "gold2")
L = lambda f: json.load(open(os.path.join(G, f + ".json")))
C = {"GC":1.0,"SI":1.5,"PL":3.0,"GLD":3.0,"IAU":3.0,"GDX":3.0,"GDXJ":4.0}

def ci(rs, B=20000, seed=4):
    rng = random.Random(seed); n = len(rs)
    m = sorted(sum(rng.choice(rs) for _ in range(n))/n for _ in range(B))
    return m[int(.025*B)], m[int(.975*B)]

print("=" * 86)
print("5.  THE BODY-FILTERED CELL vs ITS OWN RANDOM CONTROL  (GC h1)")
print("=" * 86)
h1 = L("GC_h1"); DRAWS = 300
print(f"  {DRAWS} price-matched draws. Same trade count, same stop distances,")
print("  same firing rate; only the alignment with the candle is destroyed.\n")
print(f"  {'body':>5}{'RR':>5}{'side':>7}{'n':>6}{'totR':>9}{'ctl med':>10}{'pct':>6}"
      f"{'avgR':>9}{'95% CI on avg R':>24}")
for body, rr in ((0.0, 2.0), (0.3, 3.0), (0.5, 3.0), (0.7, 3.0)):
    for side in ("short", "long"):
        a = arm(h1, side, True, body)
        kw = dict(rr=rr, stop_at="ref", valid_bars=1, on_close=True,
                  cost_bps=1.0, max_hold=24, side=side)
        tr = execute(h1, a, **kw); s = stats(tr)
        rng = random.Random(31)
        ctl = sorted(sum(x["r"] for x in execute(h1, price_matched(h1, a, rng), **kw))
                     for _ in range(DRAWS))
        pct = 100.0*sum(1 for x in ctl if x < s["tot_r"])/DRAWS
        lo, hi = ci([t["r"] for t in tr])
        print(f"  {body:>5.1f}{rr:>5.1f}{side:>7}{s['n']:>6}{s['tot_r']:>9.1f}"
              f"{ctl[DRAWS//2]:>10.1f}{pct:>6.0f}{s['avg_r']:>9.3f}"
              f"{f'[{lo:+.3f}, {hi:+.3f}]':>24}")

print("\n" + "=" * 86)
print("6.  DOES THE BODY FILTER HOLD ACROSS THE COMPLEX?  (RR 3.0, body >= 0.3)")
print("=" * 86)
print(f"  {'series':<16}{'SHORT n':>9}{'avgR':>9}{'LONG n':>9}{'avgR':>9}"
      f"{'combined':>11}{'  95% CI on combined avg R':>28}")
allr = []
for nm, f, ck in [("GC gold fut","GC_h1","GC"), ("GLD gold ETF","GLD_h1","GLD"),
                  ("IAU gold ETF","IAU_h1","IAU"), ("GDX miners","GDX_h1","GDX"),
                  ("GDXJ jr miners","GDXJ_h1","GDXJ"), ("SI silver","SI_h1","SI"),
                  ("PL platinum","PL_h1","PL")]:
    b = L(f); c = C[ck]
    ts = run(b, "short", rr=3.0, cost_bps=c, body_min=0.3)
    tl = run(b, "long",  rr=3.0, cost_bps=c, body_min=0.3)
    s, l = stats(ts), stats(tl)
    rs = [t["r"] for t in ts+tl]; allr += rs
    lo, hi = ci(rs)
    print(f"  {nm:<16}{s['n']:>9}{s['avg_r']:>9.3f}{l['n']:>9}{l['avg_r']:>9.3f}"
          f"{s['tot_r']+l['tot_r']:>11.1f}{f'[{lo:+.3f}, {hi:+.3f}]':>28}")
lo, hi = ci(allr)
print(f"\n  POOLED gold complex: n={len(allr)}, avg R {statistics.mean(allr):+.3f}, "
      f"95% CI [{lo:+.3f}, {hi:+.3f}]  "
      f"{'EXCLUDES ZERO' if lo*hi>0 else 'spans zero'}")

print("\n" + "=" * 86)
print("7.  GC AND GLD OVER THE SAME WINDOW  (they are the same metal)")
print("=" * 86)
gc, gl = L("GC_h1"), L("GLD_h1")
T0 = max(gc[0]["t"], gl[0]["t"]); T1 = min(gc[-1]["t"], gl[-1]["t"])
import datetime as dt
print(f"  overlap: {dt.datetime.utcfromtimestamp(T0).date()} -> "
      f"{dt.datetime.utcfromtimestamp(T1).date()}\n")
print(f"  {'series':<14}{'body':>6}{'RR':>5}{'SHORT n':>9}{'avgR':>9}"
      f"{'LONG n':>9}{'avgR':>9}{'combined':>11}")
for nm, b, c in (("GC=F", [x for x in gc if T0<=x["t"]<=T1], 1.0),
                 ("GLD",  [x for x in gl if T0<=x["t"]<=T1], 3.0)):
    for body, rr in ((0.0, 2.0), (0.3, 3.0)):
        s = stats(run(b, "short", rr=rr, cost_bps=c, body_min=body))
        l = stats(run(b, "long",  rr=rr, cost_bps=c, body_min=body))
        print(f"  {nm:<14}{body:>6.1f}{rr:>5.1f}{s['n']:>9}{s['avg_r']:>9.3f}"
              f"{l['n']:>9}{l['avg_r']:>9.3f}{s['tot_r']+l['tot_r']:>11.1f}")
