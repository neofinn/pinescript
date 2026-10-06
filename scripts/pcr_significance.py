"""Is the PCR-volume signal real, and does it survive the obvious ablation?"""
import json, os, sys, statistics, random, datetime as dt
sys.path.insert(0, "/home/user/pinescript/scripts")
from ema5_pcr import load_pcr
SC = "/tmp/claude-0/-home-user-pinescript/6b4bb2fe-c45d-5f96-b3e4-1392c689d1fc/scratchpad"
P = load_pcr(os.path.join(SC, "pcr.json"))
L = lambda s: json.load(open(os.path.join(SC, "d1", s + ".json")))

def series(sym, fld, horizon=5):
    d1 = L(sym)
    px = {dt.datetime.utcfromtimestamp(b["t"]).date(): b["c"] for b in d1}
    days = sorted(px)
    pos = {d: i for i, d in enumerate(days)}
    rows = []
    for d, rec in sorted(P.get(sym, {}).items()):
        v = rec.get(fld)
        if v is None or d not in pos: continue
        i = pos[d]
        if i + horizon >= len(days): continue
        fwd = (px[days[i+horizon]]/px[d] - 1) * 10000
        past = (px[d]/px[days[max(0, i-horizon)]] - 1) * 10000
        rows.append((v, fwd, past))
    return rows

def q51(rows):
    r = sorted(rows); q = len(r)//5
    return statistics.mean(x[1] for x in r[4*q:]) - statistics.mean(x[1] for x in r[:q])

def spearman(a, b):
    ra = {v: i for i, v in enumerate(sorted(a))}
    rb = {v: i for i, v in enumerate(sorted(b))}
    x = [ra[v] for v in a]; y = [rb[v] for v in b]
    mx, my = statistics.mean(x), statistics.mean(y)
    num = sum((p-mx)*(q-my) for p, q in zip(x, y))
    den = (sum((p-mx)**2 for p in x) * sum((q-my)**2 for q in y)) ** .5
    return num/den if den else 0.0

print("="*88)
print("3.  IS THE PCR-VOLUME SIGNAL REAL?  permutation test, 10,000 shuffles")
print("="*88)
print("  The pairing between PCR and the forward return is destroyed by")
print("  shuffling; everything else is held. 5-day forward return.\n")
print(f"  {'index':<11}{'field':<14}{'n':>5}{'Q5-Q1 bps':>11}{'perm 2.5th':>12}"
      f"{'perm 97.5th':>13}{'pct':>6}{'spearman':>10}")
rng = random.Random(3)
real = {}
for sym in ("NIFTY","BANKNIFTY"):
    for fld in ("pcr_v_all","pcr_v_near","pcr_oi_all","pcr_oi_near"):
        rows = series(sym, fld)
        if len(rows) < 100: continue
        obs = q51(rows)
        fwd = [r[1] for r in rows]
        draws = []
        for _ in range(10000):
            sh = fwd[:]; rng.shuffle(sh)
            draws.append(q51([(r[0], s, r[2]) for r, s in zip(rows, sh)]))
        draws.sort()
        pct = 100*sum(1 for x in draws if x < obs)/len(draws)
        sp = spearman([r[0] for r in rows], fwd)
        real[(sym,fld)] = (obs, pct, sp, len(rows))
        print(f"  {sym:<11}{fld:<14}{len(rows):>5}{obs:>11.1f}{draws[250]:>12.1f}"
              f"{draws[9750]:>13.1f}{pct:>6.1f}{sp:>10.3f}")
print("\n  (pct is where the real spread sits in its own permutation distribution;")
print("   below 2.5 or above 97.5 is significant at 95% for a single test)")

print("\n" + "="*88)
print("4.  THE ABLATION: is PCR-volume just saying 'the market already fell'?")
print("="*88)
print("  Put volume spikes during selloffs. If the index's own trailing 5-day")
print("  return predicts the next 5 days as well as PCR does, PCR adds nothing.\n")
print(f"  {'index':<11}{'predictor':<24}{'n':>5}{'Q5-Q1 bps':>11}{'spearman':>10}")
for sym in ("NIFTY","BANKNIFTY"):
    rows = series(sym, "pcr_v_all")
    fwd = [r[1] for r in rows]
    print(f"  {sym:<11}{'PCR-volume (all exp)':<24}{len(rows):>5}"
          f"{q51(rows):>11.1f}{spearman([r[0] for r in rows], fwd):>10.3f}")
    past_rows = [(r[2], r[1], r[0]) for r in rows]
    print(f"  {sym:<11}{'trailing 5-day return':<24}{len(rows):>5}"
          f"{q51(past_rows):>11.1f}{spearman([r[2] for r in rows], fwd):>10.3f}")
    # PCR residual: within each trailing-return quintile, does PCR still sort?
    byq = sorted(rows, key=lambda r: r[2]); q = len(byq)//5
    sub = []
    for k in range(5):
        seg = byq[k*q:(k+1)*q] if k < 4 else byq[4*q:]
        seg = sorted(seg)
        m = len(seg)//3
        sub.append(statistics.mean(x[1] for x in seg[-m:]) -
                   statistics.mean(x[1] for x in seg[:m]))
    print(f"  {sym:<11}{'PCR WITHIN past-return':<24}{len(rows):>5}"
          f"{statistics.mean(sub):>11.1f}{'':>10}   (top third minus bottom third,")
    print(f"  {'':<11}{'  quintiles':<24}{'':>5}{'':>11}{'':>10}    averaged over 5 buckets)")
    print()
