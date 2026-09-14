"""NIFTY 50 breakouts confirmed by confluence in the underlying constituents.

An index has no volume of its own worth trusting, so the honest analog of a
volume gate is participation: how many of the 50 names are actually in the move,
and how much real traded value is behind them. That is computed from the
constituents' own bars rather than from anything the index prints.
"""
import json, os, glob, datetime, statistics as st

SC = os.path.dirname(os.path.abspath(__file__))

def day(ts): return datetime.datetime.fromtimestamp(ts, datetime.UTC).date()

def ema(v, n):
    out=[None]*len(v); k=2/(n+1); e=None
    for i,x in enumerate(v):
        e = x if e is None else x*k+e*(1-k); out[i]=e
    return out

# ---- constituents ----------------------------------------------------------
def load_constituents():
    per = {}
    for p in sorted(glob.glob(os.path.join(SC, "n50", "*.json"))):
        sym = os.path.basename(p)[:-5]
        bars = json.load(open(p))
        C=[b["c"] for b in bars]; H=[b["h"] for b in bars]; V=[b["v"] for b in bars]
        e20 = ema(C,20)
        feat={}
        for i,b in enumerate(bars):
            if i < 51: continue
            w = V[i-20:i]
            m = sum(w)/len(w) if w else 0
            feat[day(b["t"])] = dict(
                up   = C[i] > C[i-1],
                ret  = (C[i]-C[i-1])/C[i-1],
                turn = C[i]*V[i],                       # traded value, the real weight
                aboveE = C[i] > e20[i],
                newhi  = H[i] >= max(H[i-50:i]),
                newlo  = b["l"] <= min(x["l"] for x in bars[i-50:i]),
                rvol   = (V[i]/m) if m>0 else None,
            )
        per[sym]=feat
    return per

# ---- breadth per index date ------------------------------------------------
def load_breadth_cache():
    """The derived series, so the study runs without refetching 31MB of bars."""
    p = os.path.join(SC, "nifty_breadth.json")
    if not os.path.exists(p): return None
    raw = json.load(open(p))
    return {datetime.date.fromisoformat(k): v for k, v in raw.items()}

def breadth(dates, per):
    if not per:
        c = load_breadth_cache()
        if c is not None: return c
        raise SystemExit("no constituent bars and no breadth cache; run fetch_nifty50.py")
    out={}
    for d in dates:
        rows=[f[d] for f in per.values() if d in f]
        n=len(rows)
        if n < 20:            # too few names listed to call it breadth
            out[d]=None; continue
        adv=sum(1 for r in rows if r["up"])
        turn_up=sum(r["turn"] for r in rows if r["up"])
        turn_dn=sum(r["turn"] for r in rows if not r["up"])
        tot=turn_up+turn_dn
        rv=[r["rvol"] for r in rows if r["rvol"] is not None]
        out[d]=dict(
            n        = n,
            pct_adv  = adv/n,                                    # advance/decline
            pct_ema  = sum(1 for r in rows if r["aboveE"])/n,    # trend participation
            pct_hi   = sum(1 for r in rows if r["newhi"])/n,     # breakout participation
            pct_lo   = sum(1 for r in rows if r["newlo"])/n,
            vdelta   = (turn_up-turn_dn)/tot if tot>0 else 0.0,  # signed traded VALUE
            pct_rvol = sum(1 for x in rv if x>1.5)/len(rv) if rv else 0.0,
        )
    return out

# ---- engine (same as the gold work) ----------------------------------------
def atr(H,L,C,n=14):
    tr=[H[0]-L[0]]+[max(H[i]-L[i],abs(H[i]-C[i-1]),abs(L[i]-C[i-1])) for i in range(1,len(H))]
    out=[None]*len(H); s=None
    for i,t in enumerate(tr):
        s=t if s is None else (s*(n-1)+t)/n
        out[i]=s if i>=n-1 else None
    return out

def run(bars, B, gate, cost_bp=3.0, aM=3.0, don=50, fL=50, sL=150, use_trend=True):
    H=[b["h"] for b in bars]; L=[b["l"] for b in bars]; C=[b["c"] for b in bars]
    f,s,A = ema(C,fL), ema(C,sL), atr(H,L,C,14)
    out=[]; pos=None; sigs=0
    for i in range(max(sL,don)+2, len(bars)):
        a=A[i]
        if a is None or a<=0: continue
        cost = C[i]*cost_bp/10000.0
        h1=max(H[i-don:i]); l1=min(L[i-don:i])
        up=f[i]>s[i]; dn=s[i]>f[i]
        xUp=f[i-1]<=s[i-1] and f[i]>s[i]; xDn=f[i-1]>=s[i-1] and f[i]<s[i]
        if pos:
            d,ep,stp,r0=pos
            if d>0:
                stp=max(stp, C[i]-aM*a)
                if L[i]<=stp:    out.append((stp-ep-cost)/r0); pos=None
                elif xDn and dn: out.append((C[i]-ep-cost)/r0); pos=None
                else: pos=(d,ep,stp,r0)
            else:
                stp=min(stp, C[i]+aM*a)
                if H[i]>=stp:    out.append((ep-stp-cost)/r0); pos=None
                elif xUp and up: out.append((ep-C[i]-cost)/r0); pos=None
                else: pos=(d,ep,stp,r0)
            if pos: continue
        if pos is None:
            brkU = C[i]>h1 and (up or not use_trend)
            brkD = C[i]<l1 and (dn or not use_trend)
            if brkU or brkD:
                sigs+=1
                d=1 if brkU else -1
                b=B.get(day(bars[i]["t"]))
                if b is not None and gate(b,d):
                    r0=aM*a
                    pos=(d,C[i],C[i]-d*r0,r0)
    return out, sigs

