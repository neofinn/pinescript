import json, os, io, contextlib, importlib.util
SC=os.path.dirname(os.path.abspath(__file__))
spec=importlib.util.spec_from_file_location("bd", os.path.join(SC,"nifty_confluence.py"))
bd=importlib.util.module_from_spec(spec)
with contextlib.redirect_stdout(io.StringIO()): spec.loader.exec_module(bd)
spec2=importlib.util.spec_from_file_location("b2", os.path.join(SC,"nifty_confluence2.py"))

nifty=json.load(open(os.path.join(SC,"niftyd.json")))
per=bd.load_constituents(); dates=[bd.day(b["t"]) for b in nifty]
B=bd.breadth(dates, per)

def run_long(bars,B,gate,aM=3.0,cost_bp=3.0):
    H=[b["h"] for b in bars]; Lo=[b["l"] for b in bars]; C=[b["c"] for b in bars]
    f,s,A=bd.ema(C,50),bd.ema(C,150),bd.atr(H,Lo,C,14)
    out=[];pos=None;sigs=0
    for i in range(152,len(bars)):
        a=A[i]
        if a is None or a<=0: continue
        cost=C[i]*cost_bp/10000.0
        h1=max(H[i-50:i]); up=f[i]>s[i]
        xDn=f[i-1]>=s[i-1] and f[i]<s[i]; dn=s[i]>f[i]
        if pos:
            ep,stp,r0=pos
            stp=max(stp,C[i]-aM*a)
            if Lo[i]<=stp: out.append((stp-ep-cost)/r0); pos=None
            elif xDn and dn: out.append((C[i]-ep-cost)/r0); pos=None
            else: pos=(ep,stp,r0)
            if pos: continue
        if pos is None and C[i]>h1 and up:
            sigs+=1
            b=B.get(bd.day(bars[i]["t"]))
            if b and gate(b): pos=(C[i],C[i]-aM*a,aM*a)
    return out,sigs

G=[("long-only, no gate",      lambda b: True),
   ("long-only, rvol-br >10%", lambda b: b["pct_rvol"]>0.10),
   ("long-only, rvol-br >20%", lambda b: b["pct_rvol"]>0.20),
   ("long-only, rvol-br >30%", lambda b: b["pct_rvol"]>0.30),
   ("long-only, rvol-br >40%", lambda b: b["pct_rvol"]>0.40)]

print("NIFTY 50 LONG-ONLY, 2007-2026 — Donchian(50)+EMA trend, stop 3x ATR, 3bp cost")
print(bd.HDR(28))
for n,g in G:
    t,s_=run_long(nifty,B,g); print(bd.line(n,t,s_,28))

print("\nACROSS INDEPENDENT BLOCKS")
blocks=[("2007-2012",2007,2012),("2013-2018",2013,2018),("2019-2026",2019,2026)]
print(f"  {'':<28}"+"".join(f"{b[0]+' n/PF/netR':>24}" for b in blocks))
for n,g in G:
    row=f"  {n:<28}"
    for lbl,y0,y1 in blocks:
        idx=[i for i,d in enumerate(dates) if y0<=d.year<=y1]
        t,_=run_long(nifty[idx[0]:idx[-1]+1],B,g); r=bd.stat(t)
        row += f"{'--':>24}" if not r else f"{r[0]:>8} {r[4]:>6.2f} {r[2]:>+7.1f}R"
    print(row)

print("\nSTOP DISTANCE  (long-only, rvol-breadth > 30%)")
print(bd.HDR(28))
for m in (2,3,4,6):
    t,s_=run_long(nifty,B,lambda b:b["pct_rvol"]>0.30,aM=m); print(bd.line(f"stop {m}x ATR",t,s_,28))

print("\nCOST SENSITIVITY  (long-only, rvol-breadth > 30%, stop 3x)")
print(bd.HDR(28))
for c in (3.0,10.0,20.0,40.0):
    t,s_=run_long(nifty,B,lambda b:b["pct_rvol"]>0.30,cost_bp=c)
    print(bd.line(f"cost {c:.0f} bp round turn",t,s_,28))

print("\nSURVIVORSHIP CHECK — which gates depend on today's index membership?")
print("  directional breadth (advancers, above-EMA) uses today's winners, so it is")
print("  biased upward by construction. rvol-breadth compares each stock to its OWN")
print("  20-day volume mean: scale-free and membership-neutral. The gates that were")
print("  contaminated are exactly the ones that did nothing.")
