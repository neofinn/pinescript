"""The same signal, expressed as ATM options on the underlying constituents.

At each index signal we buy ATM options on the stocks that actually fired the
gate -- the ones trading at more than 1.5x their own 20-day volume -- equally
weighted, rolled at expiry exactly as the index leg is.
"""
import json, os, glob, datetime
import fo_fetch as F
import option_index as O

SC = os.path.dirname(os.path.abspath(__file__))

def stock_rvol_on(dates):
    """{date: [(sym, spot)]} for constituents with rvol>1.5 that day."""
    hits = {d: [] for d in dates}
    for p in sorted(glob.glob(os.path.join(SC, "n50", "*.json"))):
        sym = os.path.basename(p)[:-5]
        bars = json.load(open(p))
        V = [b["v"] for b in bars]
        for i, b in enumerate(bars):
            if i < 21: continue
            d = datetime.datetime.fromtimestamp(b["t"], datetime.UTC).date()
            if d not in hits: continue
            w = V[i-20:i]; m = sum(w)/len(w) if w else 0
            if m > 0 and V[i]/m > 1.5:
                hits[d].append((sym, b["c"]))
    return hits

def stock_spot_series():
    out = {}
    for p in sorted(glob.glob(os.path.join(SC, "n50", "*.json"))):
        sym = os.path.basename(p)[:-5]
        out[sym] = {datetime.datetime.fromtimestamp(b["t"], datetime.UTC).date(): b["c"]
                    for b in json.load(open(p))}
    return out

SPOTS = stock_spot_series()

def leg_stock(sym, entry, exitd, ot):
    """Same roll walk as the index leg, against this stock's own chain."""
    sp = SPOTS.get(sym, {})
    cur, legs, settle_used, guard = entry, [], 0, 0
    while cur < exitd and guard < 12:
        guard += 1
        exp = O.pick_exp(cur, sym)
        if exp is None: return None, "no expiry", 0
        spot = sp.get(cur)
        if spot is None: return None, "no spot", 0
        k = O.atm(cur, sym, ot, exp, spot)
        if k is None: return None, "no ATM", 0
        pin, tr = O.px(cur, sym, ot, exp, k)
        if pin is None or pin <= 0: return None, "no entry px", 0
        if not tr: settle_used += 1
        close_on = min(exp, exitd)
        pout, day = None, close_on
        for _ in range(6):
            pout, tr2 = O.px(day, sym, ot, exp, k)
            if pout is not None:
                if not tr2: settle_used += 1
                break
            prev = [x for x in O.DAYS if x < day]
            if not prev: break
            day = prev[-1]
        if pout is None:
            s = sp.get(close_on)
            if s is None:
                ds = [x for x in sorted(sp) if x <= close_on]
                s = sp[ds[-1]] if ds else None
            if s is None: return None, "no settle spot", 0
            pout = max(0.0, (s - k) if ot == "CE" else (k - s))
        legs.append((pin, pout))
        if close_on >= exitd: break
        nd = O.nextday(close_on)
        if nd is None or nd > exitd: break
        cur = nd
    if not legs: return None, "no legs", 0
    paid = sum(p for p, _ in legs); got = sum(o for _, o in legs)
    return (got - paid) / paid * 100, legs, settle_used

if __name__ == "__main__":
    T = O.T
    sig_dates = [datetime.date.fromisoformat(t["entry"]) for t in T]
    hits = stock_rvol_on(sig_dates)
    print("UNDERLYING ATM OPTIONS — basket of the constituents that fired the gate\n")
    print(f"{'dir':>5} {'entry':>11} {'exit':>11} {'idx R':>7} {'names':>6} {'priced':>7} {'basket %':>10}")
    rows = []
    for t in T:
        e = datetime.date.fromisoformat(t["entry"]); x = datetime.date.fromisoformat(t["exit"])
        ot = "CE" if t["dir"] > 0 else "PE"
        names = hits.get(e, [])
        rr, bad = [], 0
        for sym, _ in names:
            try: r, _l, _s = leg_stock(sym, e, x, ot)
            except Exception: r = None
            if r is None: bad += 1
            else: rr.append(r)
        if not rr:
            print(f"{'L' if t['dir']>0 else 'S':>5} {t['entry']:>11} {t['exit']:>11} {t['R']:>+7.2f} "
                  f"{len(names):>6} {0:>7}   no options listed"); continue
        b = sum(rr)/len(rr)
        rows.append(dict(entry=t["entry"], R=t["R"], dir=t["dir"], basket=b, n=len(rr)))
        print(f"{'L' if t['dir']>0 else 'S':>5} {t['entry']:>11} {t['exit']:>11} {t['R']:>+7.2f} "
              f"{len(names):>6} {len(rr):>7} {b:>+9.1f}%")
    json.dump(rows, open(os.path.join(SC, "optstockres.json"), "w"), indent=1)
    if rows:
        w = [r for r in rows if r["basket"] > 0]
        print(f"\n  {len(rows)} signals priced   win {len(w)/len(rows)*100:.1f}%   "
              f"mean {sum(r['basket'] for r in rows)/len(rows):+.1f}%")
