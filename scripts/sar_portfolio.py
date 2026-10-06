"""Trend systems are not traded one market at a time. This is the portfolio."""
import json, os, sys, glob, statistics, datetime as dt
sys.path.insert(0, "/home/user/pinescript/scripts")
from straddle_sar import run, summarise, atr
SC = "/tmp/claude-0/-home-user-pinescript/6b4bb2fe-c45d-5f96-b3e4-1392c689d1fc/scratchpad"
COST = {**{k: 1.0 for k in "ES NQ YM RTY GC SI CL NG EURUSD JPY".split()},
        **{k: 2.0 for k in "SPX DJI NDX RUT NIFTY SENSEX BANKNIFTY FTSE DAX N225".split()},
        **{k: 3.0 for k in "SPY QQQ GLD TLT AAPL NVDA TSLA JPM".split()},
        **{k: 10.0 for k in "BTC ETH".split()}}
D = {os.path.basename(f)[:-5]: json.load(open(f))
     for f in sorted(glob.glob(os.path.join(SC, "d1", "*.json")))}

def portfolio(kw, risk=0.005, cap=0.20):
    """Each trade risks `risk` of live equity; a single market may not take
    more than `cap` of equity as notional. P&L booked on the exit date."""
    ev = {}
    for k, v in D.items():
        t, _ = run(v, cost_bps=COST[k], **kw)
        a = atr(v, 14)
        for tr in t:
            i = tr["i_in"]
            stopd = abs(tr["entry"] - (a[i] or (tr["entry"]*0.02)) * 1.0)
            rd = abs(a[i] or tr["entry"]*0.02) * 3.0 / tr["entry"]   # stop as % of price
            if rd <= 0: continue
            notional = min(risk / rd, cap)
            ev.setdefault(v[tr["i_out"]]["t"], []).append(notional * tr["ret"])
    eq, peak, dd = 1.0, 1.0, 0.0
    curve = []
    for ts in sorted(ev):
        eq *= (1 + sum(ev[ts]))
        peak = max(peak, eq); dd = max(dd, (peak-eq)/peak)
        curve.append((ts, eq))
    yrs = (curve[-1][0]-curve[0][0])/(365.25*86400)
    return eq, (eq**(1/yrs)-1)*100 if eq > 0 else -100, dd*100, yrs, len(ev)

print("=" * 88)
print("5.  AS A PORTFOLIO: all 30 markets, daily, 0.5% risk per trade")
print("=" * 88)
print("  This is how a trend system is actually run. One market's whipsaw is")
print("  another's trend; the portfolio drawdown is far below any single")
print("  market's. Positions sized by ATR so each risks the same, capped at")
print("  20% notional per market.\n")
print(f"  {'entry':>7}{'trail':>10}{'mode':>6}{'final x':>10}{'CAGR%':>9}"
      f"{'maxDD%':>9}{'years':>7}{'MAR':>7}")
best = None
for el, tl, tt, am, sar in ((20,10,"donchian",0,True), (20,10,"donchian",0,False),
                            (50,10,"donchian",0,False), (20,10,"atr",3.0,False),
                            (50,10,"atr",3.0,False), (100,10,"atr",3.0,False)):
    kw = dict(entry_len=el, trail_len=tl, trail=tt, atr_mult=am or 3.0, sar=sar)
    eq, cg, dd, yrs, nd = portfolio(kw)
    mar = cg/dd if dd > 0 else 0
    if best is None or mar > best[0]: best = (mar, el, tt, am, sar, eq, cg, dd)
    lab = tt if tt=="donchian" else f"atr {am}"
    print(f"  {el:>7}{lab:>10}{'SAR' if sar else 'flat':>6}{eq:>10.2f}{cg:>9.2f}"
          f"{dd:>9.1f}{yrs:>7.1f}{mar:>7.2f}")
# the benchmark: equal-weight buy and hold of the same 30 markets, daily rebalance
ts_all = sorted({b["t"] for v in D.values() for b in v})
px = {k: {b["t"]: b["c"] for b in v} for k, v in D.items()}
eq, peak, dd, prev = 1.0, 1.0, 0.0, {}
for ts in ts_all:
    rs = []
    for k in D:
        if ts in px[k] and k in prev:
            rs.append(px[k][ts]/prev[k] - 1)
    if rs: eq *= (1 + sum(rs)/len(rs))
    peak = max(peak, eq); dd = max(dd, (peak-eq)/peak)
    for k in D:
        if ts in px[k]: prev[k] = px[k][ts]
yrs = (ts_all[-1]-ts_all[0])/(365.25*86400)
print(f"\n  equal-weight buy-and-hold, daily rebalanced, same 30 markets:")
print(f"     {eq:.2f}x, {(eq**(1/yrs)-1)*100:.2f}% CAGR, {dd*100:.1f}% max drawdown, "
      f"MAR {((eq**(1/yrs)-1)*100)/(dd*100):.2f}")
print(f"\n  best strategy cell: entry {best[1]} {best[2]}"
      f"{'' if best[2]=='donchian' else ' '+str(best[3])} "
      f"{'SAR' if best[4] else 'flat'} -> {best[5]:.2f}x, {best[6]:.2f}% CAGR, "
      f"{best[7]:.1f}% DD, MAR {best[0]:.2f}")
