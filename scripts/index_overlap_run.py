import json, os, random, statistics, sys
sys.path.insert(0, "/home/user/pinescript/scripts")
from index_overlap import crossings, evaluate, norm_window
SC = "/tmp/claude-0/-home-user-pinescript/6b4bb2fe-c45d-5f96-b3e4-1392c689d1fc/scratchpad"
I = os.path.join(SC, "idx")
L = lambda f: json.load(open(os.path.join(I, f + ".json")))

TF = [("1-minute", "m1", 390), ("5-minute", "m5", 78),
      ("1-hour", "h1", 7), ("daily", "d", 1)]

print("=" * 76)
print("0.  THE TWO SERIES")
print("=" * 76)
for lab, sfx, _ in TF:
    a, b = L("SPX_" + sfx), L("DJI_" + sfx)
    m = {x["t"]: x["c"] for x in b}
    pairs = [(x["c"], m[x["t"]]) for x in a if x["t"] in m]
    s = [p[0] for p in pairs]; d = [p[1] for p in pairs]
    rs = [(s[i]-s[i-1])/s[i-1] for i in range(1, len(s))]
    rd = [(d[i]-d[i-1])/d[i-1] for i in range(1, len(d))]
    ms, md = statistics.mean(rs), statistics.mean(rd)
    cov = sum((x-ms)*(y-md) for x, y in zip(rs, rd))
    cor = cov / ((sum((x-ms)**2 for x in rs) * sum((y-md)**2 for y in rd)) ** .5)
    print(f"  {lab:<10} {len(pairs):>6} aligned bars   SPX {s[-1]:>9,.0f}   "
          f"DJI {d[-1]:>9,.0f}   return correlation {cor:>5.3f}")
print("\n  On a SHARED price axis the gap is never smaller than "
      f"{min(abs(d[i]-s[i]) for i in range(len(s))):,.0f} points. The lines")
print("  cannot touch. Any 'overlap' comes from giving each symbol its own axis.")

print("\n" + "=" * 76)
print("1.  WHERE THEY CROSS IS SET BY THE ZOOM, NOT BY THE MARKET")
print("=" * 76)
a, b = L("SPX_m1"), L("DJI_m1")
m = {x["t"]: x["c"] for x in b}
pairs = [(x["c"], m[x["t"]]) for x in a if x["t"] in m]
S = [p[0] for p in pairs]; D = [p[1] for p in pairs]
print(f"  1-minute bars, {len(S)} of them. Crossings of the two auto-scaled lines,")
print("  recomputed at different visible-window lengths:\n")
sets = {}
for w in (30, 60, 120, 240, 390):
    c = crossings(S, D, w)
    sets[w] = c
    print(f"    window {w:>4} bars ({w/390:>4.1f} sessions on screen): "
          f"{len(c):>4} crossings  = one every {len(S)/max(len(c),1):>5.1f} min")
print("\n  how much do those crossing sets agree with each other? (Jaccard)\n")
ws = sorted(sets)
print("        " + "".join(f"{w:>8}" for w in ws))
for x in ws:
    row = f"  {x:>5} "
    for y in ws:
        u = len(sets[x] | sets[y]); i = len(sets[x] & sets[y])
        row += f"{(i/u if u else 0):>8.2f}"
    print(row)
print("\n  Same data, same two symbols, same second. Only the zoom changed.")

print("\n" + "=" * 76)
print("2.  DO THE CROSSINGS MARK BOTTOMS IN SPX?")
print("=" * 76)
print("  'bottom' = SPX is the lowest close within +/- k bars (uses the future;")
print("  a real-time rule cannot see it, so this is the most generous possible")
print("  scoring). Baseline = the same number of random bars, 400 draws.\n")
rng = random.Random(5)
print(f"  {'timeframe':<11}{'window':>7}{'k':>5}{'crossings':>11}{'bottom%':>9}"
      f"{'random%':>9}{'pct':>6}   {'fwd bps':>8}{'rand bps':>9}{'pct':>6}")
rows = []
for lab, sfx, perday in TF:
    aa, bb = L("SPX_" + sfx), L("DJI_" + sfx)
    mm = {x["t"]: x["c"] for x in bb}
    pr = [(x["c"], mm[x["t"]]) for x in aa if x["t"] in mm]
    s = [p[0] for p in pr]; d = [p[1] for p in pr]
    for w in (60, 240):
        if w >= len(s) // 3:
            continue
        for k in (10, 30):
            r = evaluate(s, d, w, k, rng, lab)
            if not r:
                continue
            rows.append((lab, r))
            print(f"  {lab:<11}{w:>7}{k:>5}{r['n']:>11}{100*r['hit']:>8.1f}%"
                  f"{100*r['base_hit']:>8.1f}%{r['pct_h']:>6.0f}"
                  f"{r['fwd']:>9.2f}{r['base_fwd']:>9.2f}{r['pct_f']:>6.0f}")
json.dump({"ok": True}, open(os.path.join(SC, "idx_done.json"), "w"))
