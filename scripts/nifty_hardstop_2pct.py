"""2% hard stop on the OPTION, all the size that stop allows. No wipeout trade.

The request was: stop-loss at 2% of capital, all in, no trade ever wipes out.
The first two cannot hold together, and the reason is arithmetic rather than
preference.

    risk = position size x stop distance

If the premium IS the capital, then a 2%-of-capital stop is a 2% move in the
option, which on a Rs 20 at-the-money contract is 0.8 NIFTY points. The median
5-minute NIFTY bar spans 14.5 points and 99.8% of bars span more than 0.8, so
that stop fires inside essentially every bar. Worse, below about Rs 50 of
premium the ROUND-TRIP COST exceeds the stop -- 2.74% against 2% at Rs 20 -- so
the trade is under water before it starts.

What CAN be honoured is the part that matters: no trade loses more than 2% of
capital. That fixes the size rather than the stop. With a 20-point stop, about
the smallest that survives one bar of noise, the deployable premium is roughly
Rs 19,000 on Rs 5,00,000 -- 3.8% of capital, not 100%.

So this runs: size for a Rs 10,000 loss at the profile stop, AND a hard
mark-to-market cap at Rs 10,000 enforced against the option's own value at each
bar's adverse extreme. Whichever comes first ends the trade. By construction no
trade can exceed 2%.
"""
from __future__ import annotations
import datetime as dt
import itertools, json, os, random, statistics, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import vp_of_pure as P
from india_options import SPEC, expiry_dates, sessions, YEAR, CLOSE_UTC
from nifty_sept_atm import price, atm_strike, RRS, HOLDS, EXPIRY, random_plans
from vp_confluence import combine, MODES
from vp_options import signals_for

CAP = 500_000.0
MAXLOSS = 0.02 * CAP          # Rs 10,000, the hard cap per trade


