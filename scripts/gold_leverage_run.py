"""$500 at 1:1000 on gold. What the leverage allows, and what survives."""
import json, os, sys, statistics, random
sys.path.insert(0, "/home/user/pinescript/scripts")
from pivot_ema import run, stats
SC = "/tmp/claude-0/-home-user-pinescript/6b4bb2fe-c45d-5f96-b3e4-1392c689d1fc/scratchpad"
GC = json.load(open(os.path.join(SC,"h1","GC.json")))
CAP, LEV, COST = 500.0, 1000, 0.8
MIN_LOT, LOT_OZ = 0.01, 100.0          # broker minimum, ounces per standard lot
STOPOUT = 0.50                          # liquidation at 50% margin level
TR = run(GC, group="P", mode="break", ema_mode="aligned", target="rr", rr=20.0,
         cost_bps=COST)
print(f"{len(TR)} trades. Median stop distance "
      f"${statistics.median(t['risk_px'] for t in TR):.2f} per ounce "
      f"({statistics.median(t['risk_px']/t['entry']*100 for t in TR):.2f}% of price).\n")

def simulate(risk_frac, cap=CAP, cap_lots=None, rng_order=None):
    eq, peak, dd = cap, cap, 0.0
    order = list(TR)
    if rng_order is not None:
        order = order[:]; rng_order.shuffle(order)
    for t in order:
        if eq <= 0: return 0.0, 1.0, True, "blown"
        want_oz = (eq * risk_frac) / t["risk_px"]
        max_oz = (eq * LEV) / t["entry"]            # the leverage ceiling
        oz = min(want_oz, max_oz)
        if cap_lots: oz = min(oz, cap_lots * LOT_OZ)
        lots = max(MIN_LOT, round(oz / LOT_OZ, 2))  # broker lot granularity
        oz = lots * LOT_OZ
        margin = oz * t["entry"] / LEV
        if margin > eq: return 0.0, 1.0, True, "margin"
        pnl = t["r"] * t["risk_px"] * oz
        # a losing trade's excursion must not breach the stop-out level first
        if pnl < 0 and (eq + pnl) < STOPOUT * margin:
            return 0.0, 1.0, True, "stopout"
        eq += pnl
        peak = max(peak, eq); dd = max(dd, (peak-eq)/peak)
    return eq, dd, eq <= 0, "survived"

print("="*92)
print("1.  WHAT EACH RISK SETTING DOES TO $500")
print("="*92)
print(f"  Risking X% of live equity per trade, sized by the actual stop")
print(f"  distance, capped by 1:1000 leverage, broker minimum 0.01 lots,")
print(f"  liquidation at a {STOPOUT:.0%} margin level.\n")
print(f"  {'risk/trade':>11}{'final $':>12}{'maxDD%':>9}{'outcome':>12}"
      f"{'median lots':>13}{'median $/trade':>16}")
for rf in (0.005, 0.01, 0.02, 0.05, 0.10, 0.20, 0.50, 1.00):
    eq, dd, blown, why = simulate(rf)
    # what size that implies at the median stop
    med_oz = (CAP*rf)/statistics.median(t["risk_px"] for t in TR)
    lots = max(MIN_LOT, round(med_oz/LOT_OZ, 2))
    print(f"  {100*rf:>10.1f}%{eq:>12,.0f}{100*dd:>9.1f}{why:>12}"
          f"{lots:>13.2f}{lots*LOT_OZ*statistics.median(t['risk_px'] for t in TR):>15,.0f}")
print("\n  Note the lot granularity: 0.01 lots is the smallest a retail broker")
print("  accepts, and on a $500 account at the median $22 stop that one")
print("  minimum lot already risks $22 -- about 4.4% of the account. Risk")
print("  settings below that are not reachable; the rows above 1% are the")
print("  only ones the broker can actually express.")

print("\n" + "="*92)
print("2.  RUIN -- the order of the same trades decides whether $500 survives")
print("="*92)
print("  Same 317 trades, same statistics, only the sequence reshuffled.")
print("  1,000 orderings per risk setting.\n")
print(f"  {'risk/trade':>11}{'ruin rate':>12}{'median final $':>17}"
      f"{'5th pct $':>12}{'95th pct $':>13}")
rng = random.Random(7)
for rf in (0.01, 0.02, 0.05, 0.10, 0.20, 0.50):
    outs, ruin = [], 0
    for _ in range(1000):
        eq, dd, blown, why = simulate(rf, rng_order=rng)
        outs.append(eq); ruin += (why != "survived")
    outs.sort()
    print(f"  {100*rf:>10.1f}%{100*ruin/1000:>11.1f}%{outs[500]:>17,.0f}"
          f"{outs[50]:>12,.0f}{outs[950]:>13,.0f}")
