"""Three structural fixes for premium-eats-the-edge, measured rather than argued.

1. Debit spreads. Long ATM, short ATM+2 caps the payoff but roughly halves the
   cost. Since the median winner moves 1.79% and ATM+2 sits about that far out,
   the cap may cost less than the premium saved.
2. A premium-aware entry filter. Skip signals where the option costs too much
   relative to the move the strategy is actually playing for (1R = 3x ATR),
   which is a different question from whether IV is high in the abstract.
3. No rolling. Close at the first expiry instead of paying premium again on a
   hold whose median already outlives a monthly option.
"""
import sys, os, json, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import option_index as O

SC = os.path.dirname(os.path.abspath(__file__))

def atr_series(bars, n=14):
    H=[b["h"] for b in bars]; L=[b["l"] for b in bars]; C=[b["c"] for b in bars]
    tr=[H[0]-L[0]]+[max(H[i]-L[i],abs(H[i]-C[i-1]),abs(L[i]-C[i-1])) for i in range(1,len(H))]
    out=[None]*len(H); s=None
    for i,t in enumerate(tr):
        s=t if s is None else (s*(n-1)+t)/n
        out[i]=s if i>=n-1 else None
    return out

_n = json.load(open(os.path.join(SC,"niftyd.json")))
_a = atr_series(_n)
ATR = {datetime.datetime.fromtimestamp(b["t"], datetime.UTC).date(): _a[i]
       for i,b in enumerate(_n) if _a[i]}

def spread_leg(entry, exitd, ot, wide=2, no_roll=False):
    """Vertical debit spread, rolled at expiry unless no_roll. Returns % on debit."""
    cur, debits, values, guard = entry, [], [], 0
    while cur < exitd and guard < 12:
        guard += 1
        exp = O.pick_exp(cur, "NIFTY")
        spot = O.SPOT.get(cur)
        if exp is None or spot is None: return None
        k1 = O.atm(cur, "NIFTY", ot, exp, spot, 0)
        k2 = O.atm(cur, "NIFTY", ot, exp, spot, wide)
        if k1 is None or k2 is None: return None
        p1,_ = O.px(cur, "NIFTY", ot, exp, k1)
        p2,_ = O.px(cur, "NIFTY", ot, exp, k2)
        if not p1 or p2 is None: return None
        deb = p1 - p2
        if deb <= 0: return None
        close_on = min(exp, exitd)
        v = None
        for _ in range(6):
            q1,_t = O.px(close_on, "NIFTY", ot, exp, k1)
            q2,_t = O.px(close_on, "NIFTY", ot, exp, k2)
            if q1 is not None and q2 is not None: v = q1 - q2; break
            prev=[x for x in O.DAYS if x < close_on]
            if not prev: break
            close_on = prev[-1]
        if v is None:
            s = O.SPOT.get(close_on) or O.SPOT[[x for x in O.DAYS if x<=close_on][-1]]
            i1 = max(0.0,(s-k1) if ot=="CE" else (k1-s))
            i2 = max(0.0,(s-k2) if ot=="CE" else (k2-s))
            v = i1-i2
        debits.append(deb); values.append(max(0.0,v))
        if no_roll or close_on >= exitd: break
        nd = O.nextday(close_on)
        if nd is None or nd > exitd: break
        cur = nd
    if not debits: return None
    return (sum(values)-sum(debits))/sum(debits)*100

def naked_first_expiry(entry, exitd, ot, offset=0):
    """Buy once, close at the first expiry or the signal exit, whichever first."""
    exp = O.pick_exp(entry, "NIFTY"); spot = O.SPOT.get(entry)
    if exp is None or spot is None: return None
    k = O.atm(entry, "NIFTY", ot, exp, spot, offset)
    if k is None: return None
    p,_ = O.px(entry, "NIFTY", ot, exp, k)
    if not p: return None
    close_on = min(exp, exitd); v = None
    for _ in range(6):
        q,_t = O.px(close_on, "NIFTY", ot, exp, k)
        if q is not None: v = q; break
        prev=[x for x in O.DAYS if x < close_on]
        if not prev: break
        close_on = prev[-1]
    if v is None:
        s = O.SPOT.get(close_on) or O.SPOT[[x for x in O.DAYS if x<=close_on][-1]]
        v = max(0.0,(s-k) if ot=="CE" else (k-s))
    return (v-p)/p*100

