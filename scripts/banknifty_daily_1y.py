import json, os, sys, datetime
sys.path.insert(0,'/home/user/pinescript/scripts')
from indices_run import ema, atr, stat, line, HDR

bn=json.load(open('/home/user/pinescript/scripts/idx/BANKNIFTY.json'))
day=lambda t: datetime.datetime.fromtimestamp(t, datetime.UTC).date()
last=day(bn[-1]['t']); cut=last.replace(year=last.year-1)
print(f"BANKNIFTY daily — data to {last}, counting trades entered after {cut}")
print(f"  full history {len(bn)} bars; last year is {sum(1 for b in bn if day(b['t'])>cut)} bars")
print(f"  (indicators warmed on all {len(bn)} bars -- EMA150 alone needs 150)\n")

def run(bars, aM=3.0, cost_bp=3.0, don=50, long_only=False, since=None):
    H=[b["h"] for b in bars]; L=[b["l"] for b in bars]; C=[b["c"] for b in bars]
    f,s,A=ema(C,50),ema(C,150),atr(H,L,C,14)
    out=[];pos=None
    for i in range(152,len(bars)):
        a=A[i]
        if a is None or a<=0: continue
        cost=C[i]*cost_bp/10000.0
        h1=max(H[i-don:i]); l1=min(L[i-don:i])
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
            R=(((done-ep) if d>0 else (ep-done))-cost)/r0
            if since is None or day(bars[ei]["t"])>since:
                out.append(dict(R=R,dir=d,entry=str(day(bars[ei]['t'])),exit=str(day(bars[i]['t'])),
                                ep=round(ep,1),xp=round(done,1),bars=i-ei))
            pos=None
        if pos is None:
            bu=C[i]>h1 and up; bd=(C[i]<l1 and dn) and not long_only
            if bu or bd:
                d=1 if bu else -1; r0=aM*a
                pos=(d,C[i],C[i]-d*r0,r0,i)
    return out

def show(t,lbl):
    r=stat([x["R"] for x in t])
    if not r: return f"  {lbl:<22}{len(t):>6}   too few to score"
    n,wr,net,ex,pf,dd=r
    return f"  {lbl:<22}{n:>6}{wr:>7.1f}%{net:>+9.1f}R{ex:>+8.3f}R{pf:>7.2f}{dd:>8.1f}R"

t=run(bn, since=cut)
print(f"  {'':<22}{'trds':>6}{'win':>8}{'netR':>10}{'exp':>9}{'PF':>7}{'maxDD':>8}")
print(show(t,"both sides"))
print(show([x for x in t if x['dir']>0],"long only"))
print(show([x for x in t if x['dir']<0],"short only"))
print()
print(f"  {'dir':>6} {'entry':>12} {'exit':>12} {'bars':>5} {'entry':>9} {'exit':>9} {'R':>7}")
for x in t:
    print(f"  {'LONG' if x['dir']>0 else 'SHORT':>6} {x['entry']:>12} {x['exit']:>12} {x['bars']:>5} "
          f"{x['ep']:>9.0f} {x['xp']:>9.0f} {x['R']:>+7.2f}")
