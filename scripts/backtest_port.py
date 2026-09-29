"""Faithful Python port of multi_strategy_confirmation.pine, run on real bars.

Not a substitute for TradingView: different data source, and the fill model
is simplified. It answers the COMPARATIVE question the Pine backtest cannot
answer without a person toggling switches — what each filter does to trade
count and expectancy — and it answers it on real gold.

Results are in R multiples (each trade in units of its own initial risk), so
position sizing and compounding cannot flatter one configuration over
another. That is the distortion the 500-USD runs suffered from.
"""
import json, math, statistics as st
from dataclasses import dataclass, field

B = json.load(open("gc45.json"))
N = len(B)
O = [b["o"] for b in B]; H = [b["h"] for b in B]
L = [b["l"] for b in B]; C = [b["c"] for b in B]; V = [b["v"] for b in B]; T = [b["t"] for b in B]
D = [b["d"] for b in B]   # volume delta: up-closing sub-bar volume minus down

def rma(vals, n):
    out=[None]*len(vals); s=None
    for i,v in enumerate(vals):
        if v is None: out[i]=s; continue
        s = v if s is None else (s*(n-1)+v)/n
        out[i]=s if i>=n-1 else None
    return out

tr=[None]*N
for i in range(N):
    tr[i] = H[i]-L[i] if i==0 else max(H[i]-L[i], abs(H[i]-C[i-1]), abs(L[i]-C[i-1]))
ATR = rma(tr,14)

def pivots(vals,left,right,is_high):
    out=[None]*len(vals)
    for i in range(left,len(vals)-right):
        w=vals[i-left:i+right+1]
        if (is_high and vals[i]==max(w) and w.count(vals[i])==1) or \
           (not is_high and vals[i]==min(w) and w.count(vals[i])==1):
            out[i+right]=vals[i]
    return out

def sma(vals,n):
    out=[None]*len(vals); s=0.0
    for i,v in enumerate(vals):
        s+=v
        if i>=n: s-=vals[i-n]
        out[i]= s/n if i>=n-1 else None
    return out

def ema(vals,n):
    out=[None]*len(vals); k=2/(n+1); e=None
    for i,v in enumerate(vals):
        e = v if e is None else v*k + e*(1-k)
        out[i]=e
    return out

@dataclass
class Cfg:
    name: str
    minConf: int = 2
    holdBars: int = 0
    closeStrength: float = 0.0
    displacement: bool = False
    dispAtr: float = 0.8
    volSurge: bool = False
    volZ: float = 2.0
    useDelta: bool = False
    deltaRatio: float = 0.0   # |delta|/volume floor; 0 = sign only
    useOrb: bool = False
    useEmaVwap: bool = False
    breakevenR: float = 1.0
    trailAtr: float = 2.5
    trailPoints: float = 0.0    # >0 switches the trail to fixed points
    trailStep: float = 0.0      # stop only moves when it improves by this
    ban: tuple = ()             # level sources to refuse
    stopAtr: float = 1.5
    entryAtr: float = 0.1
    expiry: int = 5

@dataclass
class Res:
    trades: list = field(default_factory=list)
    tagged: list = field(default_factory=list)   # (source, R, ended_at_stop)
    skipped_no_room: int = 0
    signals: int = 0

