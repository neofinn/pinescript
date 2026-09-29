"""Total balance split three ways at the start of every trading day.

Independent sleeves let a winner compound away and a loser shrink to nothing.
Daily rebalancing does the opposite: each morning the whole account is divided
equally again, so capital flows out of whatever just won and into whatever just
lost. That is a real and different strategy, not an accounting detail, and with
one sleeve at 3.84x and another at 1.02x it will move the total a long way.

HOW THE REPLAY WORKS, AND WHY IT IS CHECKED. Each trade is recorded with the
equity it was sized against, so its RETURN (pnl / equity at entry) can be
applied to a different capital level. Position size is an integer number of
lots, so that proportionality is approximate. The replay is therefore validated
first by running it with rebalancing OFF and comparing against the true
independent run; if the two do not agree closely the approximation is not good
enough to trust and the rebalanced figure would be meaningless.
"""
from __future__ import annotations
import datetime as dt
import json, os, statistics, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from portfolio_3index import sleeve, SLEEVE, IDX

TOTAL = 3 * SLEEVE


def to_returns(dated):
    """[(date, pnl, eq_at_entry)] -> [(date, return_fraction)]"""
    return [(d, p / e) for d, p, e in dated if e > 0]


def replay(per_sleeve, rebalance):
    """Walk the calendar; optionally reset each sleeve to total/3 each morning.

    Returns (final total, max drawdown %, daily equity path).
    """
    names = list(per_sleeve)
    days = sorted({d for s in names for d, _ in per_sleeve[s]})
    eq = {s: TOTAL / len(names) for s in names}
    peak = TOTAL
    dd = 0.0
    path = []
    for day in days:
        if rebalance:
            tot = sum(eq.values())
            for s in names:
                eq[s] = tot / len(names)
        for s in names:
            for d, r in per_sleeve[s]:
                if d == day:
                    eq[s] = max(0.0, eq[s] * (1 + r))
        tot = sum(eq.values())
        peak = max(peak, tot)
        dd = max(dd, (peak - tot) / peak)
        path.append((day, tot))
    return sum(eq.values()), dd * 100, path


def main():
    d = sys.argv[1]
    raw, per = {}, {}
    for nm in IDX:
        r = sleeve(d, nm)
        if r is None:
            continue
        raw[nm] = r
        per[nm] = to_returns(r[2])
    if len(per) < 2:
        print("not enough sleeves")
        return

    truth = sum(raw[nm][1] for nm in raw)
    flat, fdd, _ = replay(per, rebalance=False)
    err = abs(flat - truth) / truth * 100
    print("VALIDATION — replay with rebalancing off vs the true independent run")
    print(f"  true independent total  Rs {truth:,.0f}")
    print(f"  replayed, no rebalance  Rs {flat:,.0f}   ({err:.2f}% error)")
    if err > 5:
        print("  replay does not track the engine closely enough; "
              "rebalanced figures below are unreliable")
    else:
        print("  replay tracks; the rebalanced figure below is trustworthy\n")

    reb, rdd, rpath = replay(per, rebalance=True)
    print(f"{'scheme':<34}{'final Rs':>15}{'x':>8}{'maxDD%':>9}")
    print(f"{'independent sleeves (no rebal)':<34}{flat:>15,.0f}"
          f"{flat/TOTAL:>8.2f}{fdd:>9.1f}")
    print(f"{'rebalanced to 1/3 every morning':<34}{reb:>15,.0f}"
          f"{reb/TOTAL:>8.2f}{rdd:>9.1f}")
    print(f"\nper-sleeve standalone (for reference):")
    for nm in raw:
        print(f"  {nm:<12}{raw[nm][1]:>14,.0f}  {raw[nm][1]/SLEEVE:.2f}x  "
              f"{len(per[nm])} trades")

    # what rebalancing costs or earns, and why
    print(f"\nrebalancing changed the total by "
          f"{(reb - flat) / flat * 100:+.1f}% and the drawdown by "
          f"{rdd - fdd:+.1f} points")
    best = max(raw, key=lambda n: raw[n][1])
    worst = min(raw, key=lambda n: raw[n][1])
    print(f"  it repeatedly moved capital out of {best} "
          f"({raw[best][1]/SLEEVE:.2f}x) and into {worst} "
          f"({raw[worst][1]/SLEEVE:.2f}x)")

    # control: same scheme, directions shuffled
    sh = []
    for k in range(60):
        p2 = {}
        ok = True
        for nm in IDX:
            r2 = sleeve(d, nm, shuffle=77000 + k)
            if r2 is None:
                ok = False
                break
            p2[nm] = to_returns(r2[2])
        if ok:
            sh.append(replay(p2, rebalance=True)[0])
    if sh:
        sh.sort()
        pct = 100.0 * sum(1 for x in sh if x < reb) / len(sh)
        print(f"\ndirection-shuffled, rebalanced: median Rs "
              f"{statistics.median(sh):,.0f}  over {len(sh)} draws")
        print(f"the real rebalanced portfolio sits at the {pct:.0f}th percentile")
        print(f"  (60 draws still only pins this to roughly +/-8 points; "
              f"25 draws spanned 64-92 on the previous run)")


if __name__ == "__main__":
    main()
