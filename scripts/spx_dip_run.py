import json, os, random, statistics, sys, datetime as dt
sys.path.insert(0, "/home/user/pinescript/scripts")
from spx_dip import run, summarise, zscore, equity, buyhold
SC = "/tmp/claude-0/-home-user-pinescript/6b4bb2fe-c45d-5f96-b3e4-1392c689d1fc/scratchpad"
bars = json.load(open(os.path.join(SC, "idx", "SPX_d.json")))
print(f"S&P 500 daily, {len(bars)} bars, "
      f"{dt.datetime.utcfromtimestamp(bars[0]['t']).date()} -> "
      f"{dt.datetime.utcfromtimestamp(bars[-1]['t']).date()}")
print("Price index: no dividends, in the strategy or in buy-and-hold.")
print("Signal at the close, entry at the NEXT open, one position at a time, "
      "2 bps each way.\n")

print("=" * 94)
print("1.  THE GRID  -- and the only benchmark that matters is the last column")
print("=" * 94)
print(f"{'w':>4}{'thr':>6}{'hold':>6}{'n':>5}{'avg%':>8}{'win%':>7}{'total%':>10}"
      f"{'CAGR%':>8}{'maxDD%':>8}{'inMkt%':>8}{'Sharpe':>8}   {'vs buy-and-hold':>16}")
rows = []
for w in (60, 120, 240):
    for thr in (-1.5, -2.0, -2.5):
        for hold in (10, 30, 60):
            tr = run(bars, w=w, thr=thr, hold=hold, cost_bps=2.0)
            s = summarise(tr, bars)
            if not s or s["n"] < 15:
                continue
            rows.append(dict(w=w, thr=thr, hold=hold, **s))
            beat = s["cagr"] - s["bh_cagr"]
            print(f"{w:>4}{thr:>6.1f}{hold:>6}{s['n']:>5}{100*s['avg']:>8.2f}"
                  f"{s['win']:>7.1f}{100*s['tot']:>10.1f}{100*s['cagr']:>8.2f}"
                  f"{100*s['dd']:>8.1f}{100*s['inmkt']:>8.1f}{s['sharpe']:>8.2f}"
                  f"   {100*beat:>+7.2f} pts/yr")
b = rows[0]
print(f"\n  buy-and-hold over the same span: {100*b['bh']:>.1f}% total, "
      f"{100*b['bh_cagr']:>.2f}% CAGR, {100*b['bh_dd']:.1f}% max drawdown, "
      f"100% in market")
beats = sum(1 for r in rows if r["cagr"] > r["bh_cagr"])
print(f"  cells whose CAGR beats buy-and-hold: {beats}/{len(rows)}")
dd_better = sum(1 for r in rows if r["dd"] < r["bh_dd"])
print(f"  cells with a smaller max drawdown than buy-and-hold: {dd_better}/{len(rows)}")

print("\n" + "=" * 94)
print("2.  RETURN PER UNIT OF TIME EXPOSED")
print("=" * 94)
print("  The strategy sits in cash most of the time. If what it earns WHILE")
print("  INVESTED beats the index's own rate, the timing is adding something,")
print("  even when the absolute total is lower.\n")
print(f"{'w':>4}{'thr':>6}{'hold':>6}{'n':>5}{'inMkt%':>9}{'CAGR while invested%':>23}"
      f"{'index CAGR%':>14}{'edge':>10}")
for r in sorted(rows, key=lambda x: -x["cagr_exposed"])[:9]:
    print(f"{r['w']:>4}{r['thr']:>6.1f}{r['hold']:>6}{r['n']:>5}{100*r['inmkt']:>9.1f}"
          f"{100*r['cagr_exposed']:>23.2f}{100*r['bh_cagr']:>14.2f}"
          f"{100*(r['cagr_exposed']-r['bh_cagr']):>+10.2f}")

print("\n" + "=" * 94)
print("3.  IS IT A FEW CRISES?")
print("=" * 94)
tr = run(bars, w=60, thr=-2.0, hold=30, cost_bps=2.0)
s = summarise(tr, bars)
top = sorted(tr, key=lambda t: -t["ret"])[:5]
tot_log = sum(statistics.log(1+t["ret"]) if hasattr(statistics,'log') else 0 for t in tr)
import math
tot_log = sum(math.log(1 + t["ret"]) for t in tr)
top_log = sum(math.log(1 + t["ret"]) for t in top)
print(f"  w=60 thr=-2.0 hold=30: {s['n']} trades, {100*s['tot']:.1f}% total\n")
print(f"  {'date':<12}{'return%':>9}{'share of all log-growth':>26}")
for t in top:
    d = dt.datetime.utcfromtimestamp(t["t"]).date()
    print(f"  {str(d):<12}{100*t['ret']:>9.1f}"
          f"{100*math.log(1+t['ret'])/tot_log:>25.1f}%")
print(f"\n  the top 5 of {s['n']} trades account for "
      f"{100*top_log/tot_log:.1f}% of all compounded growth")
rest = [t for t in tr if t not in top]
eq2, dd2, _ = equity(rest, len(bars))
print(f"  remove them and the remaining {len(rest)} trades return "
      f"{100*(eq2/100-1):.1f}% over {s['years']:.1f} years "
      f"({100*((eq2/100)**(1/s['years'])-1):.2f}% CAGR)")

print("\n" + "=" * 94)
print("4.  OUT OF SAMPLE: fit nothing, just split the 20 years in half")
print("=" * 94)
mid = len(bars) // 2
h1, h2 = bars[:mid], bars[mid:]
print(f"  first half  {dt.datetime.utcfromtimestamp(h1[0]['t']).date()} -> "
      f"{dt.datetime.utcfromtimestamp(h1[-1]['t']).date()}")
print(f"  second half {dt.datetime.utcfromtimestamp(h2[0]['t']).date()} -> "
      f"{dt.datetime.utcfromtimestamp(h2[-1]['t']).date()}\n")
print(f"  {'half':<8}{'w':>4}{'thr':>6}{'hold':>6}{'n':>5}{'CAGR%':>8}"
      f"{'B&H CAGR%':>11}{'edge':>9}{'maxDD%':>9}{'B&H DD%':>9}")
for lab, bb in (("first", h1), ("second", h2)):
    for w, thr, hold in ((60, -2.0, 30), (60, -2.0, 10), (120, -2.0, 30)):
        t2 = run(bb, w=w, thr=thr, hold=hold, cost_bps=2.0)
        s2 = summarise(t2, bb)
        if not s2 or s2["n"] < 5: continue
        print(f"  {lab:<8}{w:>4}{thr:>6.1f}{hold:>6}{s2['n']:>5}"
              f"{100*s2['cagr']:>8.2f}{100*s2['bh_cagr']:>11.2f}"
              f"{100*(s2['cagr']-s2['bh_cagr']):>+9.2f}"
              f"{100*s2['dd']:>9.1f}{100*s2['bh_dd']:>9.1f}")