def run(cfg: Cfg) -> Res:
    PL, PR = 10, 10
    ph, pl = pivots(H,PL,PR,True), pivots(L,PL,PR,False)
    volAvg, volEma = sma(V,20), ema(C,21)
    res = Res()

    lastPH=lastPL=brokenHigh=brokenLow=None; bias=0
    obD=[]; obS=[]; fvD=[]; fvS=[]           # (top,bot,bar)
    armLevel=armBar=None; armDir=0
    orbHigh=orbLow=None; orbReady=False; orbLd=orbSd=False; curDay=None
    vwapPV=vwapV=0.0; vwapDay=None
    pos=None; pendLevel=pendBar=None; pendDir=0; pendStop=None; pendSrc=None; posSrc=None

    for i in range(N):
        atr = ATR[i]
        day = T[i]//86400
        # --- session-anchored VWAP
        if vwapDay != day: vwapPV=vwapV=0.0; vwapDay=day
        tp=(H[i]+L[i]+C[i])/3; vwapPV+=tp*V[i]; vwapV+=V[i]
        vwap = vwapPV/vwapV if vwapV>0 else None
        # --- ORB window: first 45m block of the UTC day
        if curDay != day:
            curDay=day; orbHigh=orbLow=None; orbReady=False; orbLd=orbSd=False
        secs = T[i] % 86400
        if 13*3600 <= secs < 13*3600+2700:        # 13:00-13:45 UTC, NY cash open
            orbHigh = H[i] if orbHigh is None else max(orbHigh,H[i])
            orbLow  = L[i] if orbLow  is None else min(orbLow, L[i])
        elif orbHigh is not None:
            orbReady = True

        if ph[i] is not None: lastPH=ph[i]
        if pl[i] is not None: lastPL=pl[i]
        if atr is None or atr<=0 or i<25:
            continue

        c,o,h,l = C[i],O[i],H[i],L[i]
        body=abs(c-o); rng=h-l
        # --- zones: prune then detect
        for arr,isDem in ((obD,True),(obS,False),(fvD,True),(fvS,False)):
            arr[:] = [z for z in arr if not ((c<z[1]) if isDem else (c>z[0])) and i-z[2] <= 200][-6:]
        if body > 1.5*atr and i>1:
            (obD if c>o else obS).append((H[i-1],L[i-1],i))
        if i>3:
            if L[i-1]-H[i-3] > 0.25*atr: fvD.append((L[i-1],H[i-3],i))
            if L[i-3]-H[i-1] > 0.25*atr: fvS.append((L[i-3],H[i-1],i))

        # --- strategies
        rh = max(H[max(0,i-20):i]); rl = min(L[max(0,i-20):i])
        brkL, brkS = c>rh, c<rl
        bosL=bosS=False
        if lastPH is not None and c>lastPH and (brokenHigh is None or lastPH!=brokenHigh):
            if bias>=0: bosL=True
            brokenHigh=lastPH; bias=1
        if lastPL is not None and c<lastPL and (brokenLow is None or lastPL!=brokenLow):
            if bias<=0: bosS=True
            brokenLow=lastPL; bias=-1
        tol=0.5*atr
        srL = lastPL is not None and l<=lastPL+tol and c>lastPL
        srS = lastPH is not None and h>=lastPH-tol and c<lastPH
        swL = lastPL is not None and l<lastPL and c>lastPL
        swS = lastPH is not None and h>lastPH and c<lastPH
        obLv = max([z[0] for z in obD if l<=z[0] and c>z[0]], default=None)
        obSv = min([z[1] for z in obS if h>=z[1] and c<z[1]], default=None)
        fvLv = max([z[0] for z in fvD if l<=z[0] and c>z[0]], default=None)
        fvSv = min([z[1] for z in fvS if h>=z[1] and c<z[1]], default=None)
        orbL = cfg.useOrb and orbReady and not orbLd and orbHigh is not None and c>orbHigh
        orbS_ = cfg.useOrb and orbReady and not orbSd and orbLow is not None and c<orbLow
        if orbL: orbLd=True
        if orbS_: orbSd=True
        evL=evS=False
        if cfg.useEmaVwap and vwap is not None and i>0 and volEma[i-1] is not None:
            pv = (vwapPV-tp*V[i])/(vwapV-V[i]) if vwapV-V[i]>0 else None
            if pv is not None:
                evL = volEma[i-1]<=pv and volEma[i]>vwap
                evS = volEma[i-1]>=pv and volEma[i]<vwap

        # --- fakeout gates on the structure family
        disp = (not cfg.displacement) or body > cfg.dispAtr*atr
        cu = (c-l)/rng if rng>0 else .5; cd=(h-c)/rng if rng>0 else .5
        sUp = cfg.closeStrength<=0 or cu>=cfg.closeStrength
        sDn = cfg.closeStrength<=0 or cd>=cfg.closeStrength
        slvL = rh if brkL else (brokenHigh if bosL else None)
        slvS = rl if brkS else (brokenLow if bosS else None)
        rSL = (brkL or bosL) and disp and sUp and slvL is not None
        rSS = (brkS or bosS) and disp and sDn and slvS is not None

        structL=structS=False; sLvL=sLvS=None
        if cfg.holdBars==0:
            structL,structS,sLvL,sLvS = rSL,rSS,slvL,slvS
        else:
            if armBar is None and (rSL or rSS):
                armLevel = slvL if rSL else slvS; armBar=i; armDir = 1 if rSL else -1
            if armBar is not None and i-armBar >= cfg.holdBars:
                if armDir==1 and c>armLevel: structL=True; sLvL=armLevel
                if armDir==-1 and c<armLevel: structS=True; sLvS=armLevel
                armBar=None; armDir=0; armLevel=None

        # --- volume surge filter
        vok=True
        if cfg.volSurge:
            w=[v for v in V[max(0,i-20):i] if v]
            if len(w)>2 and st.pstdev(w)>0:
                vok = (V[i]-st.fmean(w))/st.pstdev(w) >= cfg.volZ
            else: vok=False

        # --- order-flow gate. Direction must agree, and optionally the
        # split must be lopsided enough to mean something: at deltaRatio
        # 0.3 a bar needs roughly a 65/35 split rather than 51/49.
        dOkL = dOkS = True
        if cfg.useDelta:
            dv = D[i]; tv = V[i]
            if tv <= 0:
                dOkL = dOkS = False
            else:
                dOkL = dv > 0 and abs(dv)/tv >= cfg.deltaRatio
                dOkS = dv < 0 and abs(dv)/tv >= cfg.deltaRatio

        rejL, rejS = srL or swL, srS or swS
        zL, zS = obLv is not None or fvLv is not None, obSv is not None or fvSv is not None
        vL = sum([structL, rejL, zL, orbL, evL])
        vS = sum([structS, rejS, zS, orbS_, evS])
        okL = vok and dOkL and vL>=cfg.minConf and vS==0
        okS = vok and dOkS and vS>=cfg.minConf and vL==0
        if okL or okS: res.signals += 1

        # --- manage an open position first
        if pos:
            d,ep,sl,r0,be,ext = pos
            if d>0:
                ext=max(ext,h)
                if not be and c >= ep + cfg.breakevenR*r0: be=True; sl=ep
                if be:
                    cand = ext - (cfg.trailPoints if cfg.trailPoints>0 else cfg.trailAtr*atr)
                    if cand >= sl + cfg.trailStep: sl = cand
                if l<=sl:
                    r=(sl-ep)/r0; res.trades.append(r); res.tagged.append((posSrc,r,True)); pos=None
                else: pos=(d,ep,sl,r0,be,ext)
            else:
                ext=min(ext,l)
                if not be and c <= ep - cfg.breakevenR*r0: be=True; sl=ep
                if be:
                    cand = ext + (cfg.trailPoints if cfg.trailPoints>0 else cfg.trailAtr*atr)
                    if cand <= sl - cfg.trailStep: sl = cand
                if h>=sl:
                    r=(ep-sl)/r0; res.trades.append(r); res.tagged.append((posSrc,r,True)); pos=None
                else: pos=(d,ep,sl,r0,be,ext)
            continue

        # --- a pending limit order
        if pendBar is not None:
            if pendDir==1 and l<=pendLevel:
                ep=min(pendLevel,o); r0=abs(ep-pendStop)
                if r0>0: pos=(1,ep,min(pendStop,ep-0.25*atr),r0,False,h); posSrc=pendSrc
                pendBar=None
            elif pendDir==-1 and h>=pendLevel:
                ep=max(pendLevel,o); r0=abs(ep-pendStop)
                if r0>0: pos=(-1,ep,max(pendStop,ep+0.25*atr),r0,False,l); posSrc=pendSrc
                pendBar=None
            elif i-pendBar >= cfg.expiry:
                pendBar=None
            if pos or pendBar is not None: continue

        # --- new order
        def pick(long):
            if long:
                for src,val in (("orderblock",obLv),("fvg",fvLv),
                                ("sweep" if swL else "sr" if srL else None, lastPL if (swL or srL) else None),
                                ("orb", orbHigh if orbL else None),
                                ("structure", sLvL if structL else None),
                                ("emavwap", vwap if evL else None)):
                    if src and val is not None and src not in cfg.ban: return src,val
            else:
                for src,val in (("orderblock",obSv),("fvg",fvSv),
                                ("sweep" if swS else "sr" if srS else None, lastPH if (swS or srS) else None),
                                ("orb", orbLow if orbS_ else None),
                                ("structure", sLvS if structS else None),
                                ("emavwap", vwap if evS else None)):
                    if src and val is not None and src not in cfg.ban: return src,val
            return None,None
        srcL,lvlL = pick(True)
        srcS,lvlS = pick(False)
        if okL and lvlL is not None:
            lp = lvlL + cfg.entryAtr*atr
            if lp < c: pendLevel=lp; pendBar=i; pendDir=1; pendStop=lvlL-cfg.stopAtr*atr; pendSrc=srcL
            else: res.skipped_no_room += 1
        elif okS and lvlS is not None:
            lp = lvlS - cfg.entryAtr*atr
            if lp > c: pendLevel=lp; pendBar=i; pendDir=-1; pendStop=lvlS+cfg.stopAtr*atr; pendSrc=srcS
            else: res.skipped_no_room += 1
    return res

