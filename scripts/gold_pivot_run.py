import json, os, sys, statistics, random
sys.path.insert(0, "/home/user/pinescript/scripts")
from pivot_ema import run, stats, sessions
SC = "/tmp/claude-0/-home-user-pinescript/6b4bb2fe-c45d-5f96-b3e4-1392c689d1fc/scratchpad"
GC = json.load(open(os.path.join(SC, "h1", "GC.json")))
COST = 0.8   # bps: $0.25 spread + $0.07 commission on gold near $4160
print(f"GC=F hourly, {len(GC)} bars, {len(sessions(GC))} sessions (2024-05 -> 2026-10)")
print(f"cost {COST} bps round turn ~ $0.33 per ounce\n")
print("="*92)
print("1.  THE GRID ON GOLD, with reward:risk swept wide for the maximum")
print("="*92)
print(f"  {'levels':<8}{'mode':<8}{'EMA 9':<10}{'RR':>6}{'n':>6}{'totR':>9}"
      f"{'avgR':>8}{'PF':>7}{'win%':>7}")
rows = []
for g in ("P","1","2","3"):
    for md in ("bounce","break"):
        for em in ("none","aligned","counter"):
            for rr in (1.0, 2.0, 3.0, 5.0, 8.0, 12.0, 20.0):
                tr = run(GC, group=g, mode=md, ema_mode=em, target="rr", rr=rr,
                         cost_bps=COST)
                s = stats(tr)
                if s["n"] < 40: continue
                rows.append(dict(g=g, md=md, em=em, rr=rr, **s))
print(f"  {len(rows)} testable cells")
pos = [r for r in rows if r["avg_r"] > 0]
print(f"  {len(pos)} with positive average R\n")
print("  top 12 by average R:")
print(f"  {'levels':<8}{'mode':<8}{'EMA 9':<10}{'RR':>6}{'n':>6}{'totR':>9}"
      f"{'avgR':>8}{'PF':>7}{'win%':>7}")
for r in sorted(rows, key=lambda x: -x["avg_r"])[:12]:
    print(f"  {('R'+r['g']+'/S'+r['g'] if r['g']!='P' else 'P'):<8}{r['md']:<8}"
          f"{r['em']:<10}{r['rr']:>6.0f}{r['n']:>6}{r['tot_r']:>9.1f}"
          f"{r['avg_r']:>8.3f}{r['pf']:>7.2f}{r['win']:>7.1f}")
print("\n  how average R moves with RR, best EMA/mode at each level group:")
print(f"  {'levels':<8}" + "".join(f"{('RR '+str(int(x))):>9}" for x in (1,2,3,5,8,12,20)))
for g in ("P","1","2","3"):
    line = f"  {('R'+g+'/S'+g if g!='P' else 'P'):<8}"
    for rr in (1.0,2.0,3.0,5.0,8.0,12.0,20.0):
        c = [r["avg_r"] for r in rows if r["g"]==g and r["rr"]==rr]
        line += f"{max(c):>9.3f}" if c else f"{'--':>9}"
    print(line)
json.dump(rows, open(os.path.join(SC,"gold_pv_rows.json"),"w"))
best = max(rows, key=lambda r: r["avg_r"])
print(f"\n  best cell: {best['g']} {best['md']} ema={best['em']} RR {best['rr']:.0f}"
      f"  -> avgR {best['avg_r']:+.3f}, n={best['n']}, PF {best['pf']:.2f}")
print(f"  expected best of {len(rows)} null draws: "
      f"{100.0*len(rows)/(len(rows)+1):.1f}th percentile")
