"""Supply and demand zones from daily bars, and what they say about a breakout.

A zone is a base -- a run of quiet candles -- that a large candle leaves in a
hurry. The base is where the unfilled orders sat. A zone stays live until price
trades back through it.

For a breakout signal the useful question is not "is price in a zone" but "is
there anything overhead". A long breakout with fresh supply sitting half an ATR
above it has nowhere to go, and that is testable.
"""
import datetime

def atr_series(bars, n=14):
    H=[b["h"] for b in bars]; L=[b["l"] for b in bars]; C=[b["c"] for b in bars]
    tr=[H[0]-L[0]]+[max(H[i]-L[i],abs(H[i]-C[i-1]),abs(L[i]-C[i-1])) for i in range(1,len(H))]
    out=[None]*len(H); s=None
    for i,t in enumerate(tr):
        s=t if s is None else (s*(n-1)+t)/n
        out[i]=s if i>=n-1 else None
    return out

def find_zones(bars, base_max=3, quiet=0.8, depart=1.5, atr=None):
    """-> list of dicts: formed index, low, high, kind, and when it was broken.

    quiet  : a base candle's range must be under this multiple of ATR
    depart : the candle leaving the base must exceed this multiple of ATR
    """
    A = atr or atr_series(bars)
    H=[b["h"] for b in bars]; L=[b["l"] for b in bars]
    O=[b["o"] for b in bars]; C=[b["c"] for b in bars]
    zones=[]
    for i in range(20, len(bars)-1):
        a=A[i]
        if not a or a<=0: continue
        rng = H[i]-L[i]
        if rng < depart*a: continue                  # not a departure candle
        up = C[i] > O[i]
        # walk back over the base
        blo, bhi, n = None, None, 0
        for j in range(i-1, max(i-1-base_max, 0)-1, -1):
            if A[j] and (H[j]-L[j]) <= quiet*A[j]:
                blo = L[j] if blo is None else min(blo, L[j])
                bhi = H[j] if bhi is None else max(bhi, H[j])
                n += 1
            else: break
        if n == 0: continue
        zones.append(dict(i=i, lo=blo, hi=bhi, kind="demand" if up else "supply", broken=None))
    # a zone dies when price trades back through it
    for z in zones:
        for k in range(z["i"]+1, len(bars)):
            if z["kind"]=="demand" and L[k] < z["lo"]: z["broken"]=k; break
            if z["kind"]=="supply" and H[k] > z["hi"]: z["broken"]=k; break
    return zones

def overhead_supply(zones, i, price):
    """Distance to the nearest live supply zone above price, or None."""
    best=None
    for z in zones:
        if z["kind"]!="supply" or z["i"]>=i: continue
        if z["broken"] is not None and z["broken"]<=i: continue
        if z["lo"] > price:
            d = z["lo"]-price
            best = d if best is None else min(best,d)
    return best

def support_below(zones, i, price):
    best=None
    for z in zones:
        if z["kind"]!="demand" or z["i"]>=i: continue
        if z["broken"] is not None and z["broken"]<=i: continue
        if z["hi"] < price:
            d = price-z["hi"]
            best = d if best is None else min(best,d)
    return best

def room(zones, i, price, direction):
    """Room to run in ATR-free units: distance to the first obstacle ahead."""
    if direction > 0: return overhead_supply(zones, i, price)
    best=None
    for z in zones:
        if z["kind"]!="demand" or z["i"]>=i: continue
        if z["broken"] is not None and z["broken"]<=i: continue
        if z["hi"] < price:
            d = price-z["hi"]
            best = d if best is None else min(best,d)
    return best