def report(cfg, r):
    t=r.trades
    if not t:
        return f"{cfg.name:<34} {0:>4}  {'-':>7} {'-':>8} {'-':>7} {'-':>8}"
    w=[x for x in t if x>0]; los=[x for x in t if x<=0]
    gp=sum(w); gl=abs(sum(los))
    pf = gp/gl if gl>0 else float('inf')
    return (f"{cfg.name:<34} {len(t):>4}  {len(w)/len(t)*100:>6.1f}% "
            f"{sum(t):>7.2f}R {sum(t)/len(t):>6.3f}R {pf:>7.2f}")

def rep(cfg):
    r = run(cfg); t = r.trades
    if not t: return f"{cfg.name:<36} {0:>4}  {'-':>6} {'-':>8} {'-':>7} {'-':>6}"
    w=[x for x in t if x>0]; gl=abs(sum(x for x in t if x<=0))
    pf = sum(w)/gl if gl>0 else float('inf')
    return (f"{cfg.name:<36} {len(t):>4}  {len(w)/len(t)*100:>5.1f}% "
            f"{sum(t):>+7.2f}R {sum(t)/len(t):>+6.3f}R {pf:>6.2f}")

atrs=[a for a in ATR if a]
print(f"GC=F 45m, {N} bars.  ATR(14) median {sorted(atrs)[len(atrs)//2]:.1f} pts "
      f"(2.5xATR trail = {2.5*sorted(atrs)[len(atrs)//2]:.0f} pts)\n")
