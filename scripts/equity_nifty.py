"""One lakh on NIFTY daily signals, bought as options, against real bhavcopy.

Run two ways: the bare trend system, for a like-for-like comparison with the
BANKNIFTY study, and the constituent volume surge version, which is the NIFTY
variant that actually validated over nineteen years.
"""
import json, os, sys, datetime
SC = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, SC)
import fo_fetch as F
from indices_run import ema, atr

CAPITAL = 100_000
RISK_CAP = 0.25
SYM = "NIFTY"

def day(t): return datetime.datetime.fromtimestamp(t, datetime.UTC).date()

BREADTH = {datetime.date.fromisoformat(k): v
           for k, v in json.load(open(os.path.join(SC, "nifty_breadth.json"))).items()}

def signals(bars, since, aM=3.0, don=50, cost_bp=3.0, gate=None, long_only=False):
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
                                R=(((done-ep) if d>0 else (ep-done))
                                   - C[i]*cost_bp/10000.0)/r0))
            pos=None
        if pos is None:
            bu=C[i]>h1 and up; bd=(C[i]<l1 and dn) and not long_only
            if bu or bd:
                if gate is not None:
                    b=BREADTH.get(day(bars[i]["t"]))
                    if not b or not gate(b): continue
                d=1 if bu else -1; r0=aM*a
                pos=(d,C[i],C[i]-d*r0,r0,i)
    return out

def lot_of(d):
    t=F.raw(d)
    if not t: return None
    lines=t.splitlines(); hdr=[x.strip() for x in lines[0].split(",")]
    ix={c:i for i,c in enumerate(hdr)}
    if "TradDt" in hdr:
        for L in lines[1:]:
            f=L.split(",")
            if len(f)<len(hdr)-4: continue
            if f[ix["TckrSymb"]]==SYM and f[ix["FinInstrmTp"]]=="IDF":
                return int(f[ix["NewBrdLotQty"]]), float(f[ix["UndrlygPric"]])
        return None
    best=None
    for L in lines[1:]:
        f=L.split(",")
        if len(f)<14: continue
        if f[ix["SYMBOL"]]!=SYM or f[ix["INSTRUMENT"]]!="FUTIDX": continue
        try:
            con=float(f[ix["CONTRACTS"]] or 0); val=float(f[ix["VAL_INLAKH"]] or 0)
            px=float(f[ix["CLOSE"]] or 0)
            if con<=0 or val<=0 or px<=0: continue
            cand=(int(round(val*100000.0/(con*px)/5.0)*5), px)
            if best is None or con>best[0]: best=(con,cand)
        except ValueError: continue
    return best[1] if best else None

def chain(d, ot, min_days=20):
    rows=[r for r in F.parse_cached(d) if r["sym"]==SYM and r["ot"]==ot
          and r["traded"] and r["close"]>0]
    if not rows: return None
    exps=sorted({r["exp"] for r in rows}); last={}
    for e in exps: last[(e.year,e.month)]=max(last.get((e.year,e.month),e),e)
    for e in sorted(last.values()):
        if (e-d).days < min_days: continue
        c=[r for r in rows if r["exp"]==e]
        if c: return c, e
    return None

def price(d, ot, exp, k):
    for r in F.parse_cached(d):
        if r["sym"]==SYM and r["ot"]==ot and r["exp"]==exp and abs(r["strike"]-k)<1e-6:
            p=r["close"] if r["traded"] and r["close"]>0 else r["settle"]
            return (p if p>0 else None)
    return None

def trade_option(t, days_index):
    cur, exitd = t["entry"], t["exit"]
    ot = "CE" if t["dir"]>0 else "PE"
    legs=[]; lot=None; first=None; guard=0
    while cur < exitd and guard < 12:
        guard+=1
        li=lot_of(cur)
        if li is None: return None
        lot, spot = li
        ch=chain(cur, ot)
        if ch is None: return None
        c, exp = ch
        row=min(c, key=lambda r: abs(r["strike"]-spot))
        k, pin = row["strike"], row["close"]
        close_on=min(exp, exitd); pout=None; dd=close_on
        for _ in range(6):
            pout=price(dd, ot, exp, k)
            if pout is not None: break
            prev=[x for x in days_index if x<dd]
            if not prev: break
            dd=prev[-1]
        if pout is None:
            li2=lot_of(close_on) or (lot, spot)
            s=li2[1]
            pout=max(0.0,(s-k) if ot=="CE" else (k-s))
        legs.append((pin,pout))
        if first is None: first=pin
        if close_on>=exitd: break
        nxt=[x for x in days_index if x>close_on]
        if not nxt or nxt[0]>exitd: break
        cur=nxt[0]
    if not legs: return None
    return sum(p for p,_ in legs), sum(o for _,o in legs), lot, first

def replay(priced, cap):
    eq=cap; pk=cap; dd=0.0; taken=0; skip=0; wins=0
    for t,(paid,got,lot,first) in priced:
        per=first*lot
        lots=int(min(eq*RISK_CAP, eq)//per)
        if lots<1: skip+=1; continue
        pnl=(got-paid)*lot*lots
        eq+=pnl; taken+=1
        if pnl>0: wins+=1
        pk=max(pk,eq); dd=max(dd,(pk-eq)/pk*100)
    return taken, skip, wins, eq, dd

if __name__ == "__main__":
    nf=json.load(open(os.path.join(SC,"niftyd.json")))
    days=[day(b["t"]) for b in nf]
    since=datetime.date(2021,1,1)
    G30=lambda b: b["pct_rvol"]>0.30

    for lbl, sig in (("BARE TREND SYSTEM", signals(nf, since)),
                     ("VOLUME SURGE GATED", signals(nf, since, gate=G30)),
                     ("VOLUME SURGE, LONG ONLY", signals(nf, since, gate=G30, long_only=True))):
        priced=[]
        for t in sig:
            r=trade_option(t, days)
            if r: priced.append((t,r))
        idxR=sum(t["R"] for t,_ in priced)
        print(f"\n{lbl} — NIFTY since {since}")
        print(f"  {len(sig)} signals, {len(priced)} priceable, index signal {idxR:+.2f}R")
        if not priced: continue
        print(f"  {'capital':>11}{'taken':>7}{'skip':>6}{'win':>7}{'final':>13}{'return':>9}{'maxDD':>8}")
        for cap in (100_000, 500_000, 2_500_000):
            tk,sk,w,eq,dd = replay(priced, cap)
            wr = f"{w/tk*100:.0f}%" if tk else "-"
            print(f"  {cap:>11,}{tk:>7}{sk:>6}{wr:>7}{eq:>13,.0f}{(eq/cap-1)*100:>+8.1f}%{dd:>7.1f}%")
