"""The straddle SAR on 1, 3 and 5 minute bars, and the full timeframe curve."""
import json, os, sys, glob, statistics, random
sys.path.insert(0, "/home/user/pinescript/scripts")
from straddle_sar import run, summarise, atr, shuffle_bars
from inside_bar_short import aggregate
SC = "/tmp/claude-0/-home-user-pinescript/6b4bb2fe-c45d-5f96-b3e4-1392c689d1fc/scratchpad"
COST = {**{k: 1.0 for k in "ES NQ GC SI CL EURUSD".split()},
        **{k: 3.0 for k in "SPY QQQ GLD AAPL NVDA TSLA JPM".split()},
        **{k: 10.0 for k in "BTC ETH".split()}}
M1 = {os.path.basename(f)[:-5]: json.load(open(f))
      for f in sorted(glob.glob(os.path.join(SC, "m1", "*.json")))}
M5 = {os.path.basename(f)[:-5]: json.load(open(f))
      for f in sorted(glob.glob(os.path.join(SC, "m5", "*.json")))}
K = sorted(set(M1) & set(M5))
M1 = {k: M1[k] for k in K}
M5 = {k: M5[k] for k in K}
M3 = {k: aggregate(v, 3, 1) for k, v in M1.items()}
H1 = {k: json.load(open(os.path.join(SC, "h1", k + ".json")))
      for k in K if os.path.exists(os.path.join(SC, "h1", k + ".json"))}
H4 = {k: aggregate(v, 240, 60) for k, v in H1.items()}
D1 = {k: json.load(open(os.path.join(SC, "d1", k + ".json")))
      for k in K if os.path.exists(os.path.join(SC, "d1", k + ".json"))}
TF = [("m1", M1), ("m3", M3), ("m5", M5), ("h1", H1), ("h4", H4), ("daily", D1)]
print(f"{len(K)} markets common to all: {' '.join(K)}")
for nm, DD in TF:
    if DD: print(f"  {nm:<6}{len(DD):>3} series, {sum(len(v) for v in DD.values()):>9,} bars")
KW = dict(entry_len=20, trail_len=10, trail="donchian", sar=False)
ASK = dict(entry_len=20, trail_len=10, trail="donchian", sar=True)

def sweep(DD, kw, cmult=1.0):
    fin, cg, dd, ns, bt, drag = [], [], [], 0, 0, []
    for k, v in DD.items():
        t, i = run(v, cost_bps=COST[k]*cmult, **kw)
        s = summarise(t, v, i)
        if not s or s["n"] < 5: continue
        fin.append(s["final"]); cg.append(s["cagr"]); dd.append(s["dd"])
        ns += s["n"]; bt += s["cagr"] > s["hold_cagr"]
        a = atr(v, 14)
        for tr in t[:400]:
            av = a[tr["i_in"]]
            if av: drag.append((COST[k]*cmult/10_000.0*tr["entry"]*2)/av)
    if not fin: return None
    return (statistics.mean(fin), statistics.mean(cg), statistics.mean(dd),
            ns, bt, len(fin), statistics.mean(drag) if drag else 0.0)

print("\n" + "=" * 100)
print("1.  THE FULL TIMEFRAME CURVE -- m1 through daily, same system, same markets")
print("=" * 100)
print(f"{'tf':<7}{'mode':<6}{'trades':>9}{'trades/mkt/yr':>15}{'mean x':>9}"
      f"{'mean CAGR%':>12}{'mean DD%':>10}{'cost as % of 1 ATR':>21}{'beat hold':>11}")
for nm, DD in TF:
    if not DD: continue
    yrs = statistics.mean((v[-1]["t"]-v[0]["t"])/(365.25*86400) for v in DD.values())
    for lab, kw in (("SAR", ASK), ("flat", KW)):
        r = sweep(DD, kw)
        if not r: continue
        f, c, d, ns, bt, m, dg = r
        print(f"{nm:<7}{lab:<6}{ns:>9}{ns/m/yrs:>15,.0f}{f:>9.3f}{c:>12.2f}"
              f"{d:>10.1f}{100*dg:>20.1f}%{bt:>8}/{m}")
    hc = statistics.mean(((v[-1]["c"]/v[0]["c"])**(1/((v[-1]["t"]-v[0]["t"])/(365.25*86400)))-1)*100
                         for v in DD.values())
    print(f"{'':<13}{'buy-and-hold mean CAGR':<30}{hc:>8.2f}%\n")

print("=" * 100)
print("2.  COST SENSITIVITY ON THE FAST BARS -- is there signal under the spread?")
print("=" * 100)
print(f"{'tf':<7}{'cost x':>8}{'trades':>9}{'mean x':>9}{'mean CAGR%':>12}{'beat hold':>11}")
for nm, DD in (("m1", M1), ("m3", M3), ("m5", M5)):
    for cm in (0.0, 0.25, 0.5, 1.0):
        r = sweep(DD, KW, cm)
        if not r: continue
        f, c, d, ns, bt, m, dg = r
        print(f"{nm:<7}{cm:>8.2f}{ns:>9}{f:>9.3f}{c:>12.2f}{bt:>8}/{m}")
    print()
