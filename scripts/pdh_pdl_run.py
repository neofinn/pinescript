import json, os, sys, glob, collections, statistics
sys.path.insert(0, "/home/user/pinescript/scripts")
from pdh_pdl_combos import day_states, run, stats, COMBOS, atr
SC = "/tmp/claude-0/-home-user-pinescript/6b4bb2fe-c45d-5f96-b3e4-1392c689d1fc/scratchpad"
COST = {**{k:1.0 for k in "ES NQ YM RTY GC SI CL NG EURUSD JPY".split()},
        **{k:2.0 for k in "SPX DJI NDX RUT NIFTY SENSEX BANKNIFTY FTSE DAX N225".split()},
        **{k:3.0 for k in "SPY QQQ GLD TLT AAPL NVDA TSLA JPM".split()},
        **{k:10.0 for k in "BTC ETH".split()}}
D = {os.path.basename(f)[:-5]: json.load(open(f))
     for f in sorted(glob.glob(os.path.join(SC,"h1","*.json")))}
ST = {k: day_states(v) for k, v in D.items()}
AT = {k: atr(v) for k, v in D.items()}

print("="*92)
print("1.  BASE RATES -- how a session ends relative to yesterday's range")
print("="*92)
print("  NONE inside day | H only the high broke | L only the low | HL high")
print("  then low (failed breakout) | LH low then high (failed breakdown)\n")
print(f"  {'market':<11}{'sessions':>9}{'NONE':>8}{'H':>8}{'L':>8}{'HL':>8}{'LH':>8}")
tot = collections.Counter(); nses = 0
for k, st in ST.items():
    c = collections.Counter(d["state"] for d in st)
    tot += c; nses += len(st)
    print(f"  {k:<11}{len(st):>9}" + "".join(
        f"{100*c[s]/len(st):>7.1f}%" for s in ("NONE","H","L","HL","LH")))
print(f"\n  {'POOLED':<11}{nses:>9}" + "".join(
    f"{100*tot[s]/nses:>7.1f}%" for s in ("NONE","H","L","HL","LH")))
print(f"\n  one side breaks and holds: {100*(tot['H']+tot['L'])/nses:.1f}%"
      f"   both sides taken: {100*(tot['HL']+tot['LH'])/nses:.1f}%"
      f"   neither: {100*tot['NONE']/nses:.1f}%")

print("\n" + "="*92)
print("2.  ALL EIGHT CAUSAL COMBINATIONS, pooled over 30 markets")
print("="*92)
print("  ATR stops so every combination is comparable. RR 0 = hold to the")
print("  session close.\n")
rows = []
for sm in (1.0, 2.0, 3.0):
    print(f"  --- stop {sm:.0f} x ATR ---")
    print(f"  {'combination':<34}{'RR':>4}{'n':>7}{'totR':>9}{'avgR':>8}"
          f"{'PF':>7}{'win%':>7}")
    for name in COMBOS:
        for rr in (1.0, 2.0, 3.0, 0):
            tr = []
            for k, v in D.items():
                tr += run(v, name, rr=rr, stop_mode="atr", atr_mult=sm,
                          cost_bps=COST[k], states=ST[k], atr_list=AT[k])
            s = stats(tr)
            if s["n"] < 50: continue
            rows.append(dict(combo=name, rr=rr, sm=sm, **s))
            print(f"  {name:<34}{(rr if rr else 'EOD'):>4}{s['n']:>7}"
                  f"{s['tot_r']:>9.1f}{s['avg_r']:>8.3f}{s['pf']:>7.2f}"
                  f"{s['win']:>7.1f}")
    print()
k = len(rows); pos = sum(1 for r in rows if r["avg_r"] > 0)
print(f"  {k} cells, {pos} with positive average R")
b = max(rows, key=lambda r: r["avg_r"])
print(f"  best: {b['combo']}  stop {b['sm']:.0f}xATR  RR {b['rr'] or 'EOD'}  "
      f"-> avgR {b['avg_r']:+.3f}, n={b['n']}, PF {b['pf']:.2f}")
json.dump(rows, open(os.path.join(SC,"pdh_rows.json"),"w"))
