"""The daily system across world indices.

Donchian(50) + EMA 50/150 trend, 1R = 3x ATR, reward uncapped. The volume
surge gate is applied only where the volume series survives the same check
used on gold: real volume tracks absolute return, and a series that does not
carries no information about activity.
"""
import json, os, glob, sys

SC = os.path.dirname(os.path.abspath(__file__))

def ema(v, n):
    out=[None]*len(v); k=2/(n+1); e=None
    for i,x in enumerate(v):
        e = x if e is None else x*k+e*(1-k); out[i]=e
    return out

def atr(H,L,C,n=14):
    tr=[H[0]-L[0]]+[max(H[i]-L[i],abs(H[i]-C[i-1]),abs(L[i]-C[i-1])) for i in range(1,len(H))]
    out=[None]*len(H); s=None
    for i,t in enumerate(tr):
        s=t if s is None else (s*(n-1)+t)/n
        out[i]=s if i>=n-1 else None
    return out

def vol_quality(bars):
    V=[b.get("v",0) or 0 for b in bars]
    R=[abs(bars[i]["c"]-bars[i-1]["c"])/bars[i-1]["c"] for i in range(1,len(bars))]
    m=[(r,v) for r,v in zip(R,V[1:]) if v>0]
    if len(m)<200: return None
    n=len(m); mr=sum(x[0] for x in m)/n; mv=sum(x[1] for x in m)/n
    cov=sum((a-mr)*(b-mv) for a,b in m and [(x[0],x[1]) for x in m])/n
    sr=(sum((x[0]-mr)**2 for x in m)/n)**.5; sv=(sum((x[1]-mv)**2 for x in m)/n)**.5
    return cov/(sr*sv) if sr>0 and sv>0 else None

def rvol(bars, look=20):
    V=[b.get("v",0) or 0 for b in bars]
    out=[None]*len(bars)
    for i in range(look, len(bars)):
        w=V[i-look:i]
        m=sum(w)/len(w) if w else 0
        if m>0 and V[i]>0: out[i]=V[i]/m
    return out

def run(bars, aM=3.0, cost_bp=3.0, don=50, long_only=False, gate=None, RV=None):
    H=[b["h"] for b in bars]; L=[b["l"] for b in bars]; C=[b["c"] for b in bars]
    f,s,A = ema(C,50), ema(C,150), atr(H,L,C,14)
    out=[]; pos=None
    for i in range(152, len(bars)):
        a=A[i]
        if a is None or a<=0: continue
        cost=C[i]*cost_bp/10000.0
        h1=max(H[i-don:i]); l1=min(L[i-don:i])
        up=f[i]>s[i]; dn=s[i]>f[i]
        xUp=f[i-1]<=s[i-1] and f[i]>s[i]; xDn=f[i-1]>=s[i-1] and f[i]<s[i]
        if pos:
            d,ep,stp,r0=pos; done=None
            if d>0:
                stp=max(stp, C[i]-aM*a)
                if L[i]<=stp: done=stp
                elif xDn and dn: done=C[i]
            else:
                stp=min(stp, C[i]+aM*a)
                if H[i]>=stp: done=stp
                elif xUp and up: done=C[i]
            if done is None: pos=(d,ep,stp,r0); continue
            out.append((((done-ep) if d>0 else (ep-done))-cost)/r0)
            pos=None
        if pos is None:
            bu=C[i]>h1 and up; bd=(C[i]<l1 and dn) and not long_only
            if bu or bd:
                if gate is not None:
                    rv = RV[i] if RV else None
                    if rv is None or not gate(rv): continue
                d=1 if bu else -1
                r0=aM*a
                pos=(d,C[i],C[i]-d*r0,r0)
    return out

def stat(v):
    if len(v)<5: return None
    w=[x for x in v if x>0]; gl=abs(sum(x for x in v if x<=0))
    pf=sum(w)/gl if gl>0 else 99.0
    eq=pk=dd=0.0
    for r in v: eq+=r; pk=max(pk,eq); dd=max(dd,pk-eq)
    return len(v), len(w)/len(v)*100, sum(v), sum(v)/len(v), pf, dd

def line(lbl, v, w=14):
    r=stat(v)
    if not r: return f"  {lbl:<{w}}{len(v):>6}   too few"
    n,wr,net,ex,pf,dd=r
    return f"  {lbl:<{w}}{n:>6}{wr:>7.1f}%{net:>+9.1f}R{ex:>+8.3f}R{pf:>7.2f}{dd:>8.1f}R"
HDR=lambda w=14: f"  {'':<{w}}{'trds':>6}{'win':>8}{'netR':>10}{'exp':>9}{'PF':>7}{'maxDD':>8}"

ORDER = ["NIFTY","BANKNIFTY","NIFTYIT","SP500","NASDAQ","RUSSELL2K","SPY","QQQ","IWM",
         "DAX","FTSE","CAC","STOXX50","NIKKEI","HANGSENG","ASX200","KOSPI","TAIEX","EEM"]

if __name__ == "__main__":
    data = {n: json.load(open(os.path.join(SC,"idx",f"{n}.json"))) for n in ORDER
            if os.path.exists(os.path.join(SC,"idx",f"{n}.json"))}

    print("VOLUME DATA QUALITY  corr(volume, |return|) — below ~0.2 the field is void")
    q={}
    for n,b in data.items():
        c=vol_quality(b); q[n]=c
        tag = "usable" if (c is not None and c>0.2) else "VOID"
        print(f"  {n:<12}{'n/a' if c is None else f'{c:+.3f}':>8}   {tag}")
    print()

    print("BASE SYSTEM, BOTH SIDES  (Donchian 50 + EMA trend, stop 3x ATR, 3bp)")
    print(HDR())
    for n,b in data.items(): print(line(n, run(b)))
    print()
    print("LONG ONLY")
    print(HDR())
    for n,b in data.items(): print(line(n, run(b, long_only=True)))

def gate_sweep():
    data = {n: json.load(open(os.path.join(SC,"idx",f"{n}.json"))) for n in ORDER
            if os.path.exists(os.path.join(SC,"idx",f"{n}.json"))}
    ok = [n for n,b in data.items() if (vol_quality(b) or 0) > 0.2]
    print("VOLUME SURGE GATE, LONG ONLY — only where the volume field is usable")
    print("does the gate grade smoothly, the way it did on NIFTY constituents?\n")
    ths=[None,1.0,1.25,1.5,2.0,3.0]
    print(f"  {'':<12}" + "".join(f"{('no gate' if t is None else f'rvol>{t}'):>13}" for t in ths))
    for n in ok:
        b=data[n]; RV=rvol(b); row=f"  {n:<12}"
        for t in ths:
            g=None if t is None else (lambda t: lambda x: x>t)(t)
            v=run(b, long_only=True, gate=g, RV=RV); r=stat(v)
            row += f"{'--':>13}" if not r else f"{r[4]:>6.2f}/{r[0]:>4}"
        print(row)
    print("\n  cell = profit factor / trade count")

if __name__ == "__main__" and "--gate" in sys.argv:
    gate_sweep()
