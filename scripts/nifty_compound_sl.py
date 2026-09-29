"""Stop at X% of COMPOUNDED capital. No trade may exceed it.

Two corrections over the previous run, both found by the table disagreeing with
its own promise -- it printed a worst trade of -Rs 33,142 under a Rs 10,000 cap:

  COSTS WERE OUTSIDE THE CAP. The trigger compared the option's mark-to-market
  against the limit, then subtracted spread and statutory charges afterwards,
  so every capped trade breached by the cost. The check now includes them.

  ONLY ONE EXIT PATH WAS FLOORED. The floor was applied when the hard stop
  fired but not when the profile stop, the target or the bell closed the trade,
  so a position sized off a tiny modelled stop could lose far more through
  those routes. Every exit is floored now.

And the risk base COMPOUNDS: the limit is X% of equity as it stands when the
trade opens, not X% of the opening balance. After a loss the next trade is
smaller, which is the property that makes ruin approach zero asymptotically
rather than arriving.
"""
from __future__ import annotations
import datetime as dt
import itertools, json, os, statistics, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import vp_of_pure as P
from india_options import SPEC, expiry_dates, sessions, YEAR, CLOSE_UTC
from nifty_sept_atm import price, atm_strike, RRS, HOLDS, EXPIRY, random_plans
from vp_confluence import combine, MODES
from vp_options import signals_for

CAP0 = 500_000.0


