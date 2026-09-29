"""September 2026, NIFTY 50, ATM option buying — the best configuration, and
what "best" is worth.

The request is to maximise reward. That is a legitimate thing to want and this
script does it: 160 configurations, the winner reported. But a maximum taken
over 160 cells is the maximum of 160 draws, and on 20 sessions the spread of
those draws is wide. Quoting the winner alone would be the single most
misleading number this project could produce.

So three things are reported beside it:

  RANDOM GRID   the identical 160-cell grid run on random entries carrying the
                strategy's own stop distances. Its maximum is what searching
                160 cells buys you when there is nothing to find. The
                strategy's max has to beat THAT, not beat zero.
  MATCHED n     a control at the winner's own trade count, because 20 sessions
                of an intraday signal is a small number of trades and profit
                factor on small samples runs hot.
  AUGUST        the September winner applied, unchanged, to August. One month
                is not evidence; a configuration that only works in the month
                it was chosen from is the definition of the problem.

ATM is taken literally as 0.50 delta, which removes the strike axis from the
search rather than letting it be tuned.
"""
from __future__ import annotations
import datetime as dt
import itertools, json, os, random, statistics, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import india_volume as IV
import vp_of_pure as P
from hft.pricing import bs_call, bs_put, bs_delta_call, bs_delta_put
from india_options import SPEC, expiry_dates, sessions, YEAR, RF, CLOSE_UTC
from vp_confluence import combine, MODES
from vp_options import signals_for

EQUITY = 500_000.0
RISK = 5_000.0
MAX_PREM = 0.25
DELTA_ATM = 0.50          # "ATM" is not a free parameter
HOLD_SEC = 45 * 60        # assumed hold for ex-ante sizing


def price(is_call, s, k, t, iv):
    return bs_call(s, k, t, iv, RF) if is_call else bs_put(s, k, t, iv, RF)


def atm_strike(spot, step):
    return round(spot / step) * step


