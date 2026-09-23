"""A one lakh account on BANKNIFTY daily signals, bought as options.

Futures are not simulated because the previous script establishes they are not
affordable: one lot is 1.7 million of notional against 100,000 of capital.

Every premium is a real traded bhavcopy price. Position size is whole lots, and
the option is rolled at expiry if the signal is still open, because the signal
routinely outlives a monthly contract.
"""
import json, os, sys, datetime
SC = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, SC)
import fo_fetch as F
from indices_run import ema, atr

CAPITAL = 100_000
RISK_CAP = 0.25          # never put more than a quarter of the account in one trade

def day(t): return datetime.datetime.fromtimestamp(t, datetime.UTC).date()

def signals(bars, since, aM=3.0, don=50, cost_bp=3.0):
    H=[b["h"] for b in bars]; L=[b["l"] for b in bars]; C=[b["c"] for b in bars]
    f,s,A = ema(C,50), ema(C,150), atr(H,L,C,14)
    out=[]; pos=None
    for i in range(152,len(bars)):
        a=A[i]
        if a is None or a<=0: continue
        h1=max(H[i-don:i]); l1=min(L[i-don:i])
        up=f[i]>s[i]; dn=s[i]>f[i]
        xUp=f[i-1]<=s[i-1] and f[i]>s[i]; xDn=f[i-1]>=s[i-1] and f[i]<s[i]
        if pos:
            d,ep,stp,r0,ei=pos; done=None
            if d>0:
                stp=max(stp,C[i]-aM*a)
                if L[i]<=stp: done=stp
                elif xDn and dn: done=C[i]
            else:
                stp=min(stp,C[i]+aM*a)
                if H[i]>=stp: done=stp
                elif xUp and up: done=C[i]
            if done is None: pos=(d,ep,stp,r0,ei); continue
            if day(bars[ei]["t"])>=since:
                out.append(dict(dir=d, entry=day(bars[ei]["t"]), exit=day(bars[i]["t"]),
                                ep=ep, xp=done, R=(((done-ep) if d>0 else (ep-done))
                                                   - C[i]*cost_bp/10000.0)/r0))
            pos=None
        if pos is None:
            bu=C[i]>h1 and up; bd=C[i]<l1 and dn
            if bu or bd:
                d=1 if bu else -1; r0=aM*a
                pos=(d,C[i],C[i]-d*r0,r0,i)
    return out

def chain(d, ot, min_days=20):
    """The ATM-bearing chain for a MONTHLY expiry.

    The nearest expiry is a weekly, and rolling weeklies across a hold that runs
    months means paying premium a dozen times -- the exact leak the selection
    engine already measured. Monthlies are the last expiry in their month.
    """
    rows=[r for r in F.parse_cached(d) if r["sym"]=="BANKNIFTY" and r["ot"]==ot
          and r["traded"] and r["close"]>0]
    if not rows: return None
    exps=sorted({r["exp"] for r in rows})
    last={}
    for e in exps: last[(e.year,e.month)]=max(last.get((e.year,e.month),e),e)
    for e in sorted(last.values()):
        if (e-d).days < min_days: continue
        c=[r for r in rows if r["exp"]==e]
        if c: return c, e
    return None

def lot_of(d):
    """(lot size, spot) for BANKNIFTY on this date, from whichever schema applies.

    The legacy bhavcopy carries no lot-size column, so it is recovered from the
    turnover identity: value in lakhs = contracts x lot x price / 100000. That
    beats a hardcoded table -- BANKNIFTY's lot has been 25, 40, 20, 25, 15 and 30
    at different times, and a stale constant silently corrupts every rupee below.
    """
    t=F.raw(d)
    if not t: return None
    lines=t.splitlines(); hdr=[x.strip() for x in lines[0].split(",")]
    ix={c:i for i,c in enumerate(hdr)}
    if "TradDt" in hdr:
        for L in lines[1:]:
            f=L.split(",")
            if len(f)<len(hdr)-4: continue
            if f[ix["TckrSymb"]]=="BANKNIFTY" and f[ix["FinInstrmTp"]]=="IDF":
                return int(f[ix["NewBrdLotQty"]]), float(f[ix["UndrlygPric"]])
        return None
    best=None
    for L in lines[1:]:
        f=L.split(",")
        if len(f)<14: continue
        if f[ix["SYMBOL"]]!="BANKNIFTY" or f[ix["INSTRUMENT"]]!="FUTIDX": continue
        try:
            con=float(f[ix["CONTRACTS"]] or 0); val=float(f[ix["VAL_INLAKH"]] or 0)
            px=float(f[ix["CLOSE"]] or 0)
            if con<=0 or val<=0 or px<=0: continue
            lot=val*100000.0/(con*px)
            cand=(int(round(lot/5.0)*5), px)          # lots are multiples of 5
            if best is None or con>best[0]: best=(con,cand)
        except ValueError: continue
    return best[1] if best else None