def gates():
    g={}
    g["(no confluence gate)"] = lambda b,d: True
    for k in (0.50,0.60,0.70):
        g[f"advancers > {int(k*100)}%"]      = (lambda k: lambda b,d: (b["pct_adv"] if d>0 else 1-b["pct_adv"])>k)(k)
    for k in (0.50,0.60,0.70):
        g[f"above own EMA20 > {int(k*100)}%"]= (lambda k: lambda b,d: (b["pct_ema"] if d>0 else 1-b["pct_ema"])>k)(k)
    for k in (0.10,0.20,0.30):
        g[f"making 50d high > {int(k*100)}%"]= (lambda k: lambda b,d: (b["pct_hi"] if d>0 else b["pct_lo"])>k)(k)
    for k in (0.0,0.2,0.4):
        g[f"traded-value delta > {k}"]       = (lambda k: lambda b,d: (b["vdelta"]>k if d>0 else b["vdelta"]<-k))(k)
    for k in (0.20,0.35):
        g[f"names w/ rvol>1.5 over {int(k*100)}%"] = (lambda k: lambda b,d: b["pct_rvol"]>k)(k)
    g["value delta>0.2 AND adv>60%"] = lambda b,d: ((b["vdelta"]>0.2 and b["pct_adv"]>0.60) if d>0
                                                     else (b["vdelta"]<-0.2 and b["pct_adv"]<0.40))
    return g

def stat(t):
    if len(t)<5: return None
    w=[x for x in t if x>0]; gl=abs(sum(x for x in t if x<=0))
    pf=sum(w)/gl if gl>0 else 99.0
    eq=pk=dd=0.0
    for r in t: eq+=r; pk=max(pk,eq); dd=max(dd,pk-eq)
    return len(t), len(w)/len(t)*100, sum(t), sum(t)/len(t), pf, dd

def line(lbl,t,sigs,w=30):
    r=stat(t)
    if not r: return f"  {lbl:<{w}}{len(t):>6}   too few"
    n,wr,net,ex,pf,dd=r
    return (f"  {lbl:<{w}}{n:>6}{n/sigs*100 if sigs else 0:>7.0f}%{wr:>7.1f}%"
            f"{net:>+9.1f}R{ex:>+8.3f}R{pf:>7.2f}{dd:>8.1f}R")
HDR=lambda w=30: f"  {'':<{w}}{'trds':>6}{'kept':>8}{'win':>8}{'netR':>10}{'exp':>9}{'PF':>7}{'maxDD':>8}"

if __name__ == "__main__":
    nifty=json.load(open(os.path.join(SC,"niftyd.json")))
    per=load_constituents()
    dates=[day(b["t"]) for b in nifty]
    B=breadth(dates, per)

    # ---- data quality, same discipline as the gold work --------------------
    def corr(xs,ys):
        n=len(xs); mx=sum(xs)/n; my=sum(ys)/n
        cov=sum((a-mx)*(b-my) for a,b in zip(xs,ys))/n
        sx=(sum((a-mx)**2 for a in xs)/n)**.5; sy=(sum((b-my)**2 for b in ys)/n)**.5
        return cov/(sx*sy) if sx>0 and sy>0 else 0.0
    V=[b.get("v",0) or 0 for b in nifty]
    R=[abs(nifty[i]["c"]-nifty[i-1]["c"])/nifty[i-1]["c"] for i in range(1,len(nifty))]
    m=[(r,v) for r,v in zip(R,V[1:]) if v>0]
    print("DATA QUALITY")
    if len(m)>100:
        print(f"  ^NSEI own volume field      corr(vol,|ret|) = {corr([x[0] for x in m],[x[1] for x in m]):+.3f}  (n={len(m)})")
    else:
        print(f"  ^NSEI own volume field      unusable: only {len(m)} of {len(V)} bars carry any volume")
    ok=[d for d in dates if B.get(d)]
    pairs=[(abs(nifty[i]["c"]-nifty[i-1]["c"])/nifty[i-1]["c"], B[day(nifty[i]["t"])]["vdelta"])
           for i in range(1,len(nifty)) if B.get(day(nifty[i]["t"]))]
    print(f"  constituent traded value    corr(|value delta|,|ret|) = "
          f"{corr([abs(x[0]) for x in pairs],[abs(x[1]) for x in pairs]):+.3f}  (n={len(pairs)})")
    print(f"  breadth coverage            {len(ok)}/{len(dates)} index days have >=20 listed names")
    yrs={}
    for d in dates:
        b=B.get(d)
        yrs.setdefault(d.year,[]).append(b["n"] if b else 0)
    print("  names available per year:   " + "  ".join(
        f"{y}:{int(sum(v)/len(v))}" for y,v in sorted(yrs.items()) if y%3==0))
    print()

    G=gates()
    print(f"NIFTY 50 DAILY {dates[0]} -> {dates[-1]}  [{len(nifty)} bars]")
    print("Donchian(50) breakout + EMA trend, stop 3x ATR, no target, 3bp cost")
    print("'kept' = share of raw index breakout signals the confluence gate let through\n")
    print(HDR())
    for name,gt in G.items():
        t,s_=run(nifty,B,gt); print(line(name,t,s_))
