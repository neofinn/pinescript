import json, os, sys, glob, random, statistics
sys.path.insert(0, "/home/user/pinescript/scripts")
from straddle_sar import run, summarise, shuffle_bars
SC = "/tmp/claude-0/-home-user-pinescript/6b4bb2fe-c45d-5f96-b3e4-1392c689d1fc/scratchpad"
COST = {**{k: 1.0 for k in "ES NQ YM RTY GC SI CL NG EURUSD JPY".split()},
        **{k: 2.0 for k in "SPX DJI NDX RUT NIFTY SENSEX BANKNIFTY FTSE DAX N225".split()},
        **{k: 3.0 for k in "SPY QQQ GLD TLT AAPL NVDA TSLA JPM".split()},
        **{k: 10.0 for k in "BTC ETH".split()}}
D = {os.path.basename(f)[:-5]: json.load(open(f))
     for f in sorted(glob.glob(os.path.join(SC, "h1", "*.json")))}
BEST = dict(entry_len=50, trail_len=10, trail="atr", atr_mult=3.0, sar=False)
ASK  = dict(entry_len=20, trail_len=10, trail="donchian", sar=True)

print("=" * 86)
print("2.  IS IT COSTS, OR IS THERE NO SIGNAL?")
print("=" * 86)
print("  Same system, the real spread scaled down to zero. If a free version")
print("  works, the idea is sound and the execution is too expensive. If the")
print("  free version is also flat, there is nothing to make cheaper.\n")
print(f"  {'config':<28}{'cost x':>8}{'trades':>8}{'mean x':>9}{'mean CAGR%':>12}"
      f"{'beat hold':>11}")
for lab, kw in (("as asked (SAR, donchian)", ASK), ("best grid cell", BEST)):
    for mult in (0.0, 0.25, 0.5, 1.0, 2.0):
        fin, cg, ns, bt = [], [], 0, 0
        for k, v in D.items():
            t, i = run(v, cost_bps=COST[k]*mult, **kw)
            s = summarise(t, v, i)
            if s:
                fin.append(s["final"]); cg.append(s["cagr"]); ns += s["n"]
                bt += s["cagr"] > s["hold_cagr"]
        print(f"  {lab:<28}{mult:>8.2f}{ns:>8}{statistics.mean(fin):>9.3f}"
              f"{statistics.mean(cg):>12.2f}{bt:>8}/{len(fin)}")
    print()

print("=" * 86)
print("3.  DOES IT BEAT SHUFFLED DATA?  (the real control for a trend system)")
print("=" * 86)
print("  Each bar's shape and the return distribution are kept; only the ORDER")
print("  is destroyed. A trend follower's entire thesis is that order matters.")
print("  50 shuffles per market.\n")
rng = random.Random(77)
print(f"  {'config':<28}{'real mean CAGR%':>17}{'shuffled med':>14}"
      f"{'shuffled 95th':>15}{'pct':>6}")
for lab, kw in (("as asked (SAR, donchian)", ASK), ("best grid cell", BEST)):
    real = []
    for k, v in D.items():
        t, i = run(v, cost_bps=COST[k], **kw)
        s = summarise(t, v, i)
        if s: real.append(s["cagr"])
    rm = statistics.mean(real)
    draws = []
    for d in range(50):
        cg = []
        for k, v in D.items():
            sb = shuffle_bars(v, rng)
            t, i = run(sb, cost_bps=COST[k], **kw)
            s = summarise(t, sb, i)
            if s: cg.append(s["cagr"])
        draws.append(statistics.mean(cg))
    draws.sort()
    pct = 100.0*sum(1 for x in draws if x < rm)/len(draws)
    print(f"  {lab:<28}{rm:>17.2f}{draws[len(draws)//2]:>14.2f}"
          f"{draws[int(.95*len(draws))]:>15.2f}{pct:>6.0f}", flush=True)