def price(d, ot, exp, strike):
    for r in F.parse_cached(d):
        if (r["sym"]=="BANKNIFTY" and r["ot"]==ot and r["exp"]==exp
                and abs(r["strike"]-strike)<1e-6):
            p=r["close"] if r["traded"] and r["close"]>0 else r["settle"]
            return (p if p>0 else None), r["traded"]
    return None, False

def trade_option(t, days_index):
    """Walk one signal as a long option, rolling at expiry. -> (paid, got, lot)"""
    cur, exitd = t["entry"], t["exit"]
    ot = "CE" if t["dir"]>0 else "PE"
    legs=[]; lot=None
    guard=0
    while cur < exitd and guard < 12:
        guard+=1
        li = lot_of(cur)
        if li is None: return None
        lot, spot = li
        ch = chain(cur, ot)
        if ch is None: return None
        c, exp = ch
        row = min(c, key=lambda r: abs(r["strike"]-spot))
        k, pin = row["strike"], row["close"]
        close_on = min(exp, exitd)
        pout=None; dd=close_on
        for _ in range(6):
            pout,_tr = price(dd, ot, exp, k)
            if pout is not None: break
            prev=[x for x in days_index if x<dd]
            if not prev: break
            dd=prev[-1]
        if pout is None:
            li2=lot_of(close_on) or (lot, spot)
            s=li2[1]
            pout=max(0.0,(s-k) if ot=="CE" else (k-s))
        legs.append((pin,pout))
        if len(legs)==1: first=pin
        if close_on>=exitd: break
        nxt=[x for x in days_index if x>close_on]
        if not nxt or nxt[0]>exitd: break
        cur=nxt[0]
    if not legs: return None
    # first is the upfront outlay that sizes the position; paid/got are the
    # full cash flows across every roll.
    return sum(p for p,_ in legs), sum(o for _,o in legs), lot, first

if __name__ == "__main__":
    bn=json.load(open(os.path.join(SC,"idx","BANKNIFTY.json")))
    days_index=[day(b["t"]) for b in bn]
    since=datetime.date(2021,1,1)
    sig=signals(bn, since)
    print(f"BANKNIFTY daily signals since {since}: {len(sig)}  "
          f"({sum(1 for s in sig if s['dir']>0)} long, {sum(1 for s in sig if s['dir']<0)} short)\n")
    eq=CAPITAL; rows=[]
    print(f"  {'dir':>5} {'entry':>11} {'exit':>11} {'idxR':>7} {'prem/lot':>10} "
          f"{'lots':>5} {'P&L INR':>11} {'equity':>11}")
    for t in sig:
        r=trade_option(t, days_index)
        if r is None:
            print(f"  {'L' if t['dir']>0 else 'S':>5} {str(t['entry']):>11} {str(t['exit']):>11} "
                  f"{t['R']:>+7.2f}   no priceable contract"); continue
        paid, got, lot, first = r
        per_lot = first*lot                      # upfront cost of one lot
        lots = int(min(eq*RISK_CAP, eq)//per_lot)
        if lots < 1:
            print(f"  {'L' if t['dir']>0 else 'S':>5} {str(t['entry']):>11} {str(t['exit']):>11} "
                  f"{t['R']:>+7.2f} {per_lot:>10,.0f} {0:>5}   premium exceeds the risk cap")
            continue
        pnl=(got-paid)*lot*lots
        eq+=pnl; rows.append(dict(pnl=pnl, eq=eq, R=t["R"], dir=t["dir"]))
        print(f"  {'L' if t['dir']>0 else 'S':>5} {str(t['entry']):>11} {str(t['exit']):>11} "
              f"{t['R']:>+7.2f} {per_lot:>10,.0f} {lots:>5} {pnl:>+11,.0f} {eq:>11,.0f}")
    if rows:
        w=[r for r in rows if r["pnl"]>0]
        pk=CAPITAL; dd=0.0
        for r in rows: pk=max(pk,r["eq"]); dd=max(dd,(pk-r["eq"])/pk*100)
        print(f"\n  {len(rows)} trades   win {len(w)/len(rows)*100:.1f}%   "
              f"final {eq:,.0f} from {CAPITAL:,}   "
              f"return {(eq/CAPITAL-1)*100:+.1f}%   max drawdown {dd:.1f}%")
