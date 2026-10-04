import json, os, sys, glob, random, statistics
sys.path.insert(0, "/home/user/pinescript/scripts")
from break_close import arm, stats
from inside_bar_short import execute, price_matched
SC = "/tmp/claude-0/-home-user-pinescript/6b4bb2fe-c45d-5f96-b3e4-1392c689d1fc/scratchpad"
COST = {**{k: 1.0 for k in "ES NQ YM RTY GC SI CL NG EURUSD JPY".split()},
        **{k: 2.0 for k in "SPX DJI NDX RUT NIFTY SENSEX BANKNIFTY FTSE DAX N225".split()},
        **{k: 3.0 for k in "SPY QQQ GLD TLT AAPL NVDA TSLA JPM".split()},
        **{k: 10.0 for k in "BTC ETH".split()}}
D = {os.path.basename(f)[:-5]: json.load(open(f))
     for f in sorted(glob.glob(os.path.join(SC, "h1", "*.json")))}
DRAWS = 200
CELLS = [("short", 2.0, 24), ("long", 2.0, 24),
         ("short", 8.0, 48), ("long", 8.0, 48), ("long", 5.0, 48)]
print(f"Price-matched random control, {DRAWS} draws, pooled over {len(D)} markets.")
print("The control keeps each setup's shape -- trigger and stop as fractions of")
print("price -- and places it at a random bar. Same trade count, same stop")
print("distances, same firing rate. Only the alignment with the candle is gone.\n")
print(f"{'side':<7}{'RR':>5}{'hold':>6}{'n':>8}{'totR':>11}{'avgR':>9}"
      f"{'ctl med totR':>14}{'ctl avgR':>10}{'pct':>6}")
for side, rr, hold in CELLS:
    pre = {k: arm(v, side) for k, v in D.items()}
    kw = lambda k: dict(rr=rr, stop_at="ref", valid_bars=1, on_close=True,
                        cost_bps=COST[k], max_hold=hold, side=side)
    tr = []
    for k, v in D.items():
        tr += execute(v, pre[k], **kw(k))
    s = stats(tr)
    rng = random.Random(13)
    ctl = []
    for _ in range(DRAWS):
        tot = 0.0; cnt = 0
        for k, v in D.items():
            a2 = price_matched(v, pre[k], rng)
            t2 = execute(v, a2, **kw(k))
            tot += sum(x["r"] for x in t2); cnt += len(t2)
        ctl.append((tot, cnt))
    tots = sorted(c[0] for c in ctl)
    avgs = sorted(c[0]/max(c[1],1) for c in ctl)
    pct = 100.0*sum(1 for x in tots if x < s["tot_r"])/len(tots)
    print(f"{side:<7}{rr:>5.1f}{hold:>6}{s['n']:>8}{s['tot_r']:>11.1f}"
          f"{s['avg_r']:>9.3f}{tots[len(tots)//2]:>14.1f}"
          f"{avgs[len(avgs)//2]:>10.3f}{pct:>6.0f}", flush=True)