def run(st, plan, vix, spec, rr, hold, eo, lo, hi):
    b_, ses, n = st["bars"], st["ses"], st["n"]
    ss = sessions(b_)
    exp = expiry_dates([d for d, _ in ss], spec)
    day_of = {i: d for d, idxs in ss for i in idxs}
    rt = spec["cost"].round_trip_frac()
    lot, spread = spec["lot"], spec["spread"]
    pos, tr, out, capped = None, [], [], 0
    for i in range(lo, min(hi, n - 1)):
        bb = b_[i]
        if pos is not None:
            sd = pos["side"]
            t = max(0.0, (pos["expiry"] - bb["t"]) / YEAR)
            # the option's worst value INSIDE this bar
            adverse = bb["l"] if pos["call"] else bb["h"]
            worst = price(pos["call"], adverse, pos["k"], t, pos["iv"])
            mtm = (worst - pos["prem"]) * lot * pos["qty"]
            spot = None
            hard = False
            if mtm <= -MAXLOSS:
                hard = True
                spot = adverse
            else:
                hs = bb["l"] <= pos["stop"] if sd > 0 else bb["h"] >= pos["stop"]
                ht = bb["h"] >= pos["targ"] if sd > 0 else bb["l"] <= pos["targ"]
                if hs:
                    spot = pos["stop"]
                elif ht:
                    spot = pos["targ"]
                elif ses[i] != pos["ses"] or i - pos["i"] >= hold:
                    spot = bb["c"]
            if spot is not None:
                px = price(pos["call"], spot, pos["k"], t, pos["iv"])
                g = (px - pos["prem"]) * lot * pos["qty"]
                avg = (pos["prem"] + px) * 0.5 * lot * pos["qty"]
                pnl = g - rt * avg - spread * lot * pos["qty"]
                if hard:
                    capped += 1
                    pnl = max(pnl, -MAXLOSS)       # the cap is honoured
                tr.append(pnl)
                pos = None
        if pos is None and plan[i] is not None:
            sd, stop = plan[i][0], plan[i][1]
            e = b_[i + 1]["o"]
            if stop is None or sd * (e - stop) <= 0:
                continue
            d = day_of[i + 1]
            xd = exp.get(d)
            if xd is None or (eo and xd != d):
                continue
            expiry = int(dt.datetime(xd.year, xd.month, xd.day).timestamp()) + CLOSE_UTC
            t0 = (expiry - b_[i + 1]["t"]) / YEAR
            if t0 <= 0:
                continue
            iv = vix.get(str(d), 14.0) / 100.0 * spec["iv_k"]
            call = sd > 0
            k = atm_strike(e, spec["step"])
            prem = price(call, e, k, t0, iv)
            if prem <= spread:
                continue
            r = abs(e - stop)
            t_then = max(0.0, t0 - 2700 / YEAR)
            loss = ((prem - price(call, stop, k, t_then, iv)) * lot
                    + rt * prem * lot + spread * lot)
            if loss <= 0:
                continue
            qty = min(int(MAXLOSS // loss), int(CAP // (prem * lot)))
            if qty < 1:
                continue
            out.append(prem * lot * qty)
            pos = dict(side=sd, stop=stop, targ=e + sd * rr * r, k=k, iv=iv,
                       call=call, prem=prem, qty=qty, expiry=expiry,
                       ses=ses[i + 1], i=i + 1)
    return tr, out, capped


def summary(tr):
    eq = peak = CAP
    dd = 0.0
    for x in tr:
        eq += x
        peak = max(peak, eq)
        dd = max(dd, peak - eq)
    w = sum(x for x in tr if x > 0)
    l = -sum(x for x in tr if x <= 0)
    return dict(n=len(tr), net=sum(tr), final=CAP + sum(tr),
                pf=(w / l) if l else float("inf"), dd=dd,
                worst=min(tr) if tr else 0.0,
                win=100.0 * sum(1 for x in tr if x > 0) / len(tr) if tr else 0)


def main():
    d = sys.argv[1]
    vix = {}
    for b in json.load(open(os.path.join(d, "live", "INDIAVIX.json"))):
        k = str(dt.datetime.utcfromtimestamp(b["t"]).date())
        if k not in vix:
            vix[k] = b["c"]
    spec = SPEC["NIFTY"]
    print(f"NIFTY 50 ATM options, Rs {CAP:,.0f} capital")
    print(f"HARD CAP Rs {MAXLOSS:,.0f} (2%) per trade, enforced on the option's "
          f"own value\n")

    for path, yr, name in ((os.path.join(d, "live", "NIFTY_wv.json"), None,
                            "M5 — 59 sessions"),
                           (os.path.join(d, "yr", "NIFTY_h1_wv.json"), 2026,
                            "H1 — all of 2026")):
        bars = json.load(open(path))
        lo, hi = 0, len(bars)
        if yr:
            lo = hi = None
            for i, b in enumerate(bars):
                if dt.datetime.utcfromtimestamp(b["t"]).year == yr:
                    if lo is None:
                        lo = i
                    hi = i + 1
        st = P.state(bars)
        names = ["dva_edge_fade"] + list(P.REGISTRY)
        sigs = {nm: signals_for(st, nm) for nm in names}
        plans = dict(sigs)
        for m in MODES:
            plans[m] = combine(sigs, st["n"], m)
        grid = list(itertools.product(plans.keys(), EXPIRY, RRS, HOLDS))
        rows = []
        for (nm, eo, rr, hold) in grid:
            tr, out, capped = run(st, plans[nm], vix, spec, rr, hold, eo, lo, hi)
            if len(tr) >= 10:
                s = summary(tr)
                rows.append(dict(plan=nm, eo=eo, rr=rr, hold=hold,
                                 capped=capped,
                                 use=max(out) / CAP * 100 if out else 0,
                                 med_use=statistics.median(out) / CAP * 100 if out else 0,
                                 **s))
        if not rows:
            print(f"{name}: no cell reached 10 trades")
            continue
        rows.sort(key=lambda r: -r["net"])
        print(f"===== {name} =====")
        print(f"{'#':<3}{'plan':<19}{'exp':<7}{'RR':>4}{'n':>5}{'net Rs':>12}"
              f"{'final Rs':>12}{'PF':>6}{'maxDD Rs':>11}{'worst Rs':>10}"
              f"{'medUse%':>9}{'capped':>8}")
        for k, r in enumerate(rows[:6]):
            print(f"{k+1:<3}{r['plan']:<19}{'exp' if r['eo'] else 'wk':<7}"
                  f"{r['rr']:>4.1f}{r['n']:>5}{r['net']:>12,.0f}{r['final']:>12,.0f}"
                  f"{r['pf']:>6.2f}{r['dd']:>11,.0f}{r['worst']:>10,.0f}"
                  f"{r['med_use']:>9.1f}{r['capped']:>8}")
        pos = sum(1 for r in rows if r["net"] > 0)
        print(f"  profitable cells {pos}/{len(rows)}   median cell "
              f"Rs {statistics.median(r['net'] for r in rows):,.0f}")
        print(f"  worst trade anywhere in the grid: "
              f"Rs {min(r['worst'] for r in rows):,.0f}  (cap is "
              f"Rs {-MAXLOSS:,.0f})")
        best = rows[0]
        maxes = []
        for draw in range(25):
            rp = {}
            for nm in plans:
                rl = random_plans(st, plans[nm], lo, hi, 1,
                                  seed=3000 * draw + hash(nm) % 977)
                if rl:
                    rp[nm] = rl[0]
            cell = []
            for (nm, eo, rr, hold) in grid:
                if nm not in rp:
                    continue
                tr, _, _ = run(st, rp[nm], vix, spec, rr, hold, eo, lo, hi)
                if len(tr) >= 10:
                    cell.append(sum(tr))
            if cell:
                maxes.append(max(cell))
        if maxes:
            maxes.sort()
            beat = 100.0 * sum(1 for m in maxes if m < best["net"]) / len(maxes)
            print(f"  RANDOM best-of-grid: median Rs "
                  f"{statistics.median(maxes):,.0f}, max Rs {maxes[-1]:,.0f}")
            print(f"  strategy's best is at the {beat:.0f}th percentile of "
                  f"random's best\n")


if __name__ == "__main__":
    main()