def run(st, plan, vix, spec, rr, hold, eo, lo, hi, sl_frac):
    b_, ses, n = st["bars"], st["ses"], st["n"]
    ss = sessions(b_)
    exp = expiry_dates([d for d, _ in ss], spec)
    day_of = {i: d for d, idxs in ss for i in idxs}
    rt = spec["cost"].round_trip_frac()
    lot, spread = spec["lot"], spec["spread"]
    eq = CAP0
    pos, tr, use, capped, breach = None, [], [], 0, 0
    raw = []
    for i in range(lo, min(hi, n - 1)):
        bb = b_[i]
        if pos is not None:
            sd = pos["side"]
            t = max(0.0, (pos["expiry"] - bb["t"]) / YEAR)
            adverse = bb["l"] if pos["call"] else bb["h"]
            worst = price(pos["call"], adverse, pos["k"], t, pos["iv"])
            cost_at = lambda px: (rt * (pos["prem"] + px) * 0.5 * lot * pos["qty"]
                                  + spread * lot * pos["qty"])
            # costs are INSIDE the limit, not added after it
            mtm = (worst - pos["prem"]) * lot * pos["qty"] - cost_at(worst)
            spot, hard = None, False
            if mtm <= -pos["limit"]:
                spot, hard = adverse, True
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
                pnl = (px - pos["prem"]) * lot * pos["qty"] - cost_at(px)
                if pnl < -pos["limit"]:
                    breach += 1
                if hard:
                    capped += 1
                raw.append(pnl)
                # The floor is an ASSUMPTION: it says the stop always fills at
                # exactly the limit. When the option gapped through it inside a
                # bar that is not true, and `breach` counts how often. Both the
                # floored and the raw series are returned so the size of the
                # assumption is visible rather than buried.
                pnl = max(pnl, -pos["limit"])
                tr.append(pnl)
                eq = max(0.0, eq + pnl)
                pos = None
        if pos is None and eq > 0 and plan[i] is not None:
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
            limit = sl_frac * eq                 # X% of LIVE equity
            r = abs(e - stop)
            t_then = max(0.0, t0 - 2700 / YEAR)
            loss = ((prem - price(call, stop, k, t_then, iv)) * lot
                    + rt * prem * lot + spread * lot)
            if loss <= 0:
                continue
            qty = min(int(limit // loss), int(eq // (prem * lot)))
            if qty < 1:
                continue
            use.append(prem * lot * qty / eq * 100)
            pos = dict(side=sd, stop=stop, targ=e + sd * rr * r, k=k, iv=iv,
                       call=call, prem=prem, qty=qty, expiry=expiry,
                       ses=ses[i + 1], i=i + 1, limit=limit)
    # replay the raw (unfloored) series to get the equity a real fill gives
    eq_raw = CAP0
    for x in raw:
        eq_raw = max(0.0, eq_raw + x * (eq_raw / CAP0 if False else 1.0))
    return tr, use, capped, breach, eq, raw, eq_raw


def summary(tr, eq):
    e = peak = CAP0
    dd = 0.0
    for x in tr:
        e += x
        peak = max(peak, e)
        dd = max(dd, (peak - e) / peak)
    w = sum(x for x in tr if x > 0)
    l = -sum(x for x in tr if x <= 0)
    return dict(n=len(tr), final=eq, pf=(w / l) if l else float("inf"),
                dd=dd * 100, worst=min(tr) if tr else 0.0,
                win=100.0 * sum(1 for x in tr if x > 0) / len(tr) if tr else 0)


def main():
    d = sys.argv[1]
    vix = {}
    for b in json.load(open(os.path.join(d, "live", "INDIAVIX.json"))):
        k = str(dt.datetime.utcfromtimestamp(b["t"]).date())
        if k not in vix:
            vix[k] = b["c"]
    spec = SPEC["NIFTY"]
    print(f"NIFTY 50 ATM options, Rs {CAP0:,.0f} start, risk COMPOUNDS off live equity")
    print(f"hard cap per trade enforced on the option, costs included\n")

    for path, yr, name in ((os.path.join(d, "live", "NIFTY_wv.json"), None,
                            "M5 - 59 sessions"),
                           (os.path.join(d, "yr", "NIFTY_h1_wv.json"), 2026,
                            "H1 - all of 2026")):
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
        print(f"===== {name} =====")
        print(f"{'SL%':<6}{'best plan':<19}{'exp':<5}{'RR':>4}{'n':>5}"
              f"{'final Rs':>14}{'x':>7}{'PF':>7}{'maxDD%':>8}{'worst Rs':>11}"
              f"{'medUse%':>9}{'gapped':>9}")
        for sl, slab in ((0.02, "2%"), (0.05, "5%"), (0.10, "10%")):
            rows = []
            for (nm, eo, rr, hold) in grid:
                tr, use, capped, breach, eq, raw, eq_raw = run(
                    st, plans[nm], vix, spec, rr, hold, eo, lo, hi, sl)
                if len(tr) >= 10:
                    s = summary(tr, eq)
                    rows.append(dict(plan=nm, eo=eo, rr=rr, capped=capped,
                                     breach=breach, eq_raw=eq_raw,
                                     raw_worst=min(raw) if raw else 0.0,
                                     use=statistics.median(use) if use else 0,
                                     **s))
            if not rows:
                print(f"{slab:<6}  no cell reached 10 trades")
                continue
            rows.sort(key=lambda r: -r["final"])
            b = rows[0]
            pos = sum(1 for r in rows if r["final"] > CAP0)
            print(f"{slab:<6}{b['plan']:<19}{'exp' if b['eo'] else 'wk':<5}"
                  f"{b['rr']:>4.1f}{b['n']:>5}{b['final']:>14,.0f}"
                  f"{b['final']/CAP0:>7.2f}{b['pf']:>7.2f}{b['dd']:>8.1f}"
                  f"{b['worst']:>11,.0f}{b['use']:>9.1f}"
                  f"{b['breach']}/{b['n']:<8}")
            print(f"      if the stop does NOT always fill at the limit: "
                  f"Rs {b['eq_raw']:,.0f} ({b['eq_raw']/CAP0:.2f}x), "
                  f"worst single trade Rs {b['raw_worst']:,.0f}")
            print(f"      profitable cells {pos}/{len(rows)}   median cell "
                  f"Rs {statistics.median(r['final'] for r in rows):,.0f}   "
                  f"worst trade in grid Rs {min(r['worst'] for r in rows):,.0f}")
        # control at the middle setting
        maxes = []
        for draw in range(20):
            rp = {}
            for nm in plans:
                rl = random_plans(st, plans[nm], lo, hi, 1,
                                  seed=5000 * draw + hash(nm) % 971)
                if rl:
                    rp[nm] = rl[0]
            cell = []
            for (nm, eo, rr, hold) in grid:
                if nm not in rp:
                    continue
                tr, _, _, _, eq, _, _ = run(st, rp[nm], vix, spec, rr, hold,
                                            eo, lo, hi, 0.05)
                if len(tr) >= 10:
                    cell.append(eq)
            if cell:
                maxes.append(max(cell))
        if maxes:
            maxes.sort()
            print(f"      RANDOM best-of-grid at 5% SL: median Rs "
                  f"{statistics.median(maxes):,.0f}, max Rs {maxes[-1]:,.0f}\n")


if __name__ == "__main__":
    main()
