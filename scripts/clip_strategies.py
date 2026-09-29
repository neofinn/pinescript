"""Replications of the two clipped strategies, each with its OWN exits.

Forcing both through one generic stop/target harness would test a third
strategy that neither clip describes. A is always-in-or-flat and leaves on the
opposite label; B is a stop-and-target trade. They are run as filmed.
"""
from __future__ import annotations
import math, statistics
from intraday_lab import ema, rma, true_range


def wma(v, n):
    out=[None]*len(v); d=n*(n+1)/2
    for i in range(n-1,len(v)):
        out[i]=sum(v[i-n+1+k]*(k+1) for k in range(n))/d
    return out


def hma(v, n):
    h=max(1,int(n/2)); s=max(1,int(round(math.sqrt(n))))
    a,b=wma(v,h),wma(v,n)
    raw=[None]*len(v)
    for i in range(len(v)):
        if a[i] is not None and b[i] is not None: raw[i]=2*a[i]-b[i]
    start=next((i for i,x in enumerate(raw) if x is not None), len(v))
    filled=[raw[i] if raw[i] is not None else 0.0 for i in range(len(v))]
    w=wma(filled,s)
    return [w[i] if i>=start+s else None for i in range(len(v))]


def pivots(bars, prd):
    """Confirmed pivots, published prd bars late. Earlier would be lookahead."""
    ph=[None]*len(bars); pl=[None]*len(bars)
    for i in range(prd, len(bars)-prd):
        h,l=bars[i]["h"],bars[i]["l"]
        if all(bars[j]["h"]<=h for j in range(i-prd,i+prd+1) if j!=i): ph[i+prd]=h
        if all(bars[j]["l"]>=l for j in range(i-prd,i+prd+1) if j!=i): pl[i+prd]=l
    return ph,pl


def pps_supertrend(bars, prd=2, factor=3.0, atr_len=10):
    """Pivot Point SuperTrend, the clip's exact inputs 2 / 3 / 10.

    The centre is a running weighted mean of confirmed pivots: each new pivot
    pulls it one third of the way. Bands sit factor x ATR either side, and the
    trend flips when close crosses the opposite trailing band.
    """
    n=len(bars); c=[b["c"] for b in bars]
    atr=rma(true_range(bars), atr_len)
    ph,pl=pivots(bars,prd)
    centre=None; tUp=tDn=None; trend=0
    trend_s=[0]*n; trail=[None]*n
    for i in range(n):
        last = ph[i] if ph[i] is not None else pl[i]
        if last is not None:
            centre = last if centre is None else (centre*2.0+last)/3.0
        if centre is None or atr[i] is None:
            trend_s[i]=trend; continue
        up=centre-factor*atr[i]; dn=centre+factor*atr[i]
        pc=c[i-1] if i>0 else c[i]
        ptU = tUp if tUp is not None else up
        ptD = tDn if tDn is not None else dn
        nU = max(up,ptU) if pc>ptU else up
        nD = min(dn,ptD) if pc<ptD else dn
        trend = 1 if c[i]>ptD else (-1 if c[i]<ptU else (trend or 1))
        tUp,tDn=nU,nD
        trend_s[i]=trend; trail[i]= tUp if trend==1 else tDn
    return trend_s, trail


def strategy_A(bars, hma1=21, hma2=55, use_hma=True, prd=2, factor=3.0,
               atr_len=10):
    """PPS Super HMA: enter on the SuperTrend flip, leave on the opposite."""
    n=len(bars); c=[b["c"] for b in bars]
    trend,_=pps_supertrend(bars,prd,factor,atr_len)
    h1,h2=hma(c,hma1),hma(c,hma2)
    sig=[0]*n
    for i in range(1,n):
        if trend[i]==trend[i-1] or trend[i]==0: continue
        up1 = h1[i] is not None and h1[i-1] is not None and h1[i]>h1[i-1]
        up2 = h2[i] is not None and h2[i-1] is not None and h2[i]>h2[i-1]
        if trend[i]==1 and (not use_hma or (up1 and up2)): sig[i]=1
        elif trend[i]==-1 and (not use_hma or (not up1 and not up2)): sig[i]=-1
    return sig, trend


