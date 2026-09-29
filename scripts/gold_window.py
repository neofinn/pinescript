"""Is gold's 30m result a TIMEFRAME effect or a WINDOW effect?

The 30m sample is 60 days (2026-07-21 -> 09-29) and gives 38 trades. Gold h1
over 2.4 years is at the 4th percentile of its own control -- worse than
shorting at random. Two explanations, and they are distinguishable:

  timeframe  30m holds something h1 does not
  window     the summer of 2026 was kind to shorts in gold, at any timeframe

Restricting h1 and the daily to the SAME 60 days separates them.
"""
import json, os, sys, datetime as dt
sys.path.insert(0, "/home/user/pinescript/scripts")
from inside_bar_short import setups, execute, stats
SC = "/tmp/claude-0/-home-user-pinescript/6b4bb2fe-c45d-5f96-b3e4-1392c689d1fc/scratchpad"
G = os.path.join(SC, "gold")
L = lambda f: json.load(open(os.path.join(G, f + ".json")))

m30 = L("GC_m30")
T0, T1 = m30[0]["t"], m30[-1]["t"]
print(f"the 30m window: {dt.datetime.utcfromtimestamp(T0).date()} -> "
      f"{dt.datetime.utcfromtimestamp(T1).date()}")
c0, c1 = m30[0]["c"], m30[-1]["c"]
print(f"gold over it: {c0:,.1f} -> {c1:,.1f}  ({100*(c1/c0-1):+.1f}%)\n")

KW = dict(rr=2.0, valid_bars=3, max_hold=16, cost_bps=0.6)
def show(lab, bars, **kw):
    for stop in ("inside", "ref"):
        for oc in (False, True):
            tr = execute(bars, setups(bars, 20, 1.0), stop_at=stop,
                         on_close=oc, **KW, **kw)
            s = stats(tr)
            print(f"  {lab:<22}{stop:>7}{'close' if oc else 'break':>7}"
                  f"{s['n']:>6}{s['tot_r']:>9.2f}{s['avg_r']:>9.3f}{s['win']:>7.1f}")

print(f"  {'series':<22}{'stop':>7}{'entry':>7}{'n':>6}{'totR':>9}{'avgR':>9}{'win%':>7}")
show("30m, the window", m30)
print()
h1 = L("GC_h1")
show("h1, ALL 2.4 years", h1)
h1w = [b for b in h1 if T0 <= b["t"] <= T1]
print(f"  -- h1 restricted to the same 60 days ({len(h1w)} bars) --")
show("h1, the same window", h1w)
print()
d = L("GC_d")
show("1D, ALL 20 years", d)
dw = [b for b in d if T0 <= b["t"] <= T1]
print(f"  -- 1D over the same 60 days ({len(dw)} bars): too few to test --")
print()
# and the same window on the OTHER metals, at 30m
print("  the same 60 days, 30m, other instruments")
for nm, f, c in [("GLD 30m","GLD_m30",3.0), ("IAU 30m","IAU_m30",3.0),
                 ("GDX 30m","GDX_m30",3.0), ("SI 30m","SI_m30",2.0),
                 ("PL 30m","PL_m30",3.0)]:
    b = [x for x in L(f) if T0 <= x["t"] <= T1]
    kw = dict(KW); kw["cost_bps"] = c
    tr = execute(b, setups(b, 20, 1.0), stop_at="inside", on_close=False, **kw)
    s = stats(tr)
    tr2 = execute(b, setups(b, 20, 1.0), stop_at="inside", on_close=True, **kw)
    s2 = stats(tr2)
    print(f"  {nm:<22}{'inside':>7}{'break':>7}{s['n']:>6}{s['tot_r']:>9.2f}"
          f"{s['avg_r']:>9.3f}{s['win']:>7.1f}   | close {s2['n']:>4}"
          f"{s2['tot_r']:>8.2f}{s2['avg_r']:>8.3f}")
