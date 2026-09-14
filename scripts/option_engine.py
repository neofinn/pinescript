"""An option selection engine: which strike, and which expiry.

The leak found earlier was decay paid two or three times over a hold whose
median outlives a monthly contract. There are two ways to stop paying it. One
is to abandon the position at expiry, which is not the same trade. The other is
to select a contract that can carry the trade -- longer dated, so daily decay is
slower, and further in the money, so less of the premium is decay at all.

Risk is the premium, which is what a long option actually risks, so 1R = the
premium paid and the reward is left uncapped.
"""
import sys, os, json, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import option_index as O

SC = os.path.dirname(os.path.abspath(__file__))
STRIKES = [(-3,"ITM-3"),(-2,"ITM-2"),(-1,"ITM-1"),(0,"ATM"),(1,"OTM+1"),(2,"OTM+2")]
TENORS  = [(7,"near (>=7d)"),(30,"next (>=30d)"),(60,"far (>=60d)")]

def build(trades, tag):
    rows=[]
    for t in trades:
        e=datetime.date.fromisoformat(t["entry"]); x=datetime.date.fromisoformat(t["exit"])
        ot="CE" if t["dir"]>0 else "PE"
        r=dict(entry=t["entry"], dir=t["dir"], ot=ot, R=t["R"], pct=t["pct"], bars=t["bars"])
        for off,sl in STRIKES:
            for md,tl in TENORS:
                try: v,legs,_s = O.leg(e,x,ot,offset=off,min_days=md)
                except Exception: v=None
                r[f"{sl}|{tl}"] = None if v is None else v/100.0      # -> R multiples
                r[f"n|{sl}|{tl}"] = len(legs) if v is not None and not isinstance(legs,str) else 0
        rows.append(r)
    json.dump(rows, open(os.path.join(SC,f"engine_{tag}.json"),"w"), indent=1)
    return rows

def st(v,lbl,w=16):
    v=[x for x in v if x is not None]
    if len(v)<4: return f"{'--':>13}"
    w_=[x for x in v if x>0]; gl=abs(sum(x for x in v if x<=0))
    pf=sum(w_)/gl if gl>0 else 99.0
    return f"{sum(v)/len(v):>+6.2f}R/{pf:>5.2f}"

def full(v,lbl,w=30):
    v=[x for x in v if x is not None]
    if len(v)<4: return f"  {lbl:<{w}}{len(v):>6}   too few"
    w_=[x for x in v if x>0]; gl=abs(sum(x for x in v if x<=0))
    pf=sum(w_)/gl if gl>0 else 99.0
    eq=pk=dd=0.0
    for r in v: eq+=r; pk=max(pk,eq); dd=max(dd,pk-eq)
    med=sorted(v)[len(v)//2]
    return (f"  {lbl:<{w}}{len(v):>6}{len(w_)/len(v)*100:>7.1f}%{sum(v):>+9.1f}R"
            f"{sum(v)/len(v):>+8.2f}R{med:>+8.2f}R{pf:>7.2f}{dd:>8.1f}R")
H=lambda w=30: f"  {'':<{w}}{'trds':>6}{'win':>8}{'netR':>10}{'exp':>9}{'median':>8}{'PF':>7}{'maxDD':>8}"

if __name__ == "__main__":
    cache=os.path.join(SC,"engine_nifty.json")
    if os.path.exists(cache) and "--rebuild" not in sys.argv:
        rows=json.load(open(cache))
    else:
        rows=build(O.T,"nifty")
    print("OPTION SELECTION ENGINE — NIFTY, 1R = premium paid, reward uncapped")
    print(f"{len(rows)} signals, real bhavcopy, rolled to cover the hold\n")
    print("  cell = mean R / profit factor")
    print(f"  {'':<10}" + "".join(f"{tl:>16}" for _,tl in TENORS))
    for off,sl in STRIKES:
        print(f"  {sl:<10}" + "".join(st([r[f'{sl}|{tl}'] for r in rows],"") for _,tl in TENORS))
    print()
    print("  rolls needed (median) per cell:")
    print(f"  {'':<10}" + "".join(f"{tl:>16}" for _,tl in TENORS))
    for off,sl in STRIKES:
        line=f"  {sl:<10}"
        for _,tl in TENORS:
            n=[r[f'n|{sl}|{tl}'] for r in rows if r[f'n|{sl}|{tl}']]
            line+=f"{(sorted(n)[len(n)//2] if n else 0):>16}"
        print(line)
    print()
    print("FULL STATS ON THE BEST CELLS")
    print(H())
    for sl in ("ATM","ITM-1","ITM-2","ITM-3"):
        for tl in ("near (>=7d)","next (>=30d)","far (>=60d)"):
            print(full([r[f'{sl}|{tl}'] for r in rows], f"{sl}  {tl}"))
