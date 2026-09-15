"""Index against underlying, using the selection engine's own best contract.

Both sides risk the premium and cap nothing, so the numbers are R multiples on
the same footing as the index signal they came from.
"""
import sys, os, json, datetime
SC=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,SC)
import option_index as O
import option_underlying as U
from option_engine import full, H

def st_rows(v): return [x for x in v if x is not None]

if __name__=="__main__":
    idx=json.load(open(os.path.join(SC,"engine_nifty.json")))
    cache=os.path.join(SC,"engine_stock.json")
    if os.path.exists(cache) and "--rebuild" not in sys.argv:
        stk=json.load(open(cache))
    else:
        sig=[datetime.date.fromisoformat(t["entry"]) for t in O.T]
        hits=U.stock_rvol_on(sig)
        stk=[]
        for t in O.T:
            e=datetime.date.fromisoformat(t["entry"]); x=datetime.date.fromisoformat(t["exit"])
            ot="CE" if t["dir"]>0 else "PE"
            row=dict(entry=t["entry"],dir=t["dir"],R=t["R"])
            for off,md,tag in ((0,7,"ATM|near"),(-3,60,"ITM-3|far"),(-1,60,"ITM-1|far")):
                rr=[]
                for sym,_ in hits.get(e,[]):
                    try: r,_l,_s = U.leg_stock(sym,e,x,ot,offset=off,min_days=md)
                    except Exception: r=None
                    if r is not None: rr.append(r/100.0)
                row[tag]= (sum(rr)/len(rr)) if rr else None
                row["n|"+tag]=len(rr)
            stk.append(row)
        json.dump(stk,open(cache,"w"),indent=1)

    print("INDEX vs UNDERLYING — same signal, same contract rule, 1R = premium\n")
    print(H(34))
    for tag,lbl in (("ATM|near","ATM near  (the original test)"),
                    ("ITM-3|far","ITM-3 far (engine's pick)"),
                    ("ITM-1|far","ITM-1 far")):
        k=tag.replace("|"," ").replace("near","near (>=7d)").replace("far","far (>=60d)")
        ik={"ATM|near":"ATM|near (>=7d)","ITM-3|far":"ITM-3|far (>=60d)","ITM-1|far":"ITM-1|far (>=60d)"}[tag]
        print(full([r[ik] for r in idx], f"INDEX      {lbl}",34))
        print(full([r[tag] for r in stk], f"UNDERLYING {lbl}",34))
        print()
    print("LONG ONLY  (shorts fight the drift on both)")
    print(H(34))
    print(full([r["ITM-3|far (>=60d)"] for r in idx if r["dir"]>0], "INDEX      ITM-3 far, long only",34))
    print(full([r["ITM-3|far"] for r in stk if r["dir"]>0], "UNDERLYING ITM-3 far, long only",34))
    print()
    print("BID-ASK  (spread as % of premium)")
    print(H(34))
    def sp(v,s): return [None if x is None else ((1-s/2)*(1+x)-(1+s/2))/(1+s/2) for x in v]
    for s_ in (0.0,0.05,0.10,0.20):
        print(full(sp([r["ITM-3|far (>=60d)"] for r in idx],s_), f"INDEX      ITM-3 far  spread {s_*100:.0f}%",34))
    print()
    for s_ in (0.0,0.05,0.10,0.20):
        print(full(sp([r["ITM-3|far"] for r in stk],s_), f"UNDERLYING ITM-3 far  spread {s_*100:.0f}%",34))
