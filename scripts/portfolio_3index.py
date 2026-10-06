"""Rs 15,00,000 across three index sleeves: NIFTY, BANKNIFTY, SENSEX.

Rs 5,00,000 each, compounding independently, 5% of its own equity per trade,
Kronos for direction and supply/demand for the stop. 2026 only.

THE QUESTION IS WHETHER THIS IS DIVERSIFICATION AT ALL. The stock/index split
worked because the sleeves were genuinely different things -- monthly return
correlation 0.222, and a combined drawdown eleven points below the worse
sleeve. These three are not obviously different things. SENSEX and NIFTY are
built from heavily overlapping large caps; BANKNIFTY's constituents sit inside
NIFTY and make up roughly a third of its weight. If the sleeves move together,
splitting across them buys nothing except three sets of transaction costs.

So the pairwise correlations are reported first and the totals second, and the
combined drawdown is printed against the worst single sleeve so the answer is
visible rather than asserted.

Contract terms differ per index and are not cosmetic: NIFTY weekly on NSE with
a 75 lot and 50-point strikes, SENSEX weekly on BSE with a 20 lot and 100-point
strikes and its own cost stack, BANKNIFTY MONTHLY ONLY since the weeklies were
withdrawn, with a 35 lot.
"""
from __future__ import annotations
import datetime as dt
import itertools, json, os, statistics, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import zones as Z
import kronos_zone_strategy as KZ
from india_options import SPEC
from portfolio_split import curve, monthly, correl

SLEEVE = 500_000.0
IDX = ("NIFTY", "BANKNIFTY", "SENSEX")


def sleeve(d, name, shuffle=None, thresh_mode="median", rr=1.5, gate=False):
    bars = json.load(open(os.path.join(d, "htf", f"{name}_h1.json")))
    fp = os.path.join(d, "htf_fc", f"{name}_h1.json")
    if not os.path.exists(fp):
        return None
    fc = json.load(open(fp))
    fc = [f for f in fc if dt.datetime.utcfromtimestamp(f["t"]).year == 2026]
    if len(fc) < 20:
        return None
    if shuffle is not None:
        fc = KZ.shuffled_forecasts(fc, shuffle)
    vix = {}
    for b in json.load(open(os.path.join(d, "live", "INDIAVIX.json"))):
        k = str(dt.datetime.utcfromtimestamp(b["t"]).date())
        if k not in vix:
            vix[k] = b["c"]
    zn = Z.find_zones(bars)
    med = statistics.median(
        abs((f["p_close"][-1] - f["last_close"]) / f["last_close"]) for f in fc)
    thresh = med if thresh_mode == "median" else 0.0
    plan = KZ.build_plan(bars, fc, zn, thresh, rr, gate)
    lo = min(f["i"] for f in fc)
    KZ.CAP0 = SLEEVE
    return KZ.run(bars, plan, vix, SPEC[name], rr, lo, len(bars))


def main():
    d = sys.argv[1]
    print(f"Rs {3*SLEEVE:,.0f} across three index sleeves, "
          f"Rs {SLEEVE:,.0f} each, compounding, 5% cap per trade")
    print(f"Kronos direction + supply/demand stop, 2026, hourly\n")

    res = {}
    for nm in IDX:
        r = sleeve(d, nm)
        if r is None:
            print(f"  {nm}: no forecasts yet")
            continue
        tr, eq, dated = r
        _, dd, _ = curve(dated, SLEEVE)
        res[nm] = dict(n=len(dated), eq=eq, dd=dd, dated=dated,
                       m=monthly(dated, SLEEVE))
    if len(res) < 2:
        return

    print(f"{'sleeve':<12}{'expiry':<10}{'lot':>5}{'n':>5}{'final Rs':>14}"
          f"{'x':>7}{'maxDD%':>9}")
    for nm in IDX:
        if nm not in res:
            continue
        s = res[nm]
        sp = SPEC[nm]
        print(f"{nm:<12}{sp['expiry']:<10}{sp['lot']:>5}{s['n']:>5}"
              f"{s['eq']:>14,.0f}{s['eq']/SLEEVE:>7.2f}{s['dd']:>9.1f}")

    allt = sorted([x for nm in res for x in res[nm]["dated"]], key=lambda x: x[0])
    start = SLEEVE * len(res)
    _, cdd, _ = curve(allt, start)
    tot = sum(res[nm]["eq"] for nm in res)
    print(f"{'COMBINED':<12}{'':<10}{'':>5}{len(allt):>5}{tot:>14,.0f}"
          f"{tot/start:>7.2f}{cdd:>9.1f}")

    print(f"\npairwise monthly return correlation:")
    names = [n for n in IDX if n in res]
    for a, b in itertools.combinations(names, 2):
        r, k = correl(res[a]["m"], res[b]["m"])
        print(f"  {a:<11} vs {b:<11} "
              f"{'%+.3f' % r if r is not None else 'n/a':>8}  ({k} shared months)")
    worst = max(res[n]["dd"] for n in names)
    print(f"\nworst single sleeve drawdown {worst:.1f}%  ->  combined {cdd:.1f}%")
    if cdd < worst - 2:
        print("  the split reduced drawdown materially")
    elif cdd < worst:
        print("  the split reduced drawdown only marginally")
    else:
        print("  the split did NOT reduce drawdown -- these are the same bet")

    sh = []
    for k2 in range(25):
        t = 0.0
        ok = True
        for nm in names:
            r = sleeve(d, nm, shuffle=12000 + k2)
            if r is None:
                ok = False
                break
            t += r[1]
        if ok:
            sh.append(t)
    if sh:
        sh.sort()
        pct = 100.0 * sum(1 for x in sh if x < tot) / len(sh)
        print(f"\ndirection-shuffled portfolio: median Rs "
              f"{statistics.median(sh):,.0f}, 95th Rs {sh[int(len(sh)*0.95)]:,.0f}")
        print(f"the real portfolio sits at the {pct:.0f}th percentile")


if __name__ == "__main__":
    main()