print(f"{'config':<36} {'trds':>4}  {'win':>6} {'net':>8} {'exp':>7} {'PF':>6}")
print("-"*74)
print("  -- which zone source to drop (surge + delta on) --")
for c in [
    Cfg("both zones (as shipped)", volSurge=True, useDelta=True),
    Cfg("ban FVG", volSurge=True, useDelta=True, ban=("fvg",)),
    Cfg("ban order block", volSurge=True, useDelta=True, ban=("orderblock",)),
    Cfg("ban both zones", volSurge=True, useDelta=True, ban=("orderblock","fvg")),
]: print(rep(c))
print("\n  -- same, unfiltered, where the losses actually were --")
for c in [
    Cfg("baseline both zones"),
    Cfg("baseline ban FVG", ban=("fvg",)),
    Cfg("baseline ban order block", ban=("orderblock",)),
    Cfg("baseline ban both zones", ban=("orderblock","fvg")),
]: print(rep(c))
print("\n  -- trailing: ATR vs fixed points (best config, FVG banned) --")
B2 = dict(volSurge=True, useDelta=True, ban=("fvg",))
for c in [
    Cfg("trail 2.5xATR (~37 pts)", **B2),
    Cfg("trail 7 pts, no step", trailPoints=7, **B2),
    Cfg("trail 7 pts, 3 pt step", trailPoints=7, trailStep=3, **B2),
    Cfg("trail 15 pts, 3 pt step", trailPoints=15, trailStep=3, **B2),
    Cfg("trail 25 pts, 3 pt step", trailPoints=25, trailStep=3, **B2),
    Cfg("trail 37 pts, 3 pt step", trailPoints=37, trailStep=3, **B2),
]: print(rep(c))
