"""Pullback vs breakout, directionless vs directional volume, both sides."""
import json, os, datetime, sys
SC = "/home/user/pinescript/scripts"; sys.path.insert(0, SC)
from indices_run import ema, atr, stat

def day(t): return datetime.datetime.fromtimestamp(t, datetime.UTC).date()
nf = json.load(open(os.path.join(SC, "niftyd.json")))
BR = {datetime.date.fromisoformat(k): tuple(v)
      for k, v in json.load(open(os.path.join(SC, "nifty_dir_breadth.json"))).items()}
DATES = [day(b["t"]) for b in nf]

# percentile thresholds per side, so the up/down asymmetry is handled by the data
ups = sorted(v[0] for v in BR.values()); dns = sorted(v[1] for v in BR.values())
tots= sorted(v[2] for v in BR.values())
def pct(arr, p): return arr[int(len(arr)*p)]

def run(bars, entry="pullback", gate=None, gp=0.70, side="both",
        aM=3.0, cost_bp=3.0, don=50, pbLen=20, dipWithin=10):
    H=[b["h"] for b in bars]; L=[b["l"] for b in bars]; C=[b["c"] for b in bars]
    f,s,A = ema(C,50), ema(C,150), atr(H,L,C,14)
    e20 = ema(C, pbLen)
    upT=[None]*len(bars); dnT=[None]*len(bars)
    out=[]; pos=None
    thU = pct(ups, gp); thD = pct(dns, gp); thT = pct(tots, gp)
    for i in range(152, len(bars)):
        a=A[i]
        if a is None or a<=0: continue
        cost=C[i]*cost_bp/10000.0
        up=f[i]>s[i]; dn=s[i]>f[i]
        xUp=f[i-1]<=s[i-1] and f[i]>s[i]; xDn=f[i-1]>=s[i-1] and f[i]<s[i]
        if pos:
            d,ep,stp,r0,ei=pos; done=None
            if d>0:
                stp=max(stp,C[i]-aM*a)
                if L[i]<=stp: done=stp
                elif xDn and dn: done=C[i]
            else:
                stp=min(stp,C[i]+aM*a)
                if H[i]>=stp: done=stp
                elif xUp and up: done=C[i]
            if done is None: pos=(d,ep,stp,r0,ei); continue
            out.append(dict(R=(((done-ep) if d>0 else (ep-done))-cost)/r0, dir=d,
                            entry=str(DATES[ei])))
            pos=None
        if pos is None:
            b=BR.get(DATES[i])
            if entry=="breakout":
                sigL = C[i]>max(H[i-don:i]) and up
                sigS = C[i]<min(L[i-don:i]) and dn
            else:
                dipped_dn = any(C[j] < e20[j] for j in range(max(i-dipWithin,0), i))
                dipped_up = any(C[j] > e20[j] for j in range(max(i-dipWithin,0), i))
                sigL = up and dipped_dn and C[i-1] <= e20[i-1] and C[i] > e20[i]
                sigS = dn and dipped_up and C[i-1] >= e20[i-1] and C[i] < e20[i]
            if side=="long": sigS=False
            if side=="short": sigL=False
            if gate is not None and b is not None:
                if gate=="plain":
                    ok = b[2] > thT
                    sigL = sigL and ok; sigS = sigS and ok
                elif gate=="directional":
                    sigL = sigL and b[0] > thU
                    sigS = sigS and b[1] > thD
            elif gate is not None:
                sigL=False; sigS=False
            if sigL or sigS:
                d=1 if sigL else -1; r0=aM*a
                pos=(d,C[i],C[i]-d*r0,r0,i)
    return out

def line(lbl, t, w=38):
    v=[x["R"] for x in t]; r=stat(v)
    if not r: return f"  {lbl:<{w}}{len(v):>6}   too few"
    n,wr,net,ex,pf,dd=r
    per_yr = n/19.0
    return (f"  {lbl:<{w}}{n:>6}{per_yr:>7.1f}{wr:>7.1f}%{net:>+9.1f}R"
            f"{ex:>+8.3f}R{pf:>7.2f}{dd:>8.1f}R")
H=lambda w=38: (f"  {'':<{w}}{'trds':>6}{'/yr':>7}{'win':>8}{'netR':>10}"
                f"{'exp':>9}{'PF':>7}{'maxDD':>8}")

print("NIFTY daily 2007-2026 — entry type x volume gate x side\n")
print(H())
for entry in ("breakout","pullback"):
    for gate in (None,"plain","directional"):
        g = "no gate" if gate is None else gate
        for side in ("long","short"):
            t=run(nf, entry=entry, gate=gate, side=side)
            print(line(f"{entry:<9} {g:<12} {side}", t))
    print()
