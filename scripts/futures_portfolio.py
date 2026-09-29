"""ES + NQ futures portfolio, daily rebalanced. Same rules as the index work.

The correlation question again, and I have been wrong about it twice. I
expected three Indian indices to be one bet and they were not, because
BANKNIFTY's monthly-only expiry put its trades on a different calendar. ES and
NQ have no such difference: both are continuous US equity futures, same hours,
same session, overlapping constituents at the mega-cap end. If the expiry
calendar was what decorrelated the Indian sleeves, these two should NOT
decorrelate.

So the prediction is explicit before the run: ES and NQ should correlate far
higher than 0.395, and the two-sleeve split should buy much less drawdown
reduction than the three-index one did. Measured below rather than asserted.
"""
from __future__ import annotations
import datetime as dt
import json, os, statistics, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from futures_strategy import run, stats
from portfolio_split import correl, curve, monthly


def sleeve(d, sym, start, micro=True, **kw):
    bars = json.load(open(os.path.join(d, "fut", f"{sym}_h1.json")))
    fp = os.path.join(d, "fut_fc", f"{sym}_h1.json")
    if not os.path.exists(fp):
        return None
    fc = json.load(open(fp))
    if len(fc) < 20:
        return None
    contract = ("M" + sym) if micro else sym
    return run(bars, fc, contract, start, **kw) + (contract,)


def main():
    d = sys.argv[1]
    total = float(sys.argv[2]) if len(sys.argv) > 2 else 25_000.0
    half = total / 2
    print(f"ES + NQ futures, ${total:,.0f} split two ways, compounding, "
          f"5% cap per trade")
    print(f"Kronos direction + supply/demand stop, hourly, micros\n")

    res = {}
    for sym in ("ES", "NQ"):
        r = sleeve(d, sym, half)
        if r is None:
            print(f"  {sym}: forecasts not ready")
            continue
        trades, eq, contract = r
        s = stats(trades, half)
        if s is None:
            continue
        res[sym] = dict(trades=trades, eq=eq, contract=contract, **s)

    if not res:
        return
    print(f"{'sleeve':<8}{'contract':<6}{'n':>5}{'final $':>12}{'x':>7}"
          f"{'PF':>7}{'win%':>7}{'maxDD%':>9}")
    for sym, s in res.items():
        print(f"{sym:<8}{s['contract']:<6}{s['n']:>5}{s['final']:>12,.0f}"
              f"{s['final']/half:>7.2f}{s['pf']:>7.2f}{s['win']:>7.1f}"
              f"{s['dd']:>9.1f}")
    if len(res) == 2:
        allt = sorted([t for s in res.values() for t in s["trades"]],
                      key=lambda x: x[0])
        _, cdd, _ = curve(allt, total)
        tot = sum(s["eq"] for s in res.values())
        print(f"{'COMBINED':<8}{'':<6}{len(allt):>5}{tot:>12,.0f}"
              f"{tot/total:>7.2f}{'':>7}{'':>7}{cdd:>9.1f}")
        a, b = (monthly(res[s]["trades"], half) for s in ("ES", "NQ"))
        r, k = correl(a, b)
        worst = max(s["dd"] for s in res.values())
        print(f"\nES vs NQ monthly return correlation: "
              f"{'%+.3f' % r if r is not None else 'n/a'} over {k} months")
        print(f"worst single sleeve drawdown {worst:.1f}%  ->  combined {cdd:.1f}%")
        print(f"  (three Indian indices gave 0.035-0.698 and 29.4% -> 16.5%)")

        sh = []
        for kk in range(120):
            t = 0.0
            ok = True
            for sym in ("ES", "NQ"):
                r2 = sleeve(d, sym, half, shuffle=61000 + kk)
                if r2 is None:
                    ok = False
                    break
                t += r2[1]
            if ok:
                sh.append(t)
        if sh:
            sh.sort()
            pct = 100.0 * sum(1 for x in sh if x < tot) / len(sh)
            print(f"\ndirection-shuffled: median ${statistics.median(sh):,.0f} "
                  f"over {len(sh)} draws -> real portfolio at the "
                  f"{pct:.0f}th percentile")


if __name__ == "__main__":
    main()
