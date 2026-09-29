"""VWAP + 9 EMA pullback on gold, both sides.

GC=F carries real volume (corr with absolute return +0.46 hourly), so the VWAP
is the genuine article rather than the synthetic basket NIFTY needed.

CME gold runs 23 hours with the break at 21:00 UTC, so the session -- and the
VWAP anchor -- starts at 22:00 UTC. Anchoring at midnight instead would reset
VWAP in the middle of the US afternoon, which is why the anchor is swept rather
than assumed.
"""
import json, datetime, collections, sys

r = json.load(open("/home/user/pinescript/scripts/gc1h.json"))["chart"]["result"][0]
ts = r["timestamp"]; q = r["indicators"]["quote"][0]
B = [{"t": t, "o": q["open"][i], "h": q["high"][i], "l": q["low"][i],
      "c": q["close"][i], "v": q["volume"][i] or 0}
     for i, t in enumerate(ts) if q["close"][i] is not None]

def session_of(t, anchor_hour):
    d = datetime.datetime.fromtimestamp(t, datetime.UTC)
    return (d - datetime.timedelta(hours=anchor_hour)).date()

def build_vwap(bars, anchor_hour):
    out = [None]*len(bars); cpv = cvv = 0.0; cur = None
    sess = []
    for i, b in enumerate(bars):
        s = session_of(b["t"], anchor_hour)
        if s != cur:
            cur, cpv, cvv = s, 0.0, 0.0
        typ = (b["h"] + b["l"] + b["c"]) / 3.0
        cpv += typ * b["v"]; cvv += b["v"]
        out[i] = (cpv / cvv) if cvv > 0 else None
        sess.append(s)
    return out, sess

def ema(v, n):
    out=[None]*len(v); k=2/(n+1); e=None
    for i,x in enumerate(v):
        e = x if e is None else x*k+e*(1-k); out[i]=e
    return out

def atr_s(bars, sess, n=14):
    out=[None]*len(bars); vals=[]; prev=None; cur=None
    for i,b in enumerate(bars):
        tr = b["h"]-b["l"] if sess[i]!=cur else max(b["h"]-b["l"],
             abs(b["h"]-prev), abs(b["l"]-prev))
        cur=sess[i]; vals.append(tr)
        if len(vals)>n: vals.pop(0)
        out[i]=sum(vals)/len(vals) if len(vals)==n else None
        prev=b["c"]
    return out

C=[b["c"] for b in B]; H=[b["h"] for b in B]; L=[b["l"] for b in B]

def run(emaLen=9, useVwap=True, side="both", stopMult=1.5, cost=0.5,
        anchor=22, flat=False, trail=True):
    VW, sess = build_vwap(B, anchor)
    A = atr_s(B, sess)
    e = ema(C, emaLen)
    last = [i==len(B)-1 or sess[i+1]!=sess[i] for i in range(len(B))]
    out=[]; pos=None
    for i in range(30, len(B)):
        a=A[i]
        if a is None or a<=0: continue
        if pos:
            d,ep,stp,r0=pos; done=None
            if trail:
                stp = max(stp, C[i]-stopMult*a) if d>0 else min(stp, C[i]+stopMult*a)
            hit = (L[i]<=stp) if d>0 else (H[i]>=stp)
            if hit: done=stp
            elif flat and last[i]: done=C[i]
            if done is not None:
                out.append(dict(R=(((done-ep) if d>0 else (ep-done))-cost)/r0, dir=d))
                pos=None
            else:
                pos=(d,ep,stp,r0); continue
        if pos is None and not (flat and last[i]):
            vw = VW[i]
            if useVwap and vw is None: continue
            sigL = C[i-1] <= e[i-1] and C[i] > e[i] and (not useVwap or C[i] > vw)
            sigS = C[i-1] >= e[i-1] and C[i] < e[i] and (not useVwap or C[i] < vw)
            if side=="long": sigS=False
            if side=="short": sigL=False
            if sigL or sigS:
                d=1 if sigL else -1; r0=stopMult*a
                pos=(d,C[i],C[i]-d*r0,r0)
    return out

def stat(v):
    if len(v)<5: return None
    w=[x for x in v if x>0]; gl=abs(sum(x for x in v if x<=0))
    pf=sum(w)/gl if gl>0 else 99.0
    eq=pk=dd=0.0
    for x in v: eq+=x; pk=max(pk,eq); dd=max(dd,pk-eq)
    return len(v), len(w)/len(v)*100, sum(v), sum(v)/len(v), pf, dd
def line(lbl,t,w=36):
    rr=stat([x["R"] for x in t])
    if not rr: return f"  {lbl:<{w}}{len(t):>6}   too few"
    n,wr,net,ex,pf,dd=rr
    return f"  {lbl:<{w}}{n:>6}{wr:>7.1f}%{net:>+9.1f}R{ex:>+8.3f}R{pf:>7.2f}{dd:>8.1f}R"
HD=lambda w=36: f"  {'':<{w}}{'trds':>6}{'win':>8}{'netR':>10}{'exp':>9}{'PF':>7}{'maxDD':>8}"

print("GOLD GC=F hourly, 2y, true VWAP from its own volume, 0.5pt cost\n")
print(HD())
for el in (9, 20):
    for uv in (False, True):
        tag = f"{el} EMA pullback" + (" + VWAP side" if uv else "")
        for sd in ("long","short"):
            print(line(f"{tag:<28} {sd}", run(emaLen=el, useVwap=uv, side=sd)))
    print()
print("BOTH SIDES")
print(HD())
for el in (9,20):
    for uv in (False,True):
        print(line(f"{el} EMA" + (" + VWAP" if uv else "       ") + ", both", 
                   run(emaLen=el, useVwap=uv, side="both")))
print()
print("VWAP ANCHOR SWEEP  (9 EMA + VWAP, both sides)")
print(HD())
for an in (0, 13, 22):
    print(line(f"anchor {an:02d}:00 UTC", run(emaLen=9, useVwap=True, side="both", anchor=an)))
print()
print("STOP AND EXIT  (9 EMA + VWAP, both sides, anchor 22)")
print(HD())
for sm in (1.0, 1.5, 2.0, 3.0):
    print(line(f"stop {sm}x ATR, trailed", run(emaLen=9, stopMult=sm)))
print(line("stop 1.5x, flat at session end", run(emaLen=9, stopMult=1.5, flat=True)))
print(line("stop 1.5x, no trail", run(emaLen=9, stopMult=1.5, trail=False)))
print()
print("COST SENSITIVITY  (9 EMA + VWAP both sides, stop 1.5x)")
print(HD())
for c in (0.0, 0.5, 1.0, 2.0):
    print(line(f"cost {c} pts round turn", run(emaLen=9, cost=c)))