def run_A(bars, sig, trend, cost=0.02):
    """Always-in-or-flat: the position closes when the trend flips against it."""
    trades=[]; pos=None
    for i in range(len(bars)-1):
        if pos is not None and trend[i]==-pos["side"]:
            px=bars[i]["c"]
            trades.append(dict(net=pos["side"]*(px-pos["entry"])-cost,
                               bars=i-pos["i"]))
            pos=None
        if pos is None and sig[i]!=0:
            pos=dict(side=sig[i], entry=bars[i+1]["o"], i=i+1)
    return trades


def strategy_B(bars, ma_len=200, ma_type="EMA", touch_atr=0.25, slope_bars=5,
               req_close=True, cooldown=10, atr_len=14):
    """MA pullback: trade INTO the band around a rising MA and close back out."""
    n=len(bars); c=[b["c"] for b in bars]
    ma = ema(c,ma_len) if ma_type=="EMA" else hma(c,ma_len)
    atr=rma(true_range(bars), atr_len)
    sig=[0]*n; last=-10**9
    for i in range(max(ma_len,slope_bars)+2, n):
        if ma[i] is None or atr[i] is None: continue
        if i-last < cooldown: continue
        z=atr[i]*touch_atr
        rising = ma[i] > ma[i-slope_bars]
        falling = ma[i] < ma[i-slope_bars]
        b=bars[i]
        if rising and b["l"]<=ma[i]+z and b["l"]>=ma[i]-z*3.0 and \
           (not req_close or b["c"]>ma[i]):
            sig[i]=1; last=i
        elif falling and b["h"]>=ma[i]-z and b["h"]<=ma[i]+z*3.0 and \
             (not req_close or b["c"]<ma[i]):
            sig[i]=-1; last=i
    return sig, atr


def run_B(bars, sig, atr, rr=3.0, stop_buf=0.1, cost=0.02, max_hold=200):
    """Stop under the pullback's own low; target an R multiple."""
    trades=[]; pos=None
    for i in range(len(bars)-1):
        if pos is not None:
            b=bars[i]; s=pos["side"]
            hs = b["l"]<=pos["stop"] if s>0 else b["h"]>=pos["stop"]
            ht = b["h"]>=pos["targ"] if s>0 else b["l"]<=pos["targ"]
            px = pos["stop"] if hs else (pos["targ"] if ht else
                 (b["c"] if i-pos["i"]>=max_hold else None))
            if px is not None:
                trades.append(dict(net=s*(px-pos["entry"])-cost, bars=i-pos["i"]))
                pos=None
        if pos is None and sig[i]!=0 and atr[i]:
            s=sig[i]; e=bars[i+1]["o"]
            raw = bars[i]["l"]-atr[i]*stop_buf if s>0 else bars[i]["h"]+atr[i]*stop_buf
            stop = min(raw, e-0.01) if s>0 else max(raw, e+0.01)
            risk = abs(e-stop)
            if risk<=0: continue
            pos=dict(side=s, entry=e, stop=stop, targ=e+s*risk*rr, i=i+1)
    return trades


def sc(t):
    if not t: return dict(n=0,pf=0.0,win=0.0,net=0.0,med=0.0,bars=0.0)
    w=sum(x["net"] for x in t if x["net"]>0); l=-sum(x["net"] for x in t if x["net"]<=0)
    return dict(n=len(t), pf=(w/l) if l else float("inf"),
                win=sum(1 for x in t if x["net"]>0)/len(t)*100,
                net=sum(x["net"] for x in t),
                med=statistics.median(x["net"] for x in t),
                bars=statistics.mean(x["bars"] for x in t))
