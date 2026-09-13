"""Robrecht99 trend follower, trail_offset bug fixed, swept over timeframe
and stop/target geometry.

The original has no take-profit — it exits on the trailing stop or the EMA
cross — so "RR" here is two separate dials:
  atrMult  how far the stop sits, which SETS 1R
  tpR      an optional hard target in multiples of that R (0 = original)
"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
load = lambda n: json.load(open(os.path.join(HERE, n)))

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

def run(bars, cost=1.0, aM=4.0, tpR=0.0, fL=50, sL=150, don=50):
    H=[b["h"] for b in bars]; L=[b["l"] for b in bars]; C=[b["c"] for b in bars]
    f,s,A = ema(C,fL), ema(C,sL), atr(H,L,C,14)
    out=[]; pos=None
    for i in range(max(sL,don)+2, len(bars)):
        a=A[i]
        if a is None or a<=0: continue
        h1=max(H[i-don:i]); l1=min(L[i-don:i])
        up=f[i]>s[i]; dn=s[i]>f[i]
        xUp=f[i-1]<=s[i-1] and f[i]>s[i]; xDn=f[i-1]>=s[i-1] and f[i]<s[i]
        if pos:
            d,ep,st,r0,tp=pos
            if d>0:
                st=max(st, C[i]-aM*a)                     # the fixed trail
                if tp and H[i]>=tp: out.append((tp-ep-cost)/r0); pos=None
                elif L[i]<=st:      out.append((st-ep-cost)/r0); pos=None
                elif xDn and dn:    out.append((C[i]-ep-cost)/r0); pos=None
                else: pos=(d,ep,st,r0,tp)
            else:
                st=min(st, C[i]+aM*a)
                if tp and L[i]<=tp: out.append((ep-tp-cost)/r0); pos=None
                elif H[i]>=st:      out.append((ep-st-cost)/r0); pos=None
                elif xUp and up:    out.append((ep-C[i]-cost)/r0); pos=None
                else: pos=(d,ep,st,r0,tp)
            if pos: continue
        if pos is None:
            r0=aM*a
            if C[i]>h1 and up:
                pos=(1,C[i],C[i]-r0,r0, C[i]+tpR*r0 if tpR else 0)
            elif C[i]<l1 and dn:
                pos=(-1,C[i],C[i]+r0,r0, C[i]-tpR*r0 if tpR else 0)
    return out

def line(lbl, t, width=30):
    if len(t)<5: return f"  {lbl:<{width}}{len(t):>6}   too few"
    w=[x for x in t if x>0]; gl=abs(sum(x for x in t if x<=0))
    pf=sum(w)/gl if gl>0 else 99.0
    eq=0.0; pk=0.0; dd=0.0
    for r in t:
        eq+=r; pk=max(pk,eq); dd=max(dd,pk-eq)
    return (f"  {lbl:<{width}}{len(t):>6}{len(w)/len(t)*100:>7.1f}%"
            f"{sum(t):>+9.1f}R{sum(t)/len(t):>+8.3f}R{pf:>7.2f}{dd:>8.1f}R")

HDR = lambda w=30: f"  {'':<{w}}{'trds':>6}{'win':>8}{'netR':>10}{'exp':>9}{'PF':>7}{'maxDD':>8}"

gcd = load("gcdaily.json")
gc1h_raw = load("gc1h.json")["chart"]["result"][0]
ts,q = gc1h_raw["timestamp"], gc1h_raw["indicators"]["quote"][0]
gc1h=[{"t":t,"o":q["open"][i],"h":q["high"][i],"l":q["low"][i],"c":q["close"][i],"v":q["volume"][i] or 0}
      for i,t in enumerate(ts) if q["close"][i] is not None]
M=60
print("GOLD GC=F — trail_offset fixed to a 4x ATR distance\n")
print("TIMEFRAME  (cost 1 pt, atrMult 4, no target)")
print(HDR())
for lbl, bars in [("1h   (2y)",  resample(gc1h,60*M)),
                  ("2h   (2y)",  resample(gc1h,120*M)),
                  ("4h   (2y)",  resample(gc1h,240*M)),
                  ("8h   (2y)",  resample(gc1h,480*M)),
                  ("1d   (2y)",  resample(gc1h,1440*M)),
                  ("1d   (25y)", gcd),
                  ("2d   (25y)", resample(gcd,2*1440*M)),
                  ("1w   (25y)", resample(gcd,7*1440*M))]:
    print(line(f"{lbl}  [{len(bars)} bars]", run(bars)))

print("\nSTOP DISTANCE  (1d 25y — atrMult sets 1R)")
print(HDR())
for m in (1.5,2,3,4,5,6,8):
    print(line(f"stop {m}x ATR", run(gcd, aM=m)))

print("\nTARGET  (1d 25y, stop 4x ATR)")
print(HDR())
for tp in (0,1,1.5,2,3,4,6):
    print(line("no target (original)" if tp==0 else f"take profit at {tp}R", run(gcd, tpR=tp)))

print("\nBEST GEOMETRY x TIMEFRAME")
print(HDR())
for lbl,bars in [("4h  (2y)",resample(gc1h,240*M)),("1d (25y)",gcd),("1w (25y)",resample(gcd,7*1440*M))]:
    for m in (3,4,6):
        print(line(f"{lbl}  stop {m}x", run(bars, aM=m)))

def grid(name, bars):
    print(f"\n{name}   cell = netR / profit factor   (n = trade count)")
    print(f"  {'':<10}" + "".join(f"{('tp '+str(tp)+'R') if tp else 'no target':>15}" for tp in TPS))
    for m in STOPS:
        row=f"  stop {m:<5}"
        ns=[]
        for tp in TPS:
            t=run(bars, aM=m, tpR=tp); row+=f"{cell(t):>15}"; ns.append(len(t))
        print(row + "     n=" + "/".join(str(n) for n in ns))

STOPS=(2,3,4,6); TPS=(0,1,2,3,4)
gc4h = resample(gc1h,240*M)
print("GOLD GC=F — stop distance x target, crossed\n")
grid("1d  (25y, 6274 bars)", gcd)
grid("4h  (2y,  3714 bars)", gc4h)
grid("1h  (2y, 13720 bars)", resample(gc1h,60*M))

print("\n\nCOST SENSITIVITY  (1d 25y, best cells)")
print(HDR(24))
for m,tp in ((3,0),(2,0),(3,3),(4,0)):
    for c in (0.5,1.0,2.0,4.0):
        print(line(f"stop {m}x tp {tp or '-'}  cost {c}", run(gcd, cost=c, aM=m, tpR=tp), 24))
