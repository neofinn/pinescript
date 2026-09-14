"""Volume-based breakouts only.

Entry is a Donchian breakout that must be confirmed by volume. The question
is which definition of "confirmed by volume" actually earns its keep, and
whether volume can stand in for the EMA trend filter rather than sit beside it.

Gold hourly volume is strongly time-of-day driven, so a plain vol>SMA gate is
partly a session filter wearing a volume costume. Both are measured.
"""
import json, os, statistics as st, datetime

HERE = os.path.dirname(os.path.abspath(__file__))

def ema(v,n):
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

def resample(bars, secs):
    out,cur=[],None
    for b in bars:
        k=b["t"]//secs
        if cur is None or cur["k"]!=k:
            if cur: out.append(cur)
            cur={"k":k,**{f:b[f] for f in ("t","o","h","l","c")},"v":b.get("v",0)}
        else:
            cur["h"]=max(cur["h"],b["h"]); cur["l"]=min(cur["l"],b["l"])
            cur["c"]=b["c"]; cur["v"]+=b.get("v",0)
    if cur: out.append(cur)
    for b in out: b.pop("k")
    return out

# ---- volume features -------------------------------------------------------
def vol_features(bars, look=20):
    V=[b.get("v",0) or 0 for b in bars]
    O=[b["o"] for b in bars]; C=[b["c"] for b in bars]
    n=len(bars)
    rvol=[None]*n      # v / mean(v, look)
    z=[None]*n         # (v - mean)/sd over look
    hi=[None]*n        # v is the highest of the last `look`
    tod=[None]*n       # v / mean(v for this hour-of-day, trailing 20 same-hours)
    sdelta=[None]*n    # signed volume sum over look, normalised by total volume
    hour_hist={}
    for i in range(n):
        w=V[i-look:i]
        if i>=look and any(w):
            m=sum(w)/len(w)
            if m>0:
                rvol[i]=V[i]/m
                s=st.pstdev(w)
                z[i]=(V[i]-m)/s if s>0 else 0.0
            hi[i]= V[i] >= max(w) and V[i]>0
        h=datetime.datetime.fromtimestamp(bars[i]["t"], datetime.UTC).hour
        hh=hour_hist.setdefault(h,[])
        if len(hh)>=20 and sum(hh[-20:])>0:
            tod[i]=V[i]/(sum(hh[-20:])/20)
        hh.append(V[i])
        w2=list(range(max(0,i-look+1), i+1))
        tot=sum(V[j] for j in w2)
        if tot>0:
            sdelta[i]=sum(V[j]*(1 if C[j]>O[j] else -1 if C[j]<O[j] else 0) for j in w2)/tot
    return dict(rvol=rvol, z=z, hi=hi, tod=tod, sdelta=sdelta)

# ---- the gates -------------------------------------------------------------
def gates():
    g={}
    g["(no volume gate)"]      = lambda F,i,d: True
    for k in (1.0,1.25,1.5,2.0,3.0):
        g[f"rvol > {k}x mean20"] = (lambda k: lambda F,i,d: F["rvol"][i] is not None and F["rvol"][i]>k)(k)
    for k in (1.0,1.5,2.0):
        g[f"vol z-score > {k}"]  = (lambda k: lambda F,i,d: F["z"][i] is not None and F["z"][i]>k)(k)
    g["vol = highest of 20"]   = lambda F,i,d: bool(F["hi"][i])
    for k in (1.25,1.5,2.0):
        g[f"time-of-day rvol > {k}x"] = (lambda k: lambda F,i,d: F["tod"][i] is not None and F["tod"][i]>k)(k)
    for k in (0.0,0.2):
        g[f"signed vol agrees (>{k})"] = (lambda k: lambda F,i,d:
            F["sdelta"][i] is not None and (F["sdelta"][i]>k if d>0 else F["sdelta"][i]<-k))(k)
    g["rvol>1.5 AND signed agrees"] = lambda F,i,d: (F["rvol"][i] is not None and F["rvol"][i]>1.5
        and F["sdelta"][i] is not None and (F["sdelta"][i]>0 if d>0 else F["sdelta"][i]<0))
    return g

