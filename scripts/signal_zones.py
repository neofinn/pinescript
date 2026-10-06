"""The volume-surge signal with supply/demand room as an added filter.

The gate stays what it was -- an unusual share of constituents trading heavily.
What is added is whether the breakout has anywhere to go: a long that runs
straight into live supply is taking the same risk for less reward.

Risk is a flat 1R per trade and reward is left uncapped, so the trail decides
the exit rather than a target.
"""
import json, os, io, contextlib, importlib.util, datetime, sys
SC = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SC)
import zones as Z

spec = importlib.util.spec_from_file_location("bd", os.path.join(SC, "nifty_confluence.py"))
bd = importlib.util.module_from_spec(spec)
with contextlib.redirect_stdout(io.StringIO()): spec.loader.exec_module(bd)

NIFTY = json.load(open(os.path.join(SC, "niftyd.json")))
DATES = [bd.day(b["t"]) for b in NIFTY]
B = bd.breadth(DATES, {})
ATR = Z.atr_series(NIFTY)
ZONES = Z.find_zones(NIFTY, atr=ATR)

def trades(bars, gate, room_min=None, aM=3.0, cost_bp=3.0, don=50, long_only=False):
    H=[b["h"] for b in bars]; L=[b["l"] for b in bars]; C=[b["c"] for b in bars]
    f,s,A = bd.ema(C,50), bd.ema(C,150), ATR
    out=[]; pos=None; skipped=0
    for i in range(152, len(bars)):
        a=A[i]
        if a is None or a<=0: continue
        cost=C[i]*cost_bp/10000.0
        h1=max(H[i-don:i]); l1=min(L[i-don:i])
        up=f[i]>s[i]; dn=s[i]>f[i]
        xUp=f[i-1]<=s[i-1] and f[i]>s[i]; xDn=f[i-1]>=s[i-1] and f[i]<s[i]
        if pos:
            d,ep,stp,r0,ei=pos; done=None
            if d>0:
                stp=max(stp, C[i]-aM*a)
                if L[i]<=stp: done=stp
                elif xDn and dn: done=C[i]
            else:
                stp=min(stp, C[i]+aM*a)
                if H[i]>=stp: done=stp
                elif xUp and up: done=C[i]
            if done is None: pos=(d,ep,stp,r0,ei); continue
            R=((done-ep) if d>0 else (ep-done))-cost
            out.append(dict(dir=d, entry=str(DATES[ei]), exit=str(DATES[i]),
                            ep=round(ep,2), xp=round(done,2), R=round(R/r0,3),
                            bars=i-ei, pct=round(((done-ep) if d>0 else (ep-done))/ep*100,2)))
            pos=None
        if pos is None:
            bu=C[i]>h1 and up; bdn=(C[i]<l1 and dn) and not long_only
            if bu or bdn:
                d=1 if bu else -1
                b=B.get(DATES[i])
                if b and gate(b):
                    if room_min is not None:
                        rm = Z.room(ZONES, i, C[i], d)
                        if rm is not None and rm < room_min*a:
                            skipped += 1; continue
                    r0=aM*a
                    pos=(d,C[i],C[i]-d*r0,r0,i)
    return out, skipped

def stat(t):
    if len(t)<4: return None
    v=[x["R"] for x in t]
    w=[x for x in v if x>0]; gl=abs(sum(x for x in v if x<=0))
    pf=sum(w)/gl if gl>0 else 99.0
    eq=pk=dd=0.0
    for r in v: eq+=r; pk=max(pk,eq); dd=max(dd,pk-eq)
    return len(v), len(w)/len(v)*100, sum(v), sum(v)/len(v), pf, dd

def line(lbl,t,w=34):
    r=stat(t)
    if not r: return f"  {lbl:<{w}}{len(t):>6}   too few"
    n,wr,net,ex,pf,dd=r
    return f"  {lbl:<{w}}{n:>6}{wr:>7.1f}%{net:>+9.1f}R{ex:>+8.3f}R{pf:>7.2f}{dd:>8.1f}R"
HDR=lambda w=34: f"  {'':<{w}}{'trds':>6}{'win':>8}{'netR':>10}{'exp':>9}{'PF':>7}{'maxDD':>8}"

G30 = lambda b: b["pct_rvol"] > 0.30
G20 = lambda b: b["pct_rvol"] > 0.20

if __name__ == "__main__":
    print(f"NIFTY DAILY 2007-2026 — volume surge + supply/demand room")
    print(f"1R = 3x ATR, reward uncapped, 3bp cost.  {len(ZONES)} zones detected\n")
    print(HDR())
    base,_ = trades(NIFTY, G30)
    print(line("volume surge only (baseline)", base))
    for rm in (0.5, 1.0, 1.5, 2.0, 3.0):
        t,sk = trades(NIFTY, G30, room_min=rm)
        print(line(f"+ room ahead > {rm}x ATR   [skipped {sk}]", t))
    print()
    print("  same, on the looser volume gate (>20%) for a bigger sample")
    print(HDR())
    b2,_ = trades(NIFTY, G20)
    print(line("volume surge >20% only", b2))
    for rm in (0.5, 1.0, 1.5, 2.0, 3.0):
        t,sk = trades(NIFTY, G20, room_min=rm)
        print(line(f"+ room ahead > {rm}x ATR   [skipped {sk}]", t))
    print()
    print("  long-only (shorts fight the drift)")
    print(HDR())
    lo,_ = trades(NIFTY, G30, long_only=True)
    print(line("volume surge, long only", lo))
    for rm in (1.0, 2.0, 3.0):
        t,sk = trades(NIFTY, G30, room_min=rm, long_only=True)
        print(line(f"+ room > {rm}x ATR  [skipped {sk}]", t))
    print()
    # how often does the filter even bind?
    binds=0; tot=0
    for t in base:
        i=DATES.index(datetime.date.fromisoformat(t["entry"]))
        rm=Z.room(ZONES,i,t["ep"],t["dir"]); tot+=1
        if rm is not None: binds+=1
    print(f"  of {tot} baseline signals, {binds} had any live zone ahead at all")
