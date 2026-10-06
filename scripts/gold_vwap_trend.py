"""The same idea, specified properly: a pullback needs a trend to pull back within.

The first pass gated only on which side of VWAP price sat, which is not a trend
filter -- it let the 9 EMA cross fire 1088 times in two years, most of them
noise. Here the trend is explicit, the pullback has to actually reach the 9 EMA,
and VWAP is tested as both a side filter and a slope filter.
"""
import json, datetime, sys
exec(open("/tmp/gvwap.py").read().split("def run(")[0])

# the helpers live after run() in the source, so they are restated here
def stat(v):
    if len(v)<5: return None
    w=[x for x in v if x>0]; gl=abs(sum(x for x in v if x<=0))
    pf=sum(w)/gl if gl>0 else 99.0
    eq=pk=dd=0.0
    for x in v: eq+=x; pk=max(pk,eq); dd=max(dd,pk-eq)
    return len(v), len(w)/len(v)*100, sum(v), sum(v)/len(v), pf, dd
def line(lbl,t,w=44):
    rr=stat([x["R"] for x in t])
    if not rr: return f"  {lbl:<{w}}{len(t):>6}   too few"
    n,wr,net,ex,pf,dd=rr
    return f"  {lbl:<{w}}{n:>6}{wr:>7.1f}%{net:>+9.1f}R{ex:>+8.3f}R{pf:>7.2f}{dd:>8.1f}R"
HD=lambda w=44: f"  {'':<{w}}{'trds':>6}{'win':>8}{'netR':>10}{'exp':>9}{'PF':>7}{'maxDD':>8}"

def run2(emaLen=9, trendFast=50, trendSlow=200, useVwap="side", side="both",
         stopMult=2.0, cost=0.5, anchor=22, needTouch=True, trail=True):
    VW, sess = build_vwap(B, anchor)
    A = atr_s(B, sess)
    e  = ema(C, emaLen)
    tf = ema(C, trendFast)
    tsl= ema(C, trendSlow)
    out=[]; pos=None
    for i in range(max(trendSlow, 30) + 2, len(B)):
        a=A[i]
        if a is None or a<=0: continue
        if pos:
            d,ep,stp,r0=pos
            if trail:
                stp = max(stp, C[i]-stopMult*a) if d>0 else min(stp, C[i]+stopMult*a)
            hit = (L[i]<=stp) if d>0 else (H[i]>=stp)
            if hit:
                out.append(dict(R=(((stp-ep) if d>0 else (ep-stp))-cost)/r0, dir=d))
                pos=None
            else:
                pos=(d,ep,stp,r0); continue
        if pos is None:
            vw = VW[i]
            if useVwap != "off" and vw is None: continue
            up = tf[i] > tsl[i]
            dn = tsl[i] > tf[i]
            # a real pullback: the bar before dipped to or through the 9 EMA
            touchedL = (not needTouch) or (L[i-1] <= e[i-1])
            touchedS = (not needTouch) or (H[i-1] >= e[i-1])
            vwOkL = True; vwOkS = True
            if useVwap == "side":
                vwOkL = C[i] > vw; vwOkS = C[i] < vw
            elif useVwap == "slope":
                vwOkL = VW[i-1] is not None and vw > VW[i-1]
                vwOkS = VW[i-1] is not None and vw < VW[i-1]
            elif useVwap == "both":
                vwOkL = C[i] > vw and VW[i-1] is not None and vw > VW[i-1]
                vwOkS = C[i] < vw and VW[i-1] is not None and vw < VW[i-1]
            sigL = up and touchedL and C[i-1] <= e[i-1] and C[i] > e[i] and vwOkL
            sigS = dn and touchedS and C[i-1] >= e[i-1] and C[i] < e[i] and vwOkS
            if side=="long": sigS=False
            if side=="short": sigL=False
            if sigL or sigS:
                d=1 if sigL else -1; r0=stopMult*a
                pos=(d,C[i],C[i]-d*r0,r0)
    return out

print("GOLD GC=F hourly — pullback WITH a trend filter (EMA50/200), stop 2x ATR\n")
print(HD())
for uv in ("off","side","slope","both"):
    tag = {"off":"no VWAP filter","side":"+ VWAP side","slope":"+ VWAP slope",
           "both":"+ VWAP side and slope"}[uv]
    for sd in ("long","short","both"):
        print(line(f"9 EMA pullback, {tag:<22} {sd}", run2(useVwap=uv, side=sd)))
    print()
print("STOP SWEEP  (9 EMA + trend + VWAP side, both sides)")
print(HD())
for sm in (1.5, 2.0, 3.0, 4.0):
    print(line(f"stop {sm}x ATR", run2(useVwap="side", stopMult=sm)))
print()
print("DOES REQUIRING AN ACTUAL TOUCH MATTER?")
print(HD())
print(line("touch required", run2(useVwap="side", needTouch=True)))
print(line("cross only, no touch", run2(useVwap="side", needTouch=False)))
print()
print("COST  (9 EMA + trend + VWAP side, stop 3x)")
print(HD())
for c in (0.0, 0.5, 1.0, 2.0):
    print(line(f"cost {c} pts", run2(useVwap="side", stopMult=3.0, cost=c)))
