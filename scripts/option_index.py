"""The 62% signal, expressed as long ATM options instead of the index itself.

The signal's median hold is 23 trading days, longer than a monthly option's
useful life, so positions are rolled at expiry rather than assumed to survive.
"""
import json, os, datetime, sys
import fo_fetch as F

SC = os.path.dirname(os.path.abspath(__file__))
T = json.load(open(os.path.join(SC, "trades30.json")))
nifty = json.load(open("/home/user/pinescript/scripts/niftyd.json"))
SPOT = {datetime.datetime.fromtimestamp(b["t"], datetime.UTC).date(): b["c"] for b in nifty}
DAYS = sorted(SPOT)

def nextday(d):
    for x in DAYS:
        if x > d: return x
    return None

def px(d, sym, ot, exp, strike):
    """(price, was_traded) for one contract, or (None, _) if absent that day."""
    for r in F.chain(d, sym, ot, exp):
        if abs(r["strike"] - strike) < 1e-6:
            p = r["close"] if r["traded"] and r["close"] > 0 else r["settle"]
            return (p if p > 0 else None), r["traded"]
    return None, False

def atm(d, sym, ot, exp, spot, offset=0):
    """Strike `offset` steps out of the money from ATM, among strikes that
    actually traded. Offset walks up the ladder for calls and down for puts,
    by position rather than a fixed point step, since NIFTY's spacing widens
    away from the money and has changed over the years."""
    c = [r for r in F.chain(d, sym, ot, exp) if r["traded"] and r["close"] > 0]
    if not c: return None
    ks = sorted({r["strike"] for r in c})
    i = min(range(len(ks)), key=lambda j: abs(ks[j] - spot))
    j = i + offset if ot == "CE" else i - offset
    if j < 0 or j >= len(ks): return None
    return ks[j]

def oi_at(d, sym, ot, exp, strike):
    for r in F.chain(d, sym, ot, exp):
        if abs(r["strike"] - strike) < 1e-6: return r["oi"]
    return 0.0

def chain_oi(d, sym, exp):
    """(call OI, put OI) across the whole expiry -- the basis for PCR."""
    ce = sum(r["oi"] for r in F.chain(d, sym, "CE", exp))
    pe = sum(r["oi"] for r in F.chain(d, sym, "PE", exp))
    return ce, pe

def pick_exp(d, sym, min_days=7):
    for e in F.monthly_expiries(d, sym):
        if (e - d).days >= min_days: return e
    return None

def leg(entry, exitd, ot, sym="NIFTY", verbose=False, offset=0):
    """Walk the position, rolling at each expiry. Returns % return on premium."""
    cur, legs, settle_used = entry, [], 0
    guard = 0
    while cur < exitd and guard < 12:
        guard += 1
        exp = pick_exp(cur, sym)
        if exp is None: return None, "no expiry", 0
        spot = SPOT.get(cur)
        if spot is None: return None, "no spot", 0
        k = atm(cur, sym, ot, exp, spot, offset)
        if k is None: return None, f"no ATM {cur}", 0
        pin, tr_in = px(cur, sym, ot, exp, k)
        if pin is None: return None, f"no entry px {cur}", 0
        if not tr_in: settle_used += 1
        close_on = min(exp, exitd)
        # find a day the contract is priceable, walking back from the target
        pout, day = None, close_on
        for _ in range(6):
            pout, tr = px(day, sym, ot, exp, k)
            if pout is not None:
                if not tr: settle_used += 1
                break
            prev = [x for x in DAYS if x < day]
            if not prev: break
            day = prev[-1]
        if pout is None:
            # expired: settle at intrinsic against spot
            s = SPOT.get(close_on) or SPOT.get([x for x in DAYS if x <= close_on][-1])
            pout = max(0.0, (s - k) if ot == "CE" else (k - s))
        legs.append((cur, close_on, k, pin, pout))
        if verbose: print(f"     {cur} -> {close_on}  K={k:.0f}  {pin:.2f} -> {pout:.2f}  ({(pout/pin-1)*100:+.0f}%)")
        if close_on >= exitd: break
        nd = nextday(close_on)
        if nd is None or nd > exitd: break
        cur = nd
    if not legs: return None, "no legs", 0
    # Return on premium OUTLAID. Compounding proceeds into each next leg would
    # model an all-in parlay, where one expiry at zero erases every prior win;
    # a fixed premium per roll is what a position actually costs to carry.
    paid = sum(pin for (_, _, _, pin, _) in legs)
    got  = sum(pout for (_, _, _, _, pout) in legs)
    return (got - paid) / paid * 100, legs, settle_used

if __name__ == "__main__":
    only = sys.argv[1] if len(sys.argv) > 1 else None
    print("NIFTY ATM OPTIONS on the 62% signal (rvol-breadth>30%)")
    print("long -> buy ATM call, short -> buy ATM put; rolled at each monthly expiry\n")
    print(f"{'dir':>5} {'entry':>11} {'exit':>11} {'idx move%':>10} {'idx R':>7} {'rolls':>6} {'opt %':>9}")
    res = []
    for t in T:
        if only and not t["entry"].startswith(only): continue
        e = datetime.date.fromisoformat(t["entry"]); x = datetime.date.fromisoformat(t["exit"])
        ot = "CE" if t["dir"] > 0 else "PE"
        try:
            r, legs, su = leg(e, x, ot)
        except Exception as ex:
            print(f"{'L' if t['dir']>0 else 'S':>5} {t['entry']:>11} {t['exit']:>11}   ERROR {type(ex).__name__} {ex}")
            continue
        if r is None:
            print(f"{'L' if t['dir']>0 else 'S':>5} {t['entry']:>11} {t['exit']:>11} {t['pct']:>+10.2f} {t['R']:>+7.2f}   -- {legs}")
            continue
        res.append(dict(t=t, opt=r, rolls=len(legs), settle=su))
        print(f"{'L' if t['dir']>0 else 'S':>5} {t['entry']:>11} {t['exit']:>11} {t['pct']:>+10.2f} {t['R']:>+7.2f} {len(legs):>6} {r:>+8.1f}%")
    json.dump([{**{k: v for k, v in d.items() if k != 't'}, **d["t"]} for d in res],
              open(os.path.join(SC, "optres.json"), "w"), indent=1)
    if res:
        w = [d for d in res if d["opt"] > 0]
        print(f"\n  {len(res)} priced   win {len(w)/len(res)*100:.1f}%   "
              f"mean {sum(d['opt'] for d in res)/len(res):+.1f}%   "
              f"settlement-priced legs {sum(d['settle'] for d in res)}")
