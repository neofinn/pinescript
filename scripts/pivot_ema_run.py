import json, os, sys, statistics, random
sys.path.insert(0, "/home/user/pinescript/scripts")
from pivot_ema import run, stats, sessions
SC = "/tmp/claude-0/-home-user-pinescript/6b4bb2fe-c45d-5f96-b3e4-1392c689d1fc/scratchpad"
L = lambda d,s: json.load(open(os.path.join(SC,d,s+".json")))
MK = [("NIFTY h1", L("h1","NIFTY"), 2.0), ("NIFTY m15", L("m15","NIFTY"), 2.0),
      ("BANKNIFTY h1", L("h1","BANKNIFTY"), 2.0)]
GR = ["P","1","2","3"]; MODES = ["bounce","break"]; EMAS = ["none","aligned","counter"]
TGT = [("next pivot", dict(target="next")), ("RR 2.0", dict(target="rr", rr=2.0))]

print("="*96)
print("1.  EVERY COMBINATION -- 4 level groups x bounce/break x 3 EMA roles x 2 targets")
print("="*96)
allrows = {}
for mname, bars, cost in MK:
    print(f"\n  === {mname} ({len(sessions(bars))} sessions) ===")
    print(f"  {'levels':<8}{'mode':<8}{'EMA 9':<10}{'target':<12}{'n':>6}"
          f"{'totR':>9}{'avgR':>8}{'PF':>7}{'win%':>7}")
    rows = []
    for g in GR:
        for md in MODES:
            for em in EMAS:
                for tn, tk in TGT:
                    tr = run(bars, group=g, mode=md, ema_mode=em,
                             cost_bps=cost, **tk)
                    s = stats(tr)
                    if s["n"] < 30: continue
                    rows.append(dict(g=g, md=md, em=em, tg=tn, **s))
                    print(f"  {('R'+g+'/S'+g if g!='P' else 'P'):<8}{md:<8}{em:<10}"
                          f"{tn:<12}{s['n']:>6}{s['tot_r']:>9.1f}{s['avg_r']:>8.3f}"
                          f"{s['pf']:>7.2f}{s['win']:>7.1f}")
    allrows[mname] = rows
    pos = sum(1 for r in rows if r["avg_r"] > 0)
    print(f"  -> {len(rows)} cells, {pos} with positive average R")
    if rows:
        b = max(rows, key=lambda r: r["avg_r"])
        print(f"  -> best: {b['g']} {b['md']} ema={b['em']} {b['tg']}  "
              f"avgR {b['avg_r']:+.3f}  n={b['n']}  PF {b['pf']:.2f}")

print("\n" + "="*96)
print("2.  DOES THE BEST NIFTY CELL HOLD UP ON BANKNIFTY?")
print("="*96)
nif = allrows["NIFTY h1"]
top = sorted(nif, key=lambda r: -r["avg_r"])[:6]
bn = {(r["g"],r["md"],r["em"],r["tg"]): r for r in allrows["BANKNIFTY h1"]}
m15 = {(r["g"],r["md"],r["em"],r["tg"]): r for r in allrows["NIFTY m15"]}
print(f"  {'levels':<8}{'mode':<8}{'EMA':<10}{'target':<12}"
      f"{'NIFTY h1':>11}{'BANKNIFTY':>12}{'NIFTY m15':>12}")
for r in top:
    k = (r["g"],r["md"],r["em"],r["tg"])
    b2 = bn.get(k); m2 = m15.get(k)
    print(f"  {('R'+r['g']+'/S'+r['g'] if r['g']!='P' else 'P'):<8}{r['md']:<8}"
          f"{r['em']:<10}{r['tg']:<12}{r['avg_r']:>+11.3f}"
          f"{(b2['avg_r'] if b2 else float('nan')):>+12.3f}"
          f"{(m2['avg_r'] if m2 else float('nan')):>+12.3f}")
k = len(nif)
print(f"\n  expected best of {k} draws under the null: "
      f"{100.0*k/(k+1):.1f}th percentile of its own distribution")
json.dump({m:[dict(r) for r in v] for m,v in allrows.items()},
          open(os.path.join(SC,"pv_rows.json"),"w"))