# ---- engine ----------------------------------------------------------------
def run(bars, F, gate, cost=1.0, aM=3.0, don=50, use_trend=True, fL=50, sL=150):
    H=[b["h"] for b in bars]; L=[b["l"] for b in bars]; C=[b["c"] for b in bars]
    f,s,A = ema(C,fL), ema(C,sL), atr(H,L,C,14)
    out=[]; pos=None; sigs=0
    for i in range(max(sL,don)+2, len(bars)):
        a=A[i]
        if a is None or a<=0: continue
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
                d = 1 if brkU else -1
                if gate(F,i,d):
                    r0=aM*a
                    pos=(d,C[i],C[i]-d*r0,r0)
    return out, sigs

def line(lbl,t,sigs,w=30):
    if len(t)<5: return f"  {lbl:<{w}}{len(t):>6}{'':>44}   too few"
    win=[x for x in t if x>0]; gl=abs(sum(x for x in t if x<=0))
    pf=sum(win)/gl if gl>0 else 99.0
    eq=pk=dd=0.0
    for r in t:
        eq+=r; pk=max(pk,eq); dd=max(dd,pk-eq)
    keep = len(t)/sigs*100 if sigs else 0
    return (f"  {lbl:<{w}}{len(t):>6}{keep:>7.0f}%{len(win)/len(t)*100:>7.1f}%"
            f"{sum(t):>+9.1f}R{sum(t)/len(t):>+8.3f}R{pf:>7.2f}{dd:>8.1f}R")

HDR=lambda w=30: f"  {'':<{w}}{'trds':>6}{'kept':>8}{'win':>8}{'netR':>10}{'exp':>9}{'PF':>7}{'maxDD':>8}"

r=json.load(open(os.path.join(HERE,"gc1h.json")))["chart"]["result"][0]
ts,q=r["timestamp"], r["indicators"]["quote"][0]
gc1h=[{"t":t,"o":q["open"][i],"h":q["high"][i],"l":q["low"][i],"c":q["close"][i],"v":q["volume"][i] or 0}
      for i,t in enumerate(ts) if q["close"][i] is not None]
M=60
TFS=[("1h",resample(gc1h,60*M)),("2h",resample(gc1h,120*M)),("4h",resample(gc1h,240*M))]
G=gates()

# --- data quality gate -----------------------------------------------------
# Real futures volume tracks absolute return strongly. Where it does not, the
# volume field carries no information and every gate built on it is noise.
def vol_is_usable(bars):
    V=[b.get("v",0) or 0 for b in bars]
    R=[abs(bars[i]["c"]-bars[i-1]["c"])/bars[i-1]["c"] for i in range(1,len(bars))]
    m=[(r,v) for r,v in zip(R,V[1:]) if v>0]
    n=len(m); mr=sum(x[0] for x in m)/n; mv=sum(x[1] for x in m)/n
    cov=sum((x[0]-mr)*(x[1]-mv) for x in m)/n
    sr=(sum((x[0]-mr)**2 for x in m)/n)**.5; sv=(sum((x[1]-mv)**2 for x in m)/n)**.5
    return cov/(sr*sv)

print("DATA QUALITY  corr(volume, |return|) — below ~0.2 the volume field is void")
for lbl,b in [("GC=F 1h", resample(gc1h,60*M)), ("GC=F 4h", resample(gc1h,240*M)),
              ("GC=F daily", json.load(open(os.path.join(HERE,"gcdaily.json"))))]:
    c=vol_is_usable(b)
    print(f"  {lbl:<14}{c:>+7.3f}   {'usable' if c>0.2 else 'VOID - no volume test is meaningful here'}")
print()

print("GOLD GC=F intraday, 2y — Donchian(50) breakout, stop 3x ATR, no target, 1 pt cost")
print("'kept' = share of raw breakout signals the volume gate let through\n")

for tf,bars in TFS:
    F=vol_features(bars)
    print(f"=== {tf}  [{len(bars)} bars]   breakout + EMA trend + volume gate")
    print(HDR())
    for name,gt in G.items():
        t,s_=run(bars,F,gt); print(line(name,t,s_))
    print()

print("=== 1h   volume INSTEAD of the EMA trend filter (pure volume breakout)")
bars=dict(TFS)["1h"]; F=vol_features(bars)
print(HDR())
for name,gt in G.items():
    t,s_=run(bars,F,gt,use_trend=False); print(line(name,t,s_))

print("\n=== 4h   volume INSTEAD of the EMA trend filter")
bars=dict(TFS)["4h"]; F=vol_features(bars)
print(HDR())
for name,gt in G.items():
    t,s_=run(bars,F,gt,use_trend=False); print(line(name,t,s_))
