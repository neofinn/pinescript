import json, os, sys, glob, random, statistics
sys.path.insert(0, "/home/user/pinescript/scripts")
from straddle_sar import run, summarise, equity, shuffle_bars
SC = "/tmp/claude-0/-home-user-pinescript/6b4bb2fe-c45d-5f96-b3e4-1392c689d1fc/scratchpad"
COST = {**{k: 1.0 for k in "ES NQ YM RTY GC SI CL NG EURUSD JPY".split()},
        **{k: 2.0 for k in "SPX DJI NDX RUT NIFTY SENSEX BANKNIFTY FTSE DAX N225".split()},
        **{k: 3.0 for k in "SPY QQQ GLD TLT AAPL NVDA TSLA JPM".split()},
        **{k: 10.0 for k in "BTC ETH".split()}}
D = {os.path.basename(f)[:-5]: json.load(open(f))
     for f in sorted(glob.glob(os.path.join(SC, "h1", "*.json")))}
print(f"{len(D)} hourly series, {sum(len(v) for v in D.values()):,} bars\n")

def pooled(**kw):
    """Equal-weight across markets: mean terminal multiple and mean CAGR."""
    fin, cg, dds, ns, whips, beat = [], [], [], 0, 0, 0
    for k, v in D.items():
        t, i = run(v, cost_bps=COST[k], **kw)
        s = summarise(t, v, i)
        if not s: continue
        fin.append(s["final"]); cg.append(s["cagr"]); dds.append(s["dd"])
        ns += s["n"]; whips += s["whip"]; beat += s["cagr"] > s["hold_cagr"]
    return (statistics.mean(fin), statistics.mean(cg), statistics.mean(dds),
            ns, whips, beat, len(fin))

print("=" * 92)
print("1.  THE GRID -- entry channel, trailing stop, and whether it reverses")
print("=" * 92)
print(f"{'mode':<6}{'entry':>7}{'trail':>7}{'type':>10}{'trades':>8}{'mean x':>9}"
      f"{'mean CAGR%':>12}{'mean DD%':>10}{'whips':>7}{'beat hold':>11}")
rows = []
for sar in (True, False):
    for el in (10, 20, 50):
        for tl, tt, am in ((10, "donchian", 0), (20, "donchian", 0),
                           (0, "atr", 3.0), (0, "atr", 5.0)):
            kw = dict(entry_len=el, trail_len=tl or 10, trail=tt,
                      atr_mult=am or 3.0, sar=sar)
            f, c, d, ns, w, bt, m = pooled(**kw)
            lab = f"{tt}{'' if tt=='donchian' else ' '+str(am)}"
            rows.append((sar, el, tl, tt, am, f, c, d, ns, bt))
            print(f"{'SAR' if sar else 'flat':<6}{el:>7}{tl if tl else '-':>7}"
                  f"{lab:>10}{ns:>8}{f:>9.3f}{c:>12.2f}{d:>10.1f}{w:>7}{bt:>7}/{m}")
hold_c = statistics.mean(
    ((v[-1]["c"]/v[0]["c"]) ** (1/((v[-1]["t"]-v[0]["t"])/(365.25*86400))) - 1)*100
    for v in D.values())
hold_x = statistics.mean(v[-1]["c"]/v[0]["c"] for v in D.values())
print(f"\n  buy-and-hold, equal weight: {hold_x:.3f}x, {hold_c:.2f}% CAGR")
pos = sum(1 for r in rows if r[6] > 0)
bh  = sum(1 for r in rows if r[6] > hold_c)
print(f"  cells with positive mean CAGR: {pos}/{len(rows)}")
print(f"  cells beating buy-and-hold's mean CAGR: {bh}/{len(rows)}")
best = max(rows, key=lambda r: r[6])
print(f"  best: {'SAR' if best[0] else 'flat'} entry {best[1]} "
      f"trail {best[3]}{'' if best[3]=='donchian' else ' '+str(best[4])} "
      f"-> {best[6]:.2f}% CAGR, beat hold in {best[9]}/30 markets")
json.dump([list(r) for r in rows], open(os.path.join(SC,"sar_rows.json"),"w"))