def premium_vs_risk(t):
    """ATM premium divided by 1R (=3xATR). How dear the option is relative to
    the move the strategy is actually playing for."""
    e = datetime.date.fromisoformat(t["entry"])
    exp = O.pick_exp(e,"NIFTY"); spot = O.SPOT.get(e); a = ATR.get(e)
    if exp is None or spot is None or not a: return None
    ot = "CE" if t["dir"]>0 else "PE"
    k = O.atm(e,"NIFTY",ot,exp,spot,0)
    if k is None: return None
    p,_ = O.px(e,"NIFTY",ot,exp,k)
    if not p: return None
    return p/(3.0*a)

def st(v,lbl,w=32):
    v=[x for x in v if x is not None]
    if len(v)<4: return f"  {lbl:<{w}}{len(v):>6}   too few"
    win=[x for x in v if x>0]; gl=abs(sum(x for x in v if x<=0))
    pf=sum(win)/gl if gl>0 else 99.0
    med=sorted(v)[len(v)//2]
    return (f"  {lbl:<{w}}{len(v):>6}{len(win)/len(v)*100:>7.1f}%"
            f"{sum(v)/len(v):>+9.1f}%{med:>+9.1f}%{pf:>7.2f}")
H=lambda w=32: f"  {'':<{w}}{'trds':>6}{'win':>8}{'mean':>10}{'median':>10}{'PF':>7}"

if __name__ == "__main__":
    cache=os.path.join(SC,"optimprove.json")
    if os.path.exists(cache) and "--rebuild" not in sys.argv:
        rows=json.load(open(cache))
    else:
        rows=[]
        for t in O.T:
            e=datetime.date.fromisoformat(t["entry"]); x=datetime.date.fromisoformat(t["exit"])
            ot="CE" if t["dir"]>0 else "PE"
            try: naked,_l,_s = O.leg(e,x,ot)
            except Exception: naked=None
            rows.append(dict(entry=t["entry"],dir=t["dir"],ot=ot,R=t["R"],pct=t["pct"],
                naked=naked,
                spread2=spread_leg(e,x,ot,2),
                spread4=spread_leg(e,x,ot,4),
                noroll=naked_first_expiry(e,x,ot),
                sp_noroll=spread_leg(e,x,ot,2,no_roll=True),
                pvr=premium_vs_risk(t)))
        json.dump(rows,open(cache,"w"),indent=1)

    print(f"NIFTY ONLY, {len(rows)} signals — three fixes for premium-eats-the-edge\n")
    print("1. STRUCTURE  (same signal, different way of paying for it)")
    print(H())
    print(st([r["naked"] for r in rows],    "naked ATM, rolled  (baseline)"))
    print(st([r["spread2"] for r in rows],  "debit spread ATM/ATM+2, rolled"))
    print(st([r["spread4"] for r in rows],  "debit spread ATM/ATM+4, rolled"))
    print(st([r["noroll"] for r in rows],   "naked ATM, no roll"))
    print(st([r["sp_noroll"] for r in rows],"debit spread, no roll"))
    print()
    print("2. PREMIUM-AWARE ENTRY  (ATM premium / 1R, where 1R = 3x ATR)")
    pv=sorted(r["pvr"] for r in rows if r["pvr"])
    print(f"   ratio ranges {pv[0]:.2f} to {pv[-1]:.2f}, median {pv[len(pv)//2]:.2f}")
    print(H())
    for th in (0.30,0.35,0.40,0.45,0.50,0.60):
        sel=[r for r in rows if r["pvr"] and r["pvr"]<th]
        print(st([r["naked"] for r in sel], f"naked, premium/1R < {th:.2f}"))
    print()
    for th in (0.30,0.40,0.50,0.60):
        sel=[r for r in rows if r["pvr"] and r["pvr"]<th]
        print(st([r["spread2"] for r in sel], f"spread, premium/1R < {th:.2f}"))
    print()
    print("3. BEST COMBINATION vs the honest alternative")
    print(H())
    best=[r for r in rows if r["pvr"] and r["pvr"]<0.40]
    print(st([r["spread2"] for r in best],"spread + premium filter"))
    print(st([r["naked"] for r in best],  "naked  + premium filter"))
