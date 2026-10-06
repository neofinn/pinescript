"""Ablations, mirror and stop geometry -- on gold only."""
import json, os, sys
sys.path.insert(0, "/home/user/pinescript/scripts")
from inside_bar_short import setups, execute, stats
SC = "/tmp/claude-0/-home-user-pinescript/6b4bb2fe-c45d-5f96-b3e4-1392c689d1fc/scratchpad"
G = os.path.join(SC, "gold")
L = lambda f: json.load(open(os.path.join(G, f + ".json")))

MK = [("GOLD 30m", {"GC": L("GC_m30")}, 0.6),
      ("GOLD h1",  {"GC": L("GC_h1")},  0.6),
      ("GOLD 1D",  {"GC": L("GC_d")},   0.6),
      ("gold complex 30m",
       {"GLD": L("GLD_m30"), "IAU": L("IAU_m30"), "GDX": L("GDX_m30"),
        "GDXJ": L("GDXJ_m30")}, 3.0),
      ("SI+PL 30m", {"SI": L("SI_m30"), "PL": L("PL_m30")}, 2.0)]

VAR = [("full pattern", True, True), ("no inside-bar rule", True, False),
       ("no new-high rule", False, True)]
KW = dict(rr=2.0, stop_at="inside", valid_bars=3, on_close=False, max_hold=16)

print("=== ABLATION: does the inside bar do anything on gold? ===")
print("RR 2.0, stop at the inside bar high, entry on the break, lookback 20.")
print("'long' is the exact mirror of the pattern at a new low.\n")
print(f"{'market':<19}{'variant':<21}{'side':<7}{'n':>6}{'avgR':>9}{'PF':>7}{'win%':>7}")
grand = {}
for mname, data, cost in MK:
    for vname, ne, ni in VAR:
        for side in ("short", "long"):
            tr = []
            for k, v in data.items():
                tr += execute(v, setups(v, 20, 1.0, side, ne, ni),
                              side=side, cost_bps=cost, **KW)
            st = stats(tr)
            grand.setdefault((vname, side), []).append(st["avg_r"])
            print(f"{mname:<19}{vname:<21}{side:<7}{st['n']:>6}{st['avg_r']:>9.3f}"
                  f"{st['pf']:>7.2f}{st['win']:>7.1f}")
    print()
print("mean avg-R across the five gold-complex series")
for (vn, sd), v in grand.items():
    print(f"  {vn:<21}{sd:<7}{sum(v)/len(v):>+8.3f}")

print("\n=== EXIT MIX, gold's own settings ===")
for mname, data, cost in MK[:3]:
    tr = []
    for k, v in data.items():
        tr += execute(v, setups(v, 20, 1.0), cost_bps=cost, **KW)
    n = len(tr)
    if not n:
        continue
    st = sum(1 for t in tr if t["r"] < -0.9)
    tg = sum(1 for t in tr if t["r"] > 1.9)
    print(f"{mname:<10} {n:>5} trades: stopped {100*st/n:>4.0f}%  target {100*tg/n:>4.0f}%"
          f"  timed out {100*(n-st-tg)/n:>4.0f}%   of those that resolved, "
          f"{100*tg/max(st+tg,1):>4.1f}% hit target (random walk pays 33.3%)")

print("\n=== STOP GEOMETRY on gold, RR 2.0 (avg R / win%) ===")
pre = {m[0]: {k: setups(v, 20, 1.0) for k, v in m[1].items()} for m in MK}
print(f"{'stop x ref':>11}" + "".join(f"{m[0]:>18}" for m in MK))
for mult in (0.5, 1.0, 1.5, 2.0, 3.0, 5.0):
    line = f"{mult:>11.1f}"
    for mname, data, cost in MK:
        tr = []
        for k, v in data.items():
            tr += execute(v, pre[mname][k], rr=2.0, stop_at="mult",
                          stop_mult=mult, cost_bps=cost, max_hold=16)
        s = stats(tr)
        line += f"{s['avg_r']:>10.3f}{s['win']:>7.1f}%"
    print(line)
