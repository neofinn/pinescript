"""BANKNIFTY, both directions, trades entered in the last twelve months.

The daily system fires two or three times a year here, so a one-year window
cannot score it -- that is reported rather than dressed up. Hourly bars give a
sample that can be, run two ways: carrying positions overnight, and flat at
every bell.
"""
import json, os, sys, datetime
SC = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, SC)
from indices_run import ema, atr, stat
import intraday_orb as I

IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
day = lambda t: datetime.datetime.fromtimestamp(t, IST).date()

def swing(bars, aM=3.0, cost_bp=3.0, don=50, since=None, long_only=False,
          short_only=False, flat_at_bell=False):
    """One position at a time. flat_at_bell forces an exit on the session's
    last bar, which is the difference between a swing and an intraday book."""
    H=[b["h"] for b in bars]; L=[b["l"] for b in bars]; C=[b["c"] for b in bars]
    f,s,A = ema(C,50), ema(C,150), atr(H,L,C,14)
    sess=[day(b["t"]) for b in bars]
    lastbar=[i==len(bars)-1 or sess[i+1]!=sess[i] for i in range(len(bars))]
    out=[]; pos=None
    for i in range(152,len(bars)):
        a=A[i]
        if a is None or a<=0: continue
        cost=C[i]*cost_bp/10000.0
        h1=max(H[i-don:i]); l1=min(L[i-don:i])
        up=f[i]>s[i]; dn=s[i]>f[i]
        xUp=f[i-1]<=s[i-1] and f[i]>s[i]; xDn=f[i-1]>=s[i-1] and f[i]<s[i]
        if pos:
            d,ep,stp,r0,ei=pos; done=None; why=None
            if d>0:
                stp=max(stp, C[i]-aM*a)
                if L[i]<=stp: done, why = stp, "stop"
                elif xDn and dn: done, why = C[i], "cross"
            else:
                stp=min(stp, C[i]+aM*a)
                if H[i]>=stp: done, why = stp, "stop"
                elif xUp and up: done, why = C[i], "cross"
            if done is None and flat_at_bell and lastbar[i]: done, why = C[i], "bell"
            if done is None: pos=(d,ep,stp,r0,ei); continue
            R=(((done-ep) if d>0 else (ep-done))-cost)/r0
            if since is None or sess[ei] > since:
                out.append(dict(R=R, dir=d, entry=str(sess[ei]), exit=str(sess[i]),
                                bars=i-ei, why=why))
            pos=None
        if pos is None:
            if flat_at_bell and lastbar[i]: continue      # no entry on the closing bar
            bu = C[i]>h1 and up and not short_only
            bd = C[i]<l1 and dn and not long_only
            if bu or bd:
                d=1 if bu else -1; r0=aM*a
                pos=(d,C[i],C[i]-d*r0,r0,i)
    return out

def show(t,lbl,w=26):
    r=stat([x["R"] for x in t])
    if not r: return f"  {lbl:<{w}}{len(t):>6}   too few to score"
    n,wr,net,ex,pf,dd=r
    return f"  {lbl:<{w}}{n:>6}{wr:>7.1f}%{net:>+9.1f}R{ex:>+8.3f}R{pf:>7.2f}{dd:>8.1f}R"
HDR=lambda w=26: f"  {'':<{w}}{'trds':>6}{'win':>8}{'netR':>10}{'exp':>9}{'PF':>7}{'maxDD':>8}"

if __name__ == "__main__":
    hb=json.load(open(os.path.join(SC,"intra","BANKNIFTY.json")))
    last=day(hb[-1]["t"]); cut=last.replace(year=last.year-1)
    n1y=sum(1 for b in hb if day(b["t"])>cut)
    print(f"BANKNIFTY HOURLY — {len(hb)} bars total, {n1y} in the last year")
    print(f"trades entered after {cut}; indicators warmed on everything before it")
    print("1R = 3x ATR, reward uncapped, 3bp cost\n")

    print("CARRYING OVERNIGHT (the swing system, on hourly bars)")
    print(HDR())
    t=swing(hb, since=cut)
    print(show(t,"both sides"))
    print(show([x for x in t if x["dir"]>0],"long only"))
    print(show([x for x in t if x["dir"]<0],"short only"))
    print()
    print("FLAT AT EVERY BELL (no overnight risk)")
    print(HDR())
    ti=swing(hb, since=cut, flat_at_bell=True)
    print(show(ti,"both sides"))
    print(show([x for x in ti if x["dir"]>0],"long only"))
    print(show([x for x in ti if x["dir"]<0],"short only"))
    print()
    print("BREAKOUT LOOKBACK  (both sides, carrying overnight)")
    print(HDR())
    for don in (20,30,50,80):
        print(show(swing(hb, don=don, since=cut), f"Donchian {don} bars"))
    print()
    print("COST SENSITIVITY  (both sides, Donchian 50, overnight)")
    print(HDR())
    for c in (0,3,5,10,20):
        print(show(swing(hb, since=cut, cost_bp=c), f"cost {c}bp round turn"))
    print()
    print("THE LAST YEAR vs THE YEAR BEFORE  (both sides, overnight)")
    print(HDR())
    prev=cut.replace(year=cut.year-1)
    allt=swing(hb, since=prev)
    print(show([x for x in allt if x["entry"]<=str(cut)], f"{prev} to {cut}"))
    print(show([x for x in allt if x["entry"]> str(cut)], f"{cut} to {last}"))
