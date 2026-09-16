"""VWAP + 9 EMA pullback, intraday, both sides.

NIFTY prints no volume at any timeframe so ta.vwap is unavailable on the index.
The VWAP here is synthesised from the constituents -- sum(price x volume) over
the basket divided by sum(volume), anchored to each session. That is a real
volume-weighted price of the underlying rather than a proxy.

Caveat stated up front: the classic VWAP/9EMA pullback is a 5-minute setup and
only 1-hour data reaches back far enough to test (723 sessions). Seven bars a
session means a 9 EMA spans more than a day, so this measures the idea's shape,
not the timeframe it is usually traded on.
"""
import json, os, glob, datetime, collections, sys
SC = "/home/user/pinescript/scripts"; sys.path.insert(0, SC)

IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
def sess(t): return datetime.datetime.fromtimestamp(t, IST).date()

def load(sym):
    return json.load(open(os.path.join(SC, "intra", f"{sym}.json")))

nf = load("NIFTY")
keys = [(b["t"], sess(b["t"])) for b in nf]
idx = {t: i for i, (t, _) in enumerate(keys)}

# synthetic VWAP: sum(pv) / sum(v) across constituents, reset each session
pv = collections.defaultdict(float)
vv = collections.defaultdict(float)
n_syms = 0
for p in sorted(glob.glob(os.path.join(SC, "intra", "*.json"))):
    sym = os.path.basename(p)[:-5]
    if sym == "NIFTY": continue
    n_syms += 1
    for b in json.load(open(p)):
        if b["v"] and b["v"] > 0:
            typ = (b["h"] + b["l"] + b["c"]) / 3.0
            pv[b["t"]] += typ * b["v"]
            vv[b["t"]] += b["v"]

vwap = [None] * len(nf)
cpv = cvv = 0.0
cur = None
for i, (t, d) in enumerate(keys):
    if d != cur:
        cur, cpv, cvv = d, 0.0, 0.0
    cpv += pv.get(t, 0.0); cvv += vv.get(t, 0.0)
    if cvv > 0:
        # scale the basket VWAP onto the index by the session's first-bar ratio
        vwap[i] = cpv / cvv
have = sum(1 for x in vwap if x)
print(f"synthetic VWAP from {n_syms} constituents on {have}/{len(nf)} bars")

# the basket VWAP lives on a different scale to the index, so compare the index
# to its OWN session VWAP built by scaling the basket's intraday path
scaled = [None] * len(nf)
cur = None; anchor = None
for i, (t, d) in enumerate(keys):
    if d != cur:
        cur = d
        anchor = (nf[i]["c"] / vwap[i]) if vwap[i] else None
    if vwap[i] and anchor:
        scaled[i] = vwap[i] * anchor

def ema(v, n):
    out=[None]*len(v); k=2/(n+1); e=None
    for i,x in enumerate(v):
        if x is None: out[i]=e; continue
        e = x if e is None else x*k+e*(1-k); out[i]=e
    return out

def atr_intraday(bars, keys, n=14):
    out=[None]*len(bars); vals=[]; prev=None; cur=None
    for i,b in enumerate(bars):
        d = keys[i][1]
        tr = b["h"]-b["l"] if d != cur else max(b["h"]-b["l"],
             abs(b["h"]-prev), abs(b["l"]-prev))
        cur = d; vals.append(tr)
        if len(vals) > n: vals.pop(0)
        out[i] = sum(vals)/len(vals) if len(vals)==n else None
        prev = b["c"]
    return out

C=[b["c"] for b in nf]; H=[b["h"] for b in nf]; L=[b["l"] for b in nf]
A = atr_intraday(nf, keys)

def run(emaLen=9, useVwap=True, side="both", stopMult=1.0, cost_bp=2.0, flat=True):
    e = ema(C, emaLen)
    lastbar = [i==len(nf)-1 or keys[i+1][1]!=keys[i][1] for i in range(len(nf))]
    out=[]; pos=None
    for i in range(30, len(nf)):
        a=A[i]
        if a is None or a<=0: continue
        cost=C[i]*cost_bp/10000.0
        if pos:
            d,ep,stp,r0=pos; done=None
            hit = (L[i]<=stp) if d>0 else (H[i]>=stp)
            if hit: done=stp
            elif flat and lastbar[i]: done=C[i]
            if done is not None:
                out.append(dict(R=(((done-ep) if d>0 else (ep-done))-cost)/r0, dir=d,
                                d=str(keys[i][1])))
                pos=None
            else:
                continue
        if pos is None and not lastbar[i] and e[i] is not None and e[i-1] is not None:
            vw = scaled[i]
            aboveV = (vw is None) or (C[i] > vw)
            belowV = (vw is None) or (C[i] < vw)
            if useVwap and vw is None: continue
            sigL = C[i-1] <= e[i-1] and C[i] > e[i] and (not useVwap or aboveV)
            sigS = C[i-1] >= e[i-1] and C[i] < e[i] and (not useVwap or belowV)
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
    for r in v: eq+=r; pk=max(pk,eq); dd=max(dd,pk-eq)
    return len(v), len(w)/len(v)*100, sum(v), sum(v)/len(v), pf, dd
def line(lbl,t,w=34):
    r=stat([x["R"] for x in t])
    if not r: return f"  {lbl:<{w}}{len(t):>6}   too few"
    n,wr,net,ex,pf,dd=r
    return f"  {lbl:<{w}}{n:>6}{wr:>7.1f}%{net:>+9.1f}R{ex:>+8.3f}R{pf:>7.2f}{dd:>8.1f}R"
HD=lambda w=34: f"  {'':<{w}}{'trds':>6}{'win':>8}{'netR':>10}{'exp':>9}{'PF':>7}{'maxDD':>8}"

print(f"\nNIFTY hourly, {len(set(k[1] for k in keys))} sessions, flat at the bell, 2bp\n")
print(HD())
for el in (9, 20):
    for uv in (False, True):
        tag = f"{el} EMA pullback" + (" + VWAP side" if uv else "")
        for sd in ("long","short"):
            print(line(f"{tag:<26} {sd}", run(emaLen=el, useVwap=uv, side=sd)))
    print()
print("BOTH SIDES TOGETHER")
print(HD())
for el in (9, 20):
    for uv in (False, True):
        print(line(f"{el} EMA" + (" + VWAP" if uv else "        ") + ", both sides",
                   run(emaLen=el, useVwap=uv, side="both")))
