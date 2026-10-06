import json, os, sys, glob, statistics, random, datetime as dt
sys.path.insert(0, "/home/user/pinescript/scripts")
from straddle_sar import run, atr, shuffle_bars
SC = "/tmp/claude-0/-home-user-pinescript/6b4bb2fe-c45d-5f96-b3e4-1392c689d1fc/scratchpad"
COST = {**{k: 1.0 for k in "ES NQ YM RTY GC SI CL NG EURUSD JPY".split()},
        **{k: 2.0 for k in "SPX DJI NDX RUT NIFTY SENSEX BANKNIFTY FTSE DAX N225".split()},
        **{k: 3.0 for k in "SPY QQQ GLD TLT AAPL NVDA TSLA JPM".split()},
        **{k: 10.0 for k in "BTC ETH".split()}}
D = {os.path.basename(f)[:-5]: json.load(open(f))
     for f in sorted(glob.glob(os.path.join(SC, "d1", "*.json")))}
KW = dict(entry_len=20, trail_len=10, trail="donchian", sar=False)

def port(data, t0, t1, cmult=1.0, risk=0.005, cap=0.20, kw=None):
    ev = {}
    for k, v in data.items():
        t, _ = run(v, cost_bps=COST[k]*cmult, **(kw or KW))
        a = atr(v, 14)
        for tr in t:
            ts = v[tr["i_out"]]["t"]
            if not (t0 <= ts <= t1): continue
            av = a[tr["i_in"]] or tr["entry"]*0.02
            rd = av*3.0/tr["entry"]
            if rd <= 0: continue
            ev.setdefault(ts, []).append(min(risk/rd, cap)*tr["ret"])
    eq, peak, dd = 1.0, 1.0, 0.0
    for ts in sorted(ev):
        eq *= (1+sum(ev[ts])); peak = max(peak,eq); dd = max(dd,(peak-eq)/peak)
    yrs = (t1-t0)/(365.25*86400)
    return eq, (eq**(1/yrs)-1)*100 if eq > 0 else -100, dd*100

T0 = int(dt.datetime(2017,11,9).timestamp()); T1 = D["SPX"][-1]["t"]
NOC = {k: v for k, v in D.items() if k not in ("BTC","ETH")}
T0L = int(dt.datetime(2008,1,1).timestamp())

print("=" * 80)
print("7.  ROBUSTNESS")
print("=" * 80)
print(f"  {'variant':<46}{'final x':>9}{'CAGR%':>9}{'maxDD%':>9}{'MAR':>7}")
for lab, data, a, b, cm in (
        ("headline (30 mkts, 2017-11 ->, real cost)", D, T0, T1, 1.0),
        ("  without BTC and ETH", NOC, T0, T1, 1.0),
        ("  double the spread", D, T0, T1, 2.0),
        ("  quadruple the spread", D, T0, T1, 4.0),
        ("28 mkts over 2008-2026 (no crypto)", NOC, T0L, T1, 1.0)):
    e, c, d = port(data, a, b, cm)
    print(f"  {lab:<46}{e:>9.2f}{c:>9.2f}{d:>9.1f}{c/d if d else 0:>7.2f}")

print("\n" + "=" * 80)
print("8.  THE SHUFFLE CONTROL, AT PORTFOLIO LEVEL")
print("=" * 80)
print("  Every bar's shape and the return distribution kept; only the ORDER")
print("  destroyed. 40 shuffles of all 30 markets at once.\n")
rng = random.Random(101)
e, c, d = port(D, T0, T1)
draws = []
for i in range(40):
    sd = {k: shuffle_bars(v, rng) for k, v in D.items()}
    _, c2, _ = port(sd, T0, T1)
    draws.append(c2)
draws.sort()
pct = 100.0*sum(1 for x in draws if x < c)/len(draws)
print(f"  real portfolio CAGR          {c:>8.2f}%")
print(f"  shuffled median              {draws[len(draws)//2]:>8.2f}%")
print(f"  shuffled 95th percentile     {draws[int(.95*len(draws))]:>8.2f}%")
print(f"  shuffled best of 40          {draws[-1]:>8.2f}%")
print(f"  percentile of the real result {pct:>7.0f}")
