import json, os, sys, statistics
sys.path.insert(0, "/home/user/pinescript/scripts")
from pivot_ema import run, stats, sessions
from inside_bar_short import aggregate
SC = "/tmp/claude-0/-home-user-pinescript/6b4bb2fe-c45d-5f96-b3e4-1392c689d1fc/scratchpad"
H1 = json.load(open(os.path.join(SC,"h1","GC.json")))
TF = [("m15", json.load(open(os.path.join(SC,"gold2","GC_m15.json"))), "day", 0.8),
      ("m30", json.load(open(os.path.join(SC,"m30","GC.json"))),      "day", 0.8),
      ("h1",  H1,                                                     "day", 0.8),
      ("h4",  aggregate(H1, 240, 60),                                 "day", 0.8),
      ("d1 (weekly pivots)", json.load(open(os.path.join(SC,"d1","GC.json"))), "week", 0.8)]
print("Gold. Pivot levels + EMA, swept over timeframe and EMA length.\n")
for nm, b, per, _ in TF:
    s = sessions(b, per)
    print(f"  {nm:<20}{len(b):>7} bars  {len(s):>5} {'weeks' if per=='week' else 'sessions'}"
          f"  ~{len(b)/max(len(s),1):.1f} bars each")
print("\n" + "="*100)
print("1.  EMA 5 vs EMA 9, every timeframe, every combination")
print("="*100)
rows = []
for nm, b, per, cost in TF:
    for el in (5, 9):
        for g in ("P","1","2","3"):
            for md in ("bounce","break"):
                for em in ("none","aligned","counter"):
                    for rr in (2.0, 5.0, 20.0):
                        tr = run(b, group=g, mode=md, ema_mode=em, ema_len=el,
                                 target="rr", rr=rr, cost_bps=cost, period=per)
                        s = stats(tr)
                        if s["n"] < 40: continue
                        rows.append(dict(tf=nm, el=el, g=g, md=md, em=em, rr=rr, **s))
print(f"  {len(rows)} testable cells across 5 timeframes x 2 EMA lengths\n")
print("  best cell per timeframe and EMA length:")
print(f"  {'timeframe':<20}{'EMA':>4}{'levels':>8}{'mode':>8}{'EMA role':>10}"
      f"{'RR':>5}{'n':>6}{'avgR':>8}{'PF':>7}{'win%':>7}")
for nm, _, _, _ in TF:
    for el in (5, 9):
        sub = [r for r in rows if r["tf"]==nm and r["el"]==el]
        if not sub:
            print(f"  {nm:<20}{el:>4}{'-- no cell reached 40 trades --':>45}"); continue
        r = max(sub, key=lambda x: x["avg_r"])
        print(f"  {nm:<20}{el:>4}{('R'+r['g']+'/S'+r['g'] if r['g']!='P' else 'P'):>8}"
              f"{r['md']:>8}{r['em']:>10}{r['rr']:>5.0f}{r['n']:>6}{r['avg_r']:>8.3f}"
              f"{r['pf']:>7.2f}{r['win']:>7.1f}")

print("\n" + "="*100)
print("2.  DOES EMA LENGTH MATTER?  same cell, 5 against 9")
print("="*100)
print(f"  {'timeframe':<20}{'levels':>8}{'mode':>8}{'EMA role':>10}{'RR':>5}"
      f"{'EMA 5 avgR':>13}{'EMA 9 avgR':>13}{'diff':>9}")
diffs = []
for nm, _, _, _ in TF:
    for g in ("P","1","2"):
        for md in ("break","bounce"):
            for em in ("aligned","counter"):
                for rr in (5.0, 20.0):
                    a = [r for r in rows if r["tf"]==nm and r["el"]==5 and r["g"]==g
                         and r["md"]==md and r["em"]==em and r["rr"]==rr]
                    c = [r for r in rows if r["tf"]==nm and r["el"]==9 and r["g"]==g
                         and r["md"]==md and r["em"]==em and r["rr"]==rr]
                    if not a or not c: continue
                    d = a[0]["avg_r"] - c[0]["avg_r"]; diffs.append(d)
                    if abs(d) > 0.08 or (g=="P" and md=="break" and em=="aligned"):
                        print(f"  {nm:<20}{('R'+g+'/S'+g if g!='P' else 'P'):>8}{md:>8}"
                              f"{em:>10}{rr:>5.0f}{a[0]['avg_r']:>13.3f}"
                              f"{c[0]['avg_r']:>13.3f}{d:>+9.3f}")
print(f"\n  across {len(diffs)} matched pairs: mean (EMA5 - EMA9) = "
      f"{statistics.mean(diffs):+.4f}, EMA5 better in "
      f"{sum(1 for d in diffs if d>0)}/{len(diffs)}")
json.dump(rows, open(os.path.join(SC,"g_mtf_rows.json"),"w"))
