import json, os, sys, glob, random, statistics, collections
sys.path.insert(0, "/home/user/pinescript/scripts")
from pdh_pdl_combos import day_states, run, stats, COMBOS, atr, sessions
SC = "/tmp/claude-0/-home-user-pinescript/6b4bb2fe-c45d-5f96-b3e4-1392c689d1fc/scratchpad"
COST = {**{k:1.0 for k in "ES NQ YM RTY GC SI CL NG EURUSD JPY".split()},
        **{k:2.0 for k in "SPX DJI NDX RUT NIFTY SENSEX BANKNIFTY FTSE DAX N225".split()},
        **{k:3.0 for k in "SPY QQQ GLD TLT AAPL NVDA TSLA JPM".split()},
        **{k:10.0 for k in "BTC ETH".split()}}
D = {os.path.basename(f)[:-5]: json.load(open(f))
     for f in sorted(glob.glob(os.path.join(SC,"h1","*.json")))}

print("="*86)
print("3.  WHY FADING LOSES -- the conditional base rate")
print("="*86)
tot = collections.Counter(); n = 0
for k, v in D.items():
    for d in day_states(v):
        tot[d["state"]] += 1; n += 1
broke = n - tot["NONE"]
both = tot["HL"] + tot["LH"]
print(f"  {n:,} sessions, {broke:,} broke at least one side ({100*broke/n:.1f}%)")
print(f"  of those, both sides were taken in {both:,} ({100*both/broke:.1f}%)\n")
print(f"  So once a level breaks, the opposite level is reached only "
      f"{100*both/broke:.1f}% of the time.")
print(f"  Fading a break is a bet on that {100*both/broke:.1f}% -- and the")
print(f"  fade combinations lose 0.26 to 0.38 R per trade across ~17,000 trades.")

print("\n" + "="*86)
print("4.  IS THE SURVIVING CELL JUST DRIFT?")
print("="*86)
print("  'first PDH break -> LONG' is the only combination that cleared zero.")
print("  Its mirror is 'first PDL break -> SHORT'. If the gap between them is")
print("  the market's upward drift, the pattern itself is worth nothing.\n")
ST = {k: day_states(v) for k, v in D.items()}
AT = {k: atr(v) for k, v in D.items()}
kw = dict(rr=0, stop_mode="atr", atr_mult=3.0)
rows = []
for k, v in D.items():
    lo = stats(run(v, "1st PDH break -> LONG  (follow)", cost_bps=COST[k],
                   states=ST[k], atr_list=AT[k], **kw))
    sh = stats(run(v, "1st PDL break -> SHORT (follow)", cost_bps=COST[k],
                   states=ST[k], atr_list=AT[k], **kw))
    yrs = (v[-1]["t"]-v[0]["t"])/(365.25*86400)
    drift = ((v[-1]["c"]/v[0]["c"])**(1/yrs)-1)*100
    rows.append((k, lo["avg_r"], sh["avg_r"], drift))
rows.sort(key=lambda r: -r[3])
print(f"  {'market':<11}{'PDH->long avgR':>16}{'PDL->short avgR':>17}"
      f"{'sum':>8}{'drift %/yr':>12}")
for k, l, s, d in rows[:8] + rows[-8:]:
    print(f"  {k:<11}{l:>16.3f}{s:>17.3f}{l+s:>8.3f}{d:>12.1f}")
L = [r[1] for r in rows]; S = [r[2] for r in rows]; DR = [r[3] for r in rows]
print(f"\n  mean PDH->long  {statistics.mean(L):+.3f}   positive in "
      f"{sum(1 for x in L if x>0)}/30")
print(f"  mean PDL->short {statistics.mean(S):+.3f}   positive in "
      f"{sum(1 for x in S if x>0)}/30")
print(f"  mean of the two {statistics.mean([l+s for l,s in zip(L,S)])/2:+.3f}"
      f"   <- direction-neutral: what the pattern is worth with drift removed")
mx, my = statistics.mean(DR), statistics.mean([l-s for l,s in zip(L,S)])
cov = sum((d-mx)*((l-s)-my) for d,l,s in zip(DR,L,S))
den = (sum((d-mx)**2 for d in DR)*sum(((l-s)-my)**2 for l,s in zip(L,S)))**.5
print(f"  correlation between (long minus short) and the market's drift: "
      f"{cov/den if den else 0:+.3f}")

print("\n" + "="*86)
print("5.  SHUFFLE CONTROL -- does the PATH matter, or only the range?")
print("="*86)
print("  Bars are reordered WITHIN each session. The session's high, low and")
print("  close are unchanged, so PDH/PDL are identical; only the order in")
print("  which price visits them is destroyed. 30 shuffles.\n")
def shuffle_within(bars, rng):
    out = list(bars)
    for _, idx in sessions(bars):
        vals = [dict(out[i]) for i in idx]
        rng.shuffle(vals)
        for i, v in zip(idx, vals):
            v["t"] = out[i]["t"]; out[i] = v
    return out
rng = random.Random(17)
for name in ("1st PDH break -> LONG  (follow)", "1st PDH break -> SHORT (fade)"):
    tr = []
    for k, v in D.items():
        tr += run(v, name, cost_bps=COST[k], states=ST[k], atr_list=AT[k], **kw)
    real = stats(tr)["avg_r"]
    draws = []
    for _ in range(30):
        acc = []
        for k, v in D.items():
            sv = shuffle_within(v, rng)
            acc += run(sv, name, cost_bps=COST[k], atr_list=atr(sv), **kw)
        draws.append(stats(acc)["avg_r"])
    draws.sort()
    pct = 100*sum(1 for x in draws if x < real)/len(draws)
    print(f"  {name:<34} real {real:>+7.3f}  shuffled med {draws[15]:>+7.3f}"
          f"  best {draws[-1]:>+7.3f}  pct {pct:>3.0f}", flush=True)
