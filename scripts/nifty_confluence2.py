import json, os, datetime, io, contextlib, importlib.util
SC=os.path.dirname(os.path.abspath(__file__))
spec=importlib.util.spec_from_file_location("bd", os.path.join(SC,"nifty_confluence.py"))
bd=importlib.util.module_from_spec(spec)
with contextlib.redirect_stdout(io.StringIO()): spec.loader.exec_module(bd)

nifty=json.load(open(os.path.join(SC,"niftyd.json")))
per=bd.load_constituents()
dates=[bd.day(b["t"]) for b in nifty]
B=bd.breadth(dates, per)

print("WHY MOST GATES DO NOTHING — breadth on index breakout days vs all days")
sig=[]; alld=[]
for d in dates:
    b=B.get(d)
    if b: alld.append(b)
for name,key in (("advancers","pct_adv"),("above own EMA20","pct_ema"),
                 ("making 50d high","pct_hi"),("traded-value delta","vdelta"),
                 ("names w/ rvol>1.5","pct_rvol")):
    v=sorted(x[key] for x in alld)
    print(f"  {name:<22} median across all days = {v[len(v)//2]:+.2f}")
print("  -> at a 50-day index high, breadth is already positive by construction;")
print("     a directional breadth gate re-states the signal instead of testing it.\n")

# is the rvol-breadth gate a smooth effect or a single lucky threshold?
print("VOLUME-EXPANSION BREADTH — threshold sweep (is it smooth or a spike?)")
print(bd.HDR(30))
for k in (0.05,0.10,0.15,0.20,0.25,0.30,0.35,0.40,0.45,0.50):
    g=(lambda k: lambda b,d: b["pct_rvol"]>k)(k)
    t,s_=bd.run(nifty,B,g)
    print(bd.line(f"names w/ rvol>1.5 over {int(k*100)}%",t,s_))

print("\nBY PERIOD — the gate that bit, across independent blocks")
blocks=[("2007-2012",2007,2012),("2013-2018",2013,2018),("2019-2026",2019,2026)]
PICK=[("(no gate)",lambda b,d:True),
      ("rvol-breadth > 20%",lambda b,d:b["pct_rvol"]>0.20),
      ("rvol-breadth > 30%",lambda b,d:b["pct_rvol"]>0.30),
      ("rvol-breadth > 35%",lambda b,d:b["pct_rvol"]>0.35)]
print(f"  {'':<24}" + "".join(f"{b[0]+'  n/PF/netR':>24}" for b in blocks))
for name,g in PICK:
    row=f"  {name:<24}"
    for lbl,y0,y1 in blocks:
        idx=[i for i,d in enumerate(dates) if y0<=d.year<=y1]
        bb=nifty[idx[0]:idx[-1]+1]
        t,_=bd.run(bb,B,g); r=bd.stat(t)
        row += f"{'--':>24}" if not r else f"{r[0]:>8} {r[4]:>6.2f} {r[2]:>+7.1f}R"
    print(row)

print("\nLONG vs SHORT  (NIFTY has a structural upward drift)")
def split_dir(bars,B,gate):
    L=[];S=[]
    H=[b["h"] for b in bars]; Lo=[b["l"] for b in bars]; C=[b["c"] for b in bars]
    f,s,A=bd.ema(C,50),bd.ema(C,150),bd.atr(H,Lo,C,14)
    pos=None
    for i in range(152,len(bars)):
        a=A[i]
        if a is None or a<=0: continue
        cost=C[i]*3.0/10000.0
        h1=max(H[i-50:i]); l1=min(Lo[i-50:i])
        up=f[i]>s[i]; dn=s[i]>f[i]
        xUp=f[i-1]<=s[i-1] and f[i]>s[i]; xDn=f[i-1]>=s[i-1] and f[i]<s[i]
        if pos:
            d,ep,stp,r0=pos
            done=None
            if d>0:
                stp=max(stp,C[i]-3.0*a)
                if Lo[i]<=stp: done=(stp-ep-cost)/r0
                elif xDn and dn: done=(C[i]-ep-cost)/r0
            else:
                stp=min(stp,C[i]+3.0*a)
                if H[i]>=stp: done=(ep-stp-cost)/r0
                elif xUp and up: done=(ep-C[i]-cost)/r0
            if done is None: pos=(d,ep,stp,r0); continue
            (L if d>0 else S).append(done); pos=None
        if pos is None:
            bu=C[i]>h1 and up; bdn=C[i]<l1 and dn
            if bu or bdn:
                d=1 if bu else -1
                b=B.get(bd.day(bars[i]["t"]))
                if b and gate(b,d): pos=(d,C[i],C[i]-d*3.0*a,3.0*a)
    return L,S
print(bd.HDR(30))
for name,g in PICK:
    L,S=split_dir(nifty,B,g)
    print(bd.line(f"{name}  LONG only",L,len(L)))
    print(bd.line(f"{name}  SHORT only",S,len(S)))
