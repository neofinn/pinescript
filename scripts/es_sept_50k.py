"""ES, September 2026, $50,000, 5% risk per trade, compounding.

"All in with 5% risk" does not exist on futures and the arithmetic says why.
At $50,000 the two limits are nowhere near each other:

    5% risk, 20-point stop, MES   ->    24 contracts
    margin limit,            MES   ->  1000 contracts

Margin is forty times looser, so the risk rule binds every single time and the
all-in half never activates. What margin-limited size would actually mean is
1000 MES at $5,000 a point -- $34 million of notional on $50,000, where an
ordinary twenty-point move costs $100,000 and the broker liquidates long before
the stop is reached.

So the 5% rule binding is not a limitation of this test. It is the only thing
that makes the position survivable, and the run below is what the rules
actually produce.
"""
from __future__ import annotations
import datetime as dt
import json, os, statistics, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from futures_engine import CONTRACT, max_by_margin, size_for_risk
from futures_strategy import run, stats

START = 50_000.0


def september(fc):
    return [f for f in fc
            if dt.datetime.utcfromtimestamp(f["t"]).year == 2026
            and dt.datetime.utcfromtimestamp(f["t"]).month == 9]


def main():
    d = sys.argv[1]
    bars = json.load(open(os.path.join(d, "htf", "ES_m15.json")))
    fc = september(json.load(open(os.path.join(d, "htf_fc", "ES_m15.json"))))
    print(f"E-mini S&P, September 2026, 15-minute bars")
    print(f"${START:,.0f} start, 5% of live equity per trade, compounding, MES\n")
    print(f"  {len(fc)} non-overlapping forecasts in September")
    print(f"  5% of ${START:,.0f} = ${START*0.05:,.0f} risk per trade")
    print(f"  at a 20-point stop that is {size_for_risk('MES', START*0.05, 20)} "
          f"MES against a margin limit of {max_by_margin('MES', START):,} "
          f"-- the risk rule binds\n")

    print(f"{'RR':>5}{'gate':>6}{'n':>5}{'final $':>12}{'x':>7}{'PF':>7}"
          f"{'win%':>7}{'maxDD%':>9}{'shuffled med':>15}{'pct':>6}")
    cells = []
    for rr in (1.5, 2.0, 3.0):
        for gate in (False, True):
            tr, eq = run(bars, fc, "MES", START, rr=rr, use_gate=gate,
                         max_hold=16)
            s = stats(tr, START)
            if s is None or s["n"] < 10:
                print(f"{rr:>5.1f}{str(gate):>6}{(s['n'] if s else 0):>5}"
                      f"   below 10 trades")
                continue
            sh = []
            for k in range(200):
                t2, e2 = run(bars, fc, "MES", START, rr=rr, use_gate=gate,
                             max_hold=16, shuffle=52000 + k)
                if len(t2) >= 5:
                    sh.append(e2)
            sh.sort()
            pct = (100.0 * sum(1 for x in sh if x < s["final"]) / len(sh)
                   if sh else float("nan"))
            cells.append(pct)
            print(f"{rr:>5.1f}{str(gate):>6}{s['n']:>5}{s['final']:>12,.0f}"
                  f"{s['final']/START:>7.2f}{s['pf']:>7.2f}{s['win']:>7.1f}"
                  f"{s['dd']:>9.1f}"
                  f"{statistics.median(sh) if sh else 0:>15,.0f}{pct:>6.0f}",
                  flush=True)
    if cells:
        n = len(cells)
        print(f"\ncells above the 95th percentile: "
              f"{sum(1 for p in cells if p >= 95)}/{n}")
        print(f"expected best of {n} draws under the null: "
              f"{100.0*n/(n+1):.1f}th; observed best: {max(cells):.0f}")


if __name__ == "__main__":
    main()
