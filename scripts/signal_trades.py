import json, os, io, contextlib, importlib.util, datetime
S="/home/user/pinescript/scripts"
spec=importlib.util.spec_from_file_location("bd", os.path.join(S,"nifty_confluence.py"))
bd=importlib.util.module_from_spec(spec)
with contextlib.redirect_stdout(io.StringIO()): spec.loader.exec_module(bd)

nifty=json.load(open(os.path.join(S,"niftyd.json")))
dates=[bd.day(b["t"]) for b in nifty]
B=bd.breadth(dates, {})

def trades(bars,B,gate,aM=3.0,cost_bp=3.0,long_only=False):
    H=[b["h"] for b in bars]; Lo=[b["l"] for b in bars]; C=[b["c"] for b in bars]
    f,s,A=bd.ema(C,50),bd.ema(C,150),bd.atr(H,Lo,C,14)
    out=[];pos=None
    for i in range(152,len(bars)):
        a=A[i]
        if a is None or a<=0: continue
        cost=C[i]*cost_bp/10000.0
        h1=max(H[i-50:i]); l1=min(Lo[i-50:i])
        up=f[i]>s[i]; dn=s[i]>f[i]
        xUp=f[i-1]<=s[i-1] and f[i]>s[i]; xDn=f[i-1]>=s[i-1] and f[i]<s[i]
        if pos:
            d,ep,stp,r0,ei=pos; done=None;why=None
            if d>0:
                stp=max(stp,C[i]-aM*a)
                if Lo[i]<=stp: done=stp;why="stop"
                elif xDn and dn: done=C[i];why="cross"
            else:
                stp=min(stp,C[i]+aM*a)
                if H[i]>=stp: done=stp;why="stop"
                elif xUp and up: done=C[i];why="cross"
            if done is None: pos=(d,ep,stp,r0,ei); continue
            R=((done-ep) if d>0 else (ep-done))-cost
            out.append(dict(dir=d,entry=str(dates[ei]),exit=str(dates[i]),
                            ep=round(ep,2),xp=round(done,2),R=round(R/r0,3),
                            bars=i-ei,why=why,pct=round(((done-ep) if d>0 else (ep-done))/ep*100,2)))
            pos=None
        if pos is None:
            bu=C[i]>h1 and up; bdn=(C[i]<l1 and dn) and not long_only
            if bu or bdn:
                d=1 if bu else -1
                b=B.get(bd.day(bars[i]["t"]))
                if b and gate(b): pos=(d,C[i],C[i]-d*aM*a,aM*a,i)
    return out

g30=lambda b: b["pct_rvol"]>0.30
T=trades(nifty,B,g30)
json.dump(T, open("/tmp/claude-0/-home-user-pinescript/6b4bb2fe-c45d-5f96-b3e4-1392c689d1fc/scratchpad/trades30.json","w"), indent=1)
w=[t for t in T if t["R"]>0]
print(f"rvol-breadth>30%, both directions: {len(T)} trades, {len(w)/len(T)*100:.1f}% win, netR {sum(t['R'] for t in T):+.1f}")
print(f"  longs {sum(1 for t in T if t['dir']>0)}  shorts {sum(1 for t in T if t['dir']<0)}")
print(f"  hold: median {sorted(t['bars'] for t in T)[len(T)//2]} bars, max {max(t['bars'] for t in T)}")
print(f"  date range {T[0]['entry']} -> {T[-1]['exit']}")
byy={}
for t in T: byy.setdefault(t["entry"][:4],0); byy[t["entry"][:4]]+=1
print("  per year:", " ".join(f"{k}:{v}" for k,v in sorted(byy.items())))
print()
print(f"{'dir':>4} {'entry':>11} {'exit':>11} {'bars':>5} {'entry px':>9} {'exit px':>9} {'move%':>7} {'R':>7} why")
for t in T:
    print(f"{'LONG' if t['dir']>0 else 'SHORT':>5} {t['entry']:>10} {t['exit']:>11} {t['bars']:>5} "
          f"{t['ep']:>9.1f} {t['xp']:>9.1f} {t['pct']:>+7.2f} {t['R']:>+7.2f} {t['why']}")
