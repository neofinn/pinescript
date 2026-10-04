"""Gold straddle at 0.01 lot. Wider initial stop, trailing swept."""
import json, os, sys, statistics, random, itertools, datetime as dt
sys.path.insert(0, "/home/user/pinescript/scripts")
from straddle_sar import run, shuffle_bars
from inside_bar_short import aggregate
SC = "/tmp/claude-0/-home-user-pinescript/6b4bb2fe-c45d-5f96-b3e4-1392c689d1fc/scratchpad"
OZ = 1.0                      # 0.01 lot XAUUSD = 1 troy ounce; $1 move = $1
SPREAD, COMM = 0.25, 0.07     # dollars per ounce, round turn
SWAP_NIGHT = -0.10            # dollars per night per 0.01 lot, long gold
BARS_PER_DAY = {"h1": 24, "h4": 6, "d1": 1}

H1 = json.load(open(os.path.join(SC, "h1", "GC.json")))
D1 = json.load(open(os.path.join(SC, "d1", "GC.json")))
H4 = aggregate(H1, 240, 60)
TF = {"h1": H1, "h4": H4, "d1": D1}
for k, v in TF.items():
    print(f"  {k:<4}{len(v):>7,} bars  "
          f"{dt.datetime.utcfromtimestamp(v[0]['t']).date()} -> "
          f"{dt.datetime.utcfromtimestamp(v[-1]['t']).date()}")

def sim(bars, tf, spread=SPREAD, comm=COMM, swap=SWAP_NIGHT, **kw):
    cost_leg = spread/2 + comm/2
    t, _ = run(bars, cost_bps=0.0, cost_abs=cost_leg,
               swap_per_bar=swap/BARS_PER_DAY[tf], **kw)
    if not t: return None
    pnl = [x["pnl"]*OZ for x in t]
    eq, peak, dd = 0.0, 0.0, 0.0
    for p in pnl:
        eq += p; peak = max(peak, eq); dd = max(dd, peak-eq)
    w = sum(p for p in pnl if p > 0); l = -sum(p for p in pnl if p <= 0)
    yrs = (bars[-1]["t"]-bars[0]["t"])/(365.25*86400)
    return dict(n=len(t), net=eq, dd=dd, pf=(w/l if l else 99.9),
                win=100*sum(1 for p in pnl if p>0)/len(pnl),
                per=eq/len(t), yrs=yrs, per_yr=eq/yrs,
                gross=sum(x["gross"] for x in t)*OZ,
                fees=sum(x["fees"] for x in t)*OZ,
                held=statistics.mean(x["bars_held"] for x in t))

def hold(bars):
    return (bars[-1]["c"]-bars[0]["c"])*OZ

print(f"\n  0.01 lot XAUUSD = 1 troy ounce. $1 move = $1.")
print(f"  spread ${SPREAD:.2f} + commission ${COMM:.2f} round turn, "
      f"swap ${SWAP_NIGHT:.2f}/night")
for k, v in TF.items():
    print(f"  buy & hold 0.01 lot on {k}: ${hold(v):+,.0f}")

print("\n" + "="*104)
print("1.  WIDER INITIAL STOP ORDER x TRAILING -- the two knobs, swept together")
print("="*104)
rows = []
for tf in ("h1", "h4", "d1"):
    b = TF[tf]
    print(f"\n  --- {tf} ---  (buy & hold 0.01 lot = ${hold(b):+,.0f})")
    print(f"  {'pad':>5}{'trail':>12}{'delay':>7}{'mode':>6}{'n':>6}{'net $':>10}"
          f"{'$/trade':>9}{'maxDD $':>10}{'PF':>7}{'win%':>7}{'held':>7}")
    for pad in (0.0, 0.5, 1.0, 2.0, 3.0):
        for tname, tkw in (("donch 10", dict(trail="donchian", trail_len=10)),
                           ("donch 20", dict(trail="donchian", trail_len=20)),
                           ("atr 2", dict(trail="atr", atr_mult=2.0)),
                           ("atr 3", dict(trail="atr", atr_mult=3.0)),
                           ("atr 5", dict(trail="atr", atr_mult=5.0)),
                           ("atr 8", dict(trail="atr", atr_mult=8.0))):
            for delay in (0.0, 2.0):
                for sar in (False,):
                    r = sim(b, tf, entry_len=20, entry_pad=pad,
                            trail_delay=delay, sar=sar, **tkw)
                    if not r or r["n"] < 15: continue
                    rows.append(dict(tf=tf, pad=pad, trail=tname, delay=delay,
                                     sar=sar, **r))
                    print(f"  {pad:>5.1f}{tname:>12}{delay:>7.1f}"
                          f"{'SAR' if sar else 'flat':>6}{r['n']:>6}"
                          f"{r['net']:>10,.0f}{r['per']:>9.2f}{r['dd']:>10,.0f}"
                          f"{r['pf']:>7.2f}{r['win']:>7.1f}{r['held']:>7.0f}")
json.dump(rows, open(os.path.join(SC, "gold_lot_rows.json"), "w"))
k = len(rows); pos = sum(1 for r in rows if r["net"] > 0)
print(f"\n  {k} cells tested, {pos} with positive net P&L")
for tf in ("h1","h4","d1"):
    sub = [r for r in rows if r["tf"]==tf]
    if not sub: continue
    bh = hold(TF[tf])
    bt = sum(1 for r in sub if r["net"] > bh)
    b = max(sub, key=lambda r: r["net"])
    print(f"  {tf}: best ${b['net']:,.0f} (pad {b['pad']}, {b['trail']}, "
          f"delay {b['delay']}, DD ${b['dd']:,.0f}) | beat hold (${bh:+,.0f}): {bt}/{len(sub)}")
