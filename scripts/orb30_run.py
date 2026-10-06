import json, os, sys, glob, statistics, collections
sys.path.insert(0, "/home/user/pinescript/scripts")
from orb30 import opening_ranges, run, stats, SESSION
SC = "/tmp/claude-0/-home-user-pinescript/6b4bb2fe-c45d-5f96-b3e4-1392c689d1fc/scratchpad"
COST = {**{k:1.0 for k in "NQ ES YM RTY GC CL".split()},
        **{k:2.0 for k in "NDX IXIC SPX DAX FTSE NIFTY BANKNIFTY".split()},
        **{k:3.0 for k in "QQQ SPY AAPL NVDA TSLA MSFT AMZN".split()}}
D = {os.path.basename(f)[:-5]: json.load(open(f))
     for f in sorted(glob.glob(os.path.join(SC,"m30","*.json")))}
NAS = ["NQ","QQQ","NDX","IXIC"]

print("="*94)
print("1.  THE NASDAQ, as asked: first M30 candle, break of its high or low, 1:2 RR")
print("="*94)
print("  Stop at the other side of the opening range, so risk = the range.")
print("  Unresolved trades exit at the 16:00 ET close.\n")
print(f"  {'market':<8}{'sessions':>9}{'n':>5}{'totR':>8}{'avgR':>8}{'PF':>7}"
      f"{'win%':>7}   {'target':>7}{'stop':>7}{'close':>7}   {'OR width':>9}")
for s in NAS:
    b = D[s]; tr = run(b, s, rr=2.0, cost_bps=COST[s])
    st = stats(tr)
    tg = sum(1 for t in tr if t["r"] > 1.9); sp = sum(1 for t in tr if t["r"] < -0.9)
    to = st["n"] - tg - sp
    w = statistics.median(t["rng_bps"] for t in tr) if tr else 0
    print(f"  {s:<8}{len(opening_ranges(b,s)):>9}{st['n']:>5}{st['tot_r']:>8.1f}"
          f"{st['avg_r']:>8.3f}{st['pf']:>7.2f}{st['win']:>7.1f}   "
          f"{100*tg/max(st['n'],1):>6.0f}%{100*sp/max(st['n'],1):>6.0f}%"
          f"{100*to/max(st['n'],1):>6.0f}%   {w:>8.0f}bp")
tr = []
for s in NAS: tr += run(D[s], s, rr=2.0, cost_bps=COST[s])
st = stats(tr)
tg = sum(1 for t in tr if t["r"] > 1.9); sp = sum(1 for t in tr if t["r"] < -0.9)
print(f"\n  {'POOLED':<8}{'':>9}{st['n']:>5}{st['tot_r']:>8.1f}{st['avg_r']:>8.3f}"
      f"{st['pf']:>7.2f}{st['win']:>7.1f}   {100*tg/st['n']:>6.0f}%"
      f"{100*sp/st['n']:>6.0f}%{100*(st['n']-tg-sp)/st['n']:>6.0f}%")
print(f"\n  Of the trades that RESOLVED, {100*tg/max(tg+sp,1):.1f}% hit the 2R target.")
print(f"  A driftless random walk with a stop at r and a target at 2r resolves")
print(f"  in the target's favour 33.3% of the time.")
print(f"  The 'win%' column counts any positive R, including the many trades")
print(f"  that merely drift a little before the close -- which is why it reads")
print(f"  far higher than the share that actually reached the target.")

print("\n" + "="*94)
print("2.  REWARD:RISK SWEEP, and halving the stop")
print("="*94)
print(f"  {'stop':<12}{'RR':>5}{'n':>6}{'totR':>9}{'avgR':>8}{'PF':>7}{'win%':>7}"
      f"{'target hit%':>13}")
for sm in ("range","half"):
    for rr in (1.0, 1.5, 2.0, 3.0):
        tr = []
        for s in NAS: tr += run(D[s], s, rr=rr, cost_bps=COST[s], stop_mode=sm)
        st = stats(tr)
        tg = sum(1 for t in tr if t["r"] > rr-0.1)
        sp = sum(1 for t in tr if t["r"] < -0.9)
        print(f"  {('full range' if sm=='range' else 'half range'):<12}{rr:>5.1f}"
              f"{st['n']:>6}{st['tot_r']:>9.1f}{st['avg_r']:>8.3f}{st['pf']:>7.2f}"
              f"{st['win']:>7.1f}{100*tg/max(tg+sp,1):>12.1f}%")
    print()

print("="*94)
print("3.  IS IT THE NASDAQ, OR THE SETUP?  same rule, 20 markets, 1:2 RR")
print("="*94)
print(f"  {'market':<11}{'n':>5}{'avgR':>8}{'PF':>7}{'win%':>7}{'target%':>9}"
      f"{'OR width':>10}")
rows = []
for s in sorted(D):
    tr = run(D[s], s, rr=2.0, cost_bps=COST[s])
    st = stats(tr)
    if st["n"] < 20: continue
    tg = sum(1 for t in tr if t["r"] > 1.9); sp = sum(1 for t in tr if t["r"] < -0.9)
    w = statistics.median(t["rng_bps"] for t in tr)
    rows.append((s, st, 100*tg/max(tg+sp,1), w))
    print(f"  {s:<11}{st['n']:>5}{st['avg_r']:>8.3f}{st['pf']:>7.2f}"
          f"{st['win']:>7.1f}{100*tg/max(tg+sp,1):>8.1f}%{w:>9.0f}bp")
A = [r[1]["avg_r"] for r in rows]
print(f"\n  {len(rows)} markets: mean avg-R {statistics.mean(A):+.3f}, "
      f"positive in {sum(1 for x in A if x>0)}/{len(rows)}")
allt = []
for s in sorted(D):
    allt += run(D[s], s, rr=2.0, cost_bps=COST[s])
st = stats(allt)
tg = sum(1 for t in allt if t["r"] > 1.9); sp = sum(1 for t in allt if t["r"] < -0.9)
print(f"  pooled: n={st['n']}, avgR {st['avg_r']:+.3f}, PF {st['pf']:.2f}, "
      f"target hit {100*tg/max(tg+sp,1):.1f}% of resolved")
