import json, os, sys, glob, statistics, math
sys.path.insert(0, "/home/user/pinescript/scripts")
from break_close import run, arm, stats
from inside_bar_short import execute
SC = "/tmp/claude-0/-home-user-pinescript/6b4bb2fe-c45d-5f96-b3e4-1392c689d1fc/scratchpad"
COST = {**{k: 1.0 for k in "ES NQ YM RTY GC SI CL NG EURUSD JPY".split()},
        **{k: 2.0 for k in "SPX DJI NDX RUT NIFTY SENSEX BANKNIFTY FTSE DAX N225".split()},
        **{k: 3.0 for k in "SPY QQQ GLD TLT AAPL NVDA TSLA JPM".split()},
        **{k: 10.0 for k in "BTC ETH".split()}}
D = {os.path.basename(f)[:-5]: json.load(open(f))
     for f in sorted(glob.glob(os.path.join(SC, "h1", "*.json")))}
print(f"{len(D)} hourly series, {sum(len(v) for v in D.values()):,} bars total\n")

def pooled(side, rr, colour=True, body=0.0, hold=24):
    tr = []
    for k, v in D.items():
        tr += run(v, side=side, rr=rr, cost_bps=COST[k], max_hold=hold,
                  require_colour=colour, body_min=body)
    return stats(tr)

print("=" * 84)
print('1.  THE PATTERN AS STATED, per market, RR 2.0, 24-bar time stop')
print("=" * 84)
print(f"{'market':<11}{'SHORT n':>9}{'avgR':>9}{'PF':>7}{'win%':>7}   "
      f"{'LONG n':>8}{'avgR':>9}{'PF':>7}{'win%':>7}{'drift%/yr':>11}")
rows = []
for k, v in D.items():
    s = stats(run(v, side="short", rr=2.0, cost_bps=COST[k]))
    l = stats(run(v, side="long",  rr=2.0, cost_bps=COST[k]))
    yrs = (v[-1]["t"] - v[0]["t"]) / (365.25*86400)
    dr = ((v[-1]["c"]/v[0]["c"]) ** (1/yrs) - 1) * 100 if yrs > 0 else 0
    rows.append((k, s, l, dr))
    print(f"{k:<11}{s['n']:>9}{s['avg_r']:>9.3f}{s['pf']:>7.2f}{s['win']:>7.1f}   "
          f"{l['n']:>8}{l['avg_r']:>9.3f}{l['pf']:>7.2f}{l['win']:>7.1f}{dr:>11.1f}")
ps, pl = pooled("short", 2.0), pooled("long", 2.0)
print(f"\n{'POOLED':<11}{ps['n']:>9}{ps['avg_r']:>9.3f}{ps['pf']:>7.2f}{ps['win']:>7.1f}   "
      f"{pl['n']:>8}{pl['avg_r']:>9.3f}{pl['pf']:>7.2f}{pl['win']:>7.1f}")
sp = sum(1 for r in rows if r[1]['avg_r'] > 0); lp = sum(1 for r in rows if r[2]['avg_r'] > 0)
print(f"  markets with a positive SHORT: {sp}/{len(rows)}      "
      f"positive LONG: {lp}/{len(rows)}")

print("\n" + "=" * 84)
print('2.  "MAX RETURN BOTH SIDES" -- sweeping the target and the time stop')
print("=" * 84)
print(f"{'RR':>5}{'hold':>6}  |{'SHORT n':>9}{'avgR':>9}{'totR':>9}{'win%':>7}"
      f"  |{'LONG n':>8}{'avgR':>9}{'totR':>9}{'win%':>7}  |{'BOTH totR':>11}")
best = None
grid = []
for rr in (1.0, 1.5, 2.0, 3.0, 5.0, 8.0):
    for hold in (12, 24, 48):
        s = pooled("short", rr, hold=hold); l = pooled("long", rr, hold=hold)
        both = s["tot_r"] + l["tot_r"]
        grid.append((rr, hold, s, l, both))
        if best is None or both > best[4]:
            best = (rr, hold, s, l, both)
        print(f"{rr:>5.1f}{hold:>6}  |{s['n']:>9}{s['avg_r']:>9.3f}{s['tot_r']:>9.1f}"
              f"{s['win']:>7.1f}  |{l['n']:>8}{l['avg_r']:>9.3f}{l['tot_r']:>9.1f}"
              f"{l['win']:>7.1f}  |{both:>11.1f}")
print(f"\n  best of {len(grid)} cells: RR {best[0]}, hold {best[1]} -> "
      f"{best[4]:+.1f}R combined "
      f"(short {best[2]['tot_r']:+.1f}, long {best[3]['tot_r']:+.1f})")
pos = sum(1 for g in grid if g[4] > 0)
print(f"  cells with a positive combined total: {pos}/{len(grid)}")

print("\n" + "=" * 84)
print("3.  DOES THE CANDLE'S COLOUR DO ANY WORK?")
print("=" * 84)
print("  The pattern says the main candle must close RED for a short. The")
print("  ablation keeps the break and drops the colour requirement.\n")
print(f"{'RR':>5}  {'variant':<34}{'SHORT n':>9}{'avgR':>9}  {'LONG n':>8}{'avgR':>9}"
      f"  {'combined totR':>14}")
for rr in (1.5, 2.0, 3.0):
    for colour, lab in ((True, "colour required (the pattern)"),
                        (False, "colour IGNORED (break only)")):
        s = pooled("short", rr, colour=colour); l = pooled("long", rr, colour=colour)
        print(f"{rr:>5.1f}  {lab:<34}{s['n']:>9}{s['avg_r']:>9.3f}  "
              f"{l['n']:>8}{l['avg_r']:>9.3f}  {s['tot_r']+l['tot_r']:>14.1f}")
    print()
print("  and requiring a DECISIVE close (body >= 50% of the candle's range):\n")
for rr in (2.0,):
    for body, lab in ((0.0, "any red/green close"), (0.5, "body >= 50% of range")):
        s = pooled("short", rr, body=body); l = pooled("long", rr, body=body)
        print(f"{rr:>5.1f}  {lab:<34}{s['n']:>9}{s['avg_r']:>9.3f}  "
              f"{l['n']:>8}{l['avg_r']:>9.3f}  {s['tot_r']+l['tot_r']:>14.1f}")
json.dump({"ok":1}, open(os.path.join(SC,"bc_done.json"),"w"))
