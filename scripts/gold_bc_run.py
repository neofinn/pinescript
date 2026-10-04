import json, os, sys, glob, statistics, random, math
sys.path.insert(0, "/home/user/pinescript/scripts")
from break_close import run, arm, stats
from inside_bar_short import execute, price_matched, aggregate
SC = "/tmp/claude-0/-home-user-pinescript/6b4bb2fe-c45d-5f96-b3e4-1392c689d1fc/scratchpad"
G = os.path.join(SC, "gold2")
L = lambda f: json.load(open(os.path.join(G, f + ".json")))
C = {"GC": 1.0, "SI": 1.5, "PL": 3.0, "GLD": 3.0, "IAU": 3.0, "GDX": 3.0, "GDXJ": 4.0}

print("=" * 88)
print("1.  GOLD FUTURES, HOURLY -- the pattern as stated, both sides")
print("=" * 88)
h1 = L("GC_h1")
print(f"  GC=F h1: {len(h1):,} bars, 2024-05-12 -> 2026-10-02, 1 bp round turn\n")
print(f"  {'RR':>5}{'hold':>6}  |{'SHORT n':>9}{'avgR':>9}{'totR':>9}{'PF':>7}{'win%':>7}"
      f"  |{'LONG n':>8}{'avgR':>9}{'totR':>9}{'PF':>7}{'win%':>7}  |{'both':>8}")
best = None; cells = []
for rr in (1.0, 1.5, 2.0, 3.0, 5.0, 8.0):
    for hold in (12, 24, 48):
        s = stats(run(h1, "short", rr=rr, cost_bps=1.0, max_hold=hold))
        l = stats(run(h1, "long",  rr=rr, cost_bps=1.0, max_hold=hold))
        tot = s["tot_r"] + l["tot_r"]; cells.append((rr, hold, tot))
        if best is None or tot > best[2]: best = (rr, hold, tot)
        print(f"  {rr:>5.1f}{hold:>6}  |{s['n']:>9}{s['avg_r']:>9.3f}{s['tot_r']:>9.1f}"
              f"{s['pf']:>7.2f}{s['win']:>7.1f}  |{l['n']:>8}{l['avg_r']:>9.3f}"
              f"{l['tot_r']:>9.1f}{l['pf']:>7.2f}{l['win']:>7.1f}  |{tot:>8.1f}")
print(f"\n  best of {len(cells)}: RR {best[0]}, hold {best[1]} -> {best[2]:+.1f}R combined")
print(f"  cells with a positive combined total: {sum(1 for c in cells if c[2]>0)}/{len(cells)}")

print("\n" + "=" * 88)
print("2.  THE BODY FILTER -- the one knob that helped across 30 markets")
print("=" * 88)
print("  'closes red' by a tick is not the same as closing red with conviction.\n")
print(f"  {'body >=':>9}{'RR':>5}  |{'SHORT n':>9}{'avgR':>9}  |{'LONG n':>8}{'avgR':>9}"
      f"  |{'combined totR':>15}")
for body in (0.0, 0.3, 0.5, 0.7):
    for rr in (2.0, 3.0):
        s = stats(run(h1, "short", rr=rr, cost_bps=1.0, body_min=body))
        l = stats(run(h1, "long",  rr=rr, cost_bps=1.0, body_min=body))
        print(f"  {body:>9.1f}{rr:>5.1f}  |{s['n']:>9}{s['avg_r']:>9.3f}  "
              f"|{l['n']:>8}{l['avg_r']:>9.3f}  |{s['tot_r']+l['tot_r']:>15.1f}")

print("\n" + "=" * 88)
print("3.  EVERY GOLD TIMEFRAME")
print("=" * 88)
TFS = [("GC 15m", L("GC_m15"), 1.0), ("GC 30m", L("GC_m30"), 1.0),
       ("GC h1", h1, 1.0), ("GC h4", aggregate(h1, 240, 60), 1.0),
       ("GC daily 20y", L("GC_d"), 1.0)]
print(f"  {'series':<14}{'bars':>8}  |{'SHORT n':>9}{'avgR':>9}{'win%':>7}"
      f"  |{'LONG n':>8}{'avgR':>9}{'win%':>7}  |{'combined totR':>15}")
for nm, b, c in TFS:
    s = stats(run(b, "short", rr=2.0, cost_bps=c))
    l = stats(run(b, "long",  rr=2.0, cost_bps=c))
    print(f"  {nm:<14}{len(b):>8}  |{s['n']:>9}{s['avg_r']:>9.3f}{s['win']:>7.1f}  "
          f"|{l['n']:>8}{l['avg_r']:>9.3f}{l['win']:>7.1f}  |{s['tot_r']+l['tot_r']:>15.1f}")

print("\n" + "=" * 88)
print("4.  THE WHOLE GOLD COMPLEX AT h1")
print("=" * 88)
CX = [("GC gold fut", "GC_h1","GC"), ("GLD gold ETF","GLD_h1","GLD"),
      ("IAU gold ETF","IAU_h1","IAU"), ("GDX miners","GDX_h1","GDX"),
      ("GDXJ jr miners","GDXJ_h1","GDXJ"), ("SI silver","SI_h1","SI"),
      ("PL platinum","PL_h1","PL")]
print(f"  {'series':<16}  |{'SHORT n':>9}{'avgR':>9}{'PF':>7}  |{'LONG n':>8}{'avgR':>9}"
      f"{'PF':>7}  |{'combined':>10}{'drift%/yr':>11}")
sp = lp = 0
for nm, f, ck in CX:
    b = L(f); c = C[ck]
    s = stats(run(b, "short", rr=2.0, cost_bps=c))
    l = stats(run(b, "long",  rr=2.0, cost_bps=c))
    yrs = (b[-1]["t"]-b[0]["t"])/(365.25*86400)
    dr = ((b[-1]["c"]/b[0]["c"])**(1/yrs)-1)*100
    sp += s["avg_r"] > 0; lp += l["avg_r"] > 0
    print(f"  {nm:<16}  |{s['n']:>9}{s['avg_r']:>9.3f}{s['pf']:>7.2f}  "
          f"|{l['n']:>8}{l['avg_r']:>9.3f}{l['pf']:>7.2f}  "
          f"|{s['tot_r']+l['tot_r']:>10.1f}{dr:>11.1f}")
print(f"\n  positive SHORT: {sp}/{len(CX)}    positive LONG: {lp}/{len(CX)}")
