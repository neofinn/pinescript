"""Rs 10,00,000 split 50/50: index options and stock options, each compounding.

Two sleeves, each its own account of Rs 5,00,000, each risking 5% of ITS OWN
equity per trade. That is the "same rules" reading of a split: a loss in one
sleeve shrinks that sleeve's next position and leaves the other alone.

The point of a split is not the return, it is the drawdown. Two sleeves with
the same expectancy and uncorrelated trades produce a combined drawdown
materially smaller than either alone; two sleeves that lose together produce
nothing but a smaller version of the same curve. So the correlation between the
sleeves' monthly returns is reported next to the totals, because it is the only
thing that says whether splitting did any work.

Both sleeves are scored against the same direction-shuffled control used
throughout: keep every entry time, stop and gate, shuffle only what Kronos
predicted.
"""
from __future__ import annotations
import datetime as dt
import json, os, statistics, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import zones as Z
import kronos_zone_strategy as KZ
import fno_kronos_zone as FZ
from fno_vwap_screen import load_top20
from india_options import SPEC

SLEEVE = 500_000.0


def curve(dated, start):
    """Equity path and max drawdown from dated trades."""
    eq = peak = start
    dd = 0.0
    out = []
    for day, pnl in dated:
        eq = max(0.0, eq + pnl)
        peak = max(peak, eq)
        dd = max(dd, (peak - eq) / peak)
        out.append((day, eq))
    return out, dd * 100, eq


def monthly(dated, start):
    """Return per calendar month, as a fraction of the sleeve at month start."""
    by = {}
    for day, pnl in dated:
        by.setdefault((day.year, day.month), []).append(pnl)
    eq = start
    out = {}
    for k in sorted(by):
        s = sum(by[k])
        out[k] = s / eq if eq > 0 else 0.0
        eq = max(0.0, eq + s)
    return out


def correl(a, b):
    ks = sorted(set(a) & set(b))
    if len(ks) < 4:
        return None, len(ks)
    x = [a[k] for k in ks]
    y = [b[k] for k in ks]
    mx, my = sum(x) / len(x), sum(y) / len(y)
    num = sum((p - mx) * (q - my) for p, q in zip(x, y))
    den = (sum((p - mx) ** 2 for p in x) * sum((q - my) ** 2 for q in y)) ** 0.5
    return (num / den if den else 0.0), len(ks)


def index_sleeve(d, shuffle=None):
    bars = json.load(open(os.path.join(d, "htf", "NIFTY_h1.json")))
    fc = json.load(open(os.path.join(d, "htf_fc", "NIFTY_h1.json")))
    if shuffle is not None:
        fc = KZ.shuffled_forecasts(fc, shuffle)
    # 2026 only, so both sleeves cover the same calendar
    fc = [f for f in fc
          if dt.datetime.utcfromtimestamp(f["t"]).year == 2026]
    if not fc:
        return [], SLEEVE, []
    vix = {}
    for b in json.load(open(os.path.join(d, "live", "INDIAVIX.json"))):
        k = str(dt.datetime.utcfromtimestamp(b["t"]).date())
        if k not in vix:
            vix[k] = b["c"]
    zn = Z.find_zones(bars)
    med = statistics.median(
        abs((f["p_close"][-1] - f["last_close"]) / f["last_close"]) for f in fc)
    plan = KZ.build_plan(bars, fc, zn, med, 1.5, False)   # the best NIFTY cell
    lo = min(f["i"] for f in fc)
    KZ.CAP0 = SLEEVE
    return KZ.run(bars, plan, vix, SPEC["NIFTY"], 1.5, lo, len(bars))


def stock_sleeve(d, shuffle=None):
    data = load_top20(d)
    fcs = json.load(open(os.path.join(d, "screen_forecasts.json")))
    med = statistics.median(
        abs((r["p_close"][-1] - r["last_close"]) / r["last_close"]) for r in fcs)
    FZ.CAP0 = SLEEVE
    return FZ.build_and_run(data, fcs, med, 1.5, False, 1.15,
                            shuffle_dirs=shuffle)


def main():
    d = sys.argv[1]
    print(f"Rs {2*SLEEVE:,.0f} split 50/50, each sleeve compounding "
          f"independently, 5% cap per trade\n")
    _, ieq, idated = index_sleeve(d)
    _, seq, sdated = stock_sleeve(d)
    _, idd, _ = curve(idated, SLEEVE)
    _, sdd, _ = curve(sdated, SLEEVE)

    comb = sorted(idated + sdated, key=lambda x: x[0])
    _, cdd, ceq = curve(comb, 2 * SLEEVE)
    print(f"{'sleeve':<22}{'n':>5}{'start Rs':>12}{'final Rs':>14}{'x':>7}{'maxDD%':>9}")
    print(f"{'INDEX (NIFTY opts)':<22}{len(idated):>5}{SLEEVE:>12,.0f}"
          f"{ieq:>14,.0f}{ieq/SLEEVE:>7.2f}{idd:>9.1f}")
    print(f"{'STOCKS (top-20 F&O)':<22}{len(sdated):>5}{SLEEVE:>12,.0f}"
          f"{seq:>14,.0f}{seq/SLEEVE:>7.2f}{sdd:>9.1f}")
    print(f"{'COMBINED':<22}{len(comb):>5}{2*SLEEVE:>12,.0f}"
          f"{ieq+seq:>14,.0f}{(ieq+seq)/(2*SLEEVE):>7.2f}{cdd:>9.1f}")

    r, k = correl(monthly(idated, SLEEVE), monthly(sdated, SLEEVE))
    print(f"\nmonthly return correlation between sleeves: "
          f"{'%.3f' % r if r is not None else 'n/a'} over {k} shared months")
    worst = max(idd, sdd)
    print(f"worst single sleeve drawdown {worst:.1f}%  ->  combined {cdd:.1f}%"
          f"   ({'diversification helped' if cdd < worst else 'no benefit'})")

    # the same portfolio with only the predicted directions shuffled
    sh = []
    for k2 in range(25):
        _, ie, _ = index_sleeve(d, shuffle=9000 + k2)
        _, se, _ = stock_sleeve(d, shuffle=9000 + k2)
        sh.append(ie + se)
    sh.sort()
    pct = 100.0 * sum(1 for x in sh if x < ieq + seq) / len(sh)
    print(f"\ndirection-shuffled portfolio: median Rs "
          f"{statistics.median(sh):,.0f}, 95th Rs {sh[int(len(sh)*0.95)]:,.0f}")
    print(f"the real portfolio sits at the {pct:.0f}th percentile")


if __name__ == "__main__":
    main()