def run(st, plan, vixmap, spec, rr, max_hold, expiry_only, lo, hi):
    bars, ses, n = st["bars"], st["ses"], st["n"]
    ss = sessions(bars)
    days = [d for d, _ in ss]
    exp = expiry_dates(days, spec)
    day_of = {i: d for d, idxs in ss for i in idxs}
    rt = spec["cost"].round_trip_frac()
    lot, spread = spec["lot"], spec["spread"]
    trades, pos = [], None
    for i in range(lo, min(hi, n - 1)):
        b = bars[i]
        if pos is not None:
            sd = pos["side"]
            hit_s = b["l"] <= pos["stop"] if sd > 0 else b["h"] >= pos["stop"]
            hit_t = b["h"] >= pos["targ"] if sd > 0 else b["l"] <= pos["targ"]
            spot = None
            if hit_s:
                spot = pos["stop"]
            elif hit_t:
                spot = pos["targ"]
            elif ses[i] != pos["ses"] or i - pos["i"] >= max_hold:
                spot = b["c"]
            if spot is not None:
                t = max(0.0, (pos["expiry"] - b["t"]) / YEAR)
                px = price(pos["call"], spot, pos["k"], t, pos["iv"])
                gross = (px - pos["prem"]) * lot * pos["qty"]
                avg = (pos["prem"] + px) * 0.5 * lot * pos["qty"]
                trades.append(gross - rt * avg - spread * lot * pos["qty"])
                pos = None
        if pos is None and plan[i] is not None:
            sd, stop = plan[i][0], plan[i][1]
            e = bars[i + 1]["o"]
            if stop is None or sd * (e - stop) <= 0:
                continue
            d = day_of[i + 1]
            xd = exp.get(d)
            if xd is None or (expiry_only and xd != d):
                continue
            expiry = int(dt.datetime(xd.year, xd.month, xd.day).timestamp()) + CLOSE_UTC
            t0 = (expiry - bars[i + 1]["t"]) / YEAR
            if t0 <= 0:
                continue
            iv = vixmap.get(str(d), 14.0) / 100.0 * spec["iv_k"]
            call = sd > 0
            k = atm_strike(e, spec["step"])
            prem = price(call, e, k, t0, iv)
            if prem <= spread:
                continue
            r = abs(e - stop)
            t_then = max(0.0, t0 - HOLD_SEC / YEAR)
            loss = ((prem - price(call, stop, k, t_then, iv)) * lot
                    + rt * prem * lot + spread * lot)
            if loss <= 0:
                continue
            qty = min(int(RISK // loss), int(EQUITY * MAX_PREM // (prem * lot)))
            if qty < 1:
                continue
            pos = dict(side=sd, stop=stop, targ=e + sd * rr * r, k=k, iv=iv,
                       call=call, prem=prem, qty=qty, expiry=expiry,
                       ses=ses[i + 1], i=i + 1)
    return trades


def stats(tr):
    if not tr:
        return None
    w = sum(x for x in tr if x > 0)
    l = -sum(x for x in tr if x <= 0)
    eq = peak = EQUITY
    dd = 0.0
    for x in tr:
        eq += x
        peak = max(peak, eq)
        dd = max(dd, (peak - eq) / peak)
    return dict(n=len(tr), net=sum(tr), pf=(w / l) if l else float("inf"),
                win=100.0 * sum(1 for x in tr if x > 0) / len(tr),
                dd=dd * 100, med=statistics.median(tr),
                rdd=(sum(tr) / EQUITY * 100) / (dd * 100) if dd > 0 else float("inf"))


RRS = (1.0, 1.5, 2.0, 3.0)
HOLDS = (10_000, 24)            # session-end only, or 2 hours (24 x 5m bars)
EXPIRY = (False, True)          # nearest weekly, or expiry day only


def month_window(bars, year, month):
    lo = hi = None
    for i, b in enumerate(bars):
        d = dt.datetime.utcfromtimestamp(b["t"])
        if d.year == year and d.month == month:
            if lo is None:
                lo = i
            hi = i + 1
    return lo, hi


def random_plans(st, plan, lo, hi, draws, seed):
    """Random timing and direction, the plan's own stop distances."""
    dists = [abs(st["bars"][i]["c"] - p[1]) for i, p in enumerate(plan)
             if p and p[1] is not None and lo <= i < hi]
    if not dists:
        return []
    rng = random.Random(seed)
    out = []
    for _ in range(draws):
        rp = [None] * st["n"]
        for i in range(lo, min(hi, st["n"]) - 1):
            sd = rng.choice((-1, 1))
            c = st["bars"][i]["c"]
            rp[i] = (sd, c - sd * dists[rng.randrange(len(dists))], None)
        out.append(rp)
    return out


def main():
    d = sys.argv[1]
    st = P.state(IV.with_volume(d, "NIFTY"))
    # India VIX at the session's FIRST observation. Taking the day's last
    # value would price a 10am option with a number only known at 15:30 --
    # a small leak, and one that lands on exactly the days that moved most.
    vix = {}
    for b in json.load(open(os.path.join(d, "INDIAVIX.json"))):
        k = str(dt.datetime.utcfromtimestamp(b["t"]).date())
        if k not in vix:
            vix[k] = b["c"]
    spec = SPEC["NIFTY"]
    names = ["dva_edge_fade"] + list(P.REGISTRY)
    sigs = {nm: signals_for(st, nm) for nm in names}
    plans = dict(sigs)
    for m in MODES:
        plans[m] = combine(sigs, st["n"], m)

    sep = month_window(st["bars"], 2026, 9)
    aug = month_window(st["bars"], 2026, 8)
    grid = list(itertools.product(plans.keys(), EXPIRY, RRS, HOLDS))
    print(f"NIFTY 50, September 2026, ATM (0.50 delta) option buying")
    print(f"capital Rs {EQUITY:,.0f}, risk Rs {RISK:,.0f}/trade, "
          f"lot {spec['lot']}, {spec['step']:.0f}-pt strikes")
    print(f"grid: {len(plans)} plans x {len(EXPIRY)} expiry x {len(RRS)} RR "
          f"x {len(HOLDS)} hold = {len(grid)} configurations\n")

    rows = []
    for (nm, eo, rr, hold) in grid:
        tr = run(st, plans[nm], vix, spec, rr, hold, eo, *sep)
        s = stats(tr)
        if s and s["n"] >= 5:
            rows.append(dict(plan=nm, expiry_only=eo, rr=rr, hold=hold, **s))
    rows.sort(key=lambda r: -r["net"])

    print(f"{'#':<3}{'plan':<19}{'expiry':<8}{'RR':>4}{'hold':>6}{'n':>5}"
          f"{'net Rs':>11}{'PF':>7}{'win%':>6}{'maxDD%':>8}{'ret/DD':>8}")
    for k, r in enumerate(rows[:10]):
        print(f"{k+1:<3}{r['plan']:<19}{'expiry' if r['expiry_only'] else 'weekly':<8}"
              f"{r['rr']:>4.1f}{('none' if r['hold']>1000 else str(r['hold'])):>6}"
              f"{r['n']:>5}{r['net']:>11,.0f}{r['pf']:>7.2f}{r['win']:>6.1f}"
              f"{r['dd']:>8.1f}{r['rdd']:>8.2f}")

    best = rows[0]
    print(f"\nprofitable cells: {sum(1 for r in rows if r['net'] > 0)}/{len(rows)}")
    print(f"median cell net: Rs {statistics.median(r['net'] for r in rows):,.0f}")

    # --- what does searching 160 cells buy when there is nothing to find? ---
    print(f"\n=== the same grid on RANDOM entries ===")
    # Random must get the SAME search breadth, or the comparison is rigged in
    # the strategy's favour: one random plan reused across the grid varies only
    # execution (16 distinct cells), while the strategy varies signal too (160).
    # So each plan slot gets its OWN random plan, per draw.
    maxes = []
    for draw in range(40):
        rp_by_plan = {}
        for nm in plans:
            rl = random_plans(st, plans[nm], sep[0], sep[1], 1,
                              seed=1000 * draw + hash(nm) % 997)
            if rl:
                rp_by_plan[nm] = rl[0]
        cell = []
        for (nm, eo, rr, hold) in grid:
            rp = rp_by_plan.get(nm)
            if rp is None:
                continue
            tr = run(st, rp, vix, spec, rr, hold, eo, *sep)
            s = stats(tr)
            if s and s["n"] >= 5:
                cell.append(s["net"])
        if cell:
            maxes.append(max(cell))
    maxes.sort()
    if maxes:
        print(f"  best-of-grid on random, {len(maxes)} draws:")
        print(f"    median Rs {statistics.median(maxes):,.0f}   "
              f"90th Rs {maxes[int(len(maxes)*0.9)]:,.0f}   "
              f"max Rs {maxes[-1]:,.0f}")
        beat = 100.0 * sum(1 for m in maxes if m < best["net"]) / len(maxes)
        print(f"  the strategy's best (Rs {best['net']:,.0f}) sits at the "
              f"{beat:.0f}th percentile of random's best")

    # --- the winner, unchanged, in August ---
    print(f"\n=== September's winner applied to August ===")
    tr = run(st, plans[best["plan"]], vix, spec, best["rr"], best["hold"],
             best["expiry_only"], *aug)
    a = stats(tr)
    if a:
        print(f"  {best['plan']} rr={best['rr']} "
              f"{'expiry-day' if best['expiry_only'] else 'weekly'}: "
              f"n={a['n']}  net Rs {a['net']:,.0f}  PF {a['pf']:.2f}  "
              f"maxDD {a['dd']:.1f}%")
    json.dump(rows, open(os.path.join(d, "nifty_sept_grid.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
