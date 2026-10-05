"""Does PCR carry forward information at all? Then: does it help the 5 EMA?"""
import json, os, sys, statistics, random, datetime as dt
sys.path.insert(0, "/home/user/pinescript/scripts")
from ema5_pcr import run, stats, load_pcr, pcr_gate
from inside_bar_short import aggregate
SC = "/tmp/claude-0/-home-user-pinescript/6b4bb2fe-c45d-5f96-b3e4-1392c689d1fc/scratchpad"
P = load_pcr(os.path.join(SC, "pcr.json"))
L = lambda d,s: json.load(open(os.path.join(SC,d,s+".json")))
FIELDS = ("pcr_oi_all","pcr_oi_near","pcr_v_all","pcr_v_near")

print("=" * 90)
print("1.  DOES PCR PREDICT ANYTHING?  forward index return by PCR bucket")
print("=" * 90)
print("  PCR is published after the close, so day d's PCR is matched to the")
print("  return of day d+1 onward. Quintiles of PCR, mean forward return.\n")
for sym in ("NIFTY","BANKNIFTY"):
    d1 = L("d1", sym)
    px = {dt.datetime.utcfromtimestamp(b["t"]).date(): b["c"] for b in d1}
    days = sorted(px)
    nxt = {d: days[i+1] for i, d in enumerate(days[:-1])}
    fwd5 = {d: days[min(i+5, len(days)-1)] for i, d in enumerate(days)}
    print(f"  --- {sym} ---")
    for fld in FIELDS:
        rows = []
        for d, rec in sorted(P.get(sym, {}).items()):
            v = rec.get(fld)
            if v is None or d not in nxt or nxt[d] not in px: continue
            r1 = (px[nxt[d]]/px[d]-1)*10000
            r5 = (px[fwd5[d]]/px[d]-1)*10000
            rows.append((v, r1, r5))
        if len(rows) < 100:
            print(f"    {fld:<14} only {len(rows)} days -- skipped"); continue
        rows.sort()
        q = len(rows)//5
        line = f"    {fld:<14} n={len(rows):<4}"
        means1, means5 = [], []
        for k in range(5):
            seg = rows[k*q:(k+1)*q] if k < 4 else rows[4*q:]
            means1.append(statistics.mean(x[1] for x in seg))
            means5.append(statistics.mean(x[2] for x in seg))
        line += "  next-day bps by quintile: " + " ".join(f"{m:>+6.1f}" for m in means1)
        print(line)
        print(f"    {'':<14}      5-day bps by quintile: "
              + " ".join(f"{m:>+6.1f}" for m in means5)
              + f"   spread Q5-Q1 {means5[4]-means5[0]:>+7.1f}")
    print()

print("=" * 90)
print("2.  PCR AS A FILTER ON THE 5 EMA")
print("=" * 90)
print("  Conventional: high PCR = bullish (take longs), low PCR = bearish.")
print("  Contrarian is the same thresholds with the sides swapped. Both run.\n")
res = {}
for sym in ("NIFTY","BANKNIFTY"):
    h1 = L("h1", sym); d1 = L("d1", sym)
    for tf, b in (("h1", h1), ("1d", d1)):
        base = {}
        for side in ("short","long"):
            base[side] = stats(run(b, side=side, rr=2.0, cost_bps=2.0))
        # restrict the unfiltered baseline to the PCR era for a fair comparison
        dates = set(P.get(sym, {}))
        if not dates: continue
        lo_d, hi_d = min(dates), max(dates)
        bw = [x for x in b if lo_d <= dt.datetime.utcfromtimestamp(x["t"]).date() <= hi_d]
        if len(bw) < 200: continue
        print(f"  --- {sym} {tf} --- (PCR era: {lo_d} -> {hi_d}, {len(bw)} bars)")
        print(f"    {'filter':<34}{'side':<7}{'n':>6}{'totR':>9}{'avgR':>9}{'PF':>7}")
        for side in ("short","long"):
            s = stats(run(bw, side=side, rr=2.0, cost_bps=2.0))
            print(f"    {'none (baseline, PCR era)':<34}{side:<7}{s['n']:>6}"
                  f"{s['tot_r']:>9.1f}{s['avg_r']:>9.3f}{s['pf']:>7.2f}")
            res[(sym,tf,side,"none")] = s["avg_r"]
        for fld in ("pcr_oi_all","pcr_oi_near"):
            vals = sorted(v[fld] for v in P[sym].values() if v.get(fld))
            if len(vals) < 50: continue
            t33, t67 = vals[len(vals)//3], vals[2*len(vals)//3]
            for lab, side, lo, hi in (
                (f"{fld}: long only when PCR>{t67:.2f}",  "long",  t67, None),
                (f"{fld}: short only when PCR<{t33:.2f}", "short", None, t33),
                (f"{fld}: long only when PCR<{t33:.2f}",  "long",  None, t33),
                (f"{fld}: short only when PCR>{t67:.2f}", "short", t67, None)):
                g = pcr_gate(P[sym], fld, lo, hi)
                s = stats(run(bw, side=side, rr=2.0, cost_bps=2.0, allow=g))
                if s["n"] < 20: continue
                print(f"    {lab:<34}{side:<7}{s['n']:>6}{s['tot_r']:>9.1f}"
                      f"{s['avg_r']:>9.3f}{s['pf']:>7.2f}")
                res[(sym,tf,side,lab)] = s["avg_r"]
        print()
json.dump({str(k): v for k, v in res.items()}, open(os.path.join(SC,"pcr_res.json"),"w"))
