"""A shared-capital basket across NIFTY and BANKNIFTY, futures and options.

Each signal is executed as futures when the account can post the margin and as
long options when it cannot, which is the choice a real account actually faces
rather than a preference. Positions from both indices can be open at once and
compete for the same capital, so the basket is a portfolio and not two
backtests added together.

Futures margin is the one input NSE's archive does not carry, so it is a
parameter and the sensitivity is shown.
"""
import json, os, sys, datetime
SC = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, SC)
import fo_fetch as F
import equity_nifty as EN
from indices_run import ema, atr

RISK_CAP   = 0.25     # most of the account one option position may use
MARGIN_PCT = 0.12     # SPAN + exposure on index futures, as a share of notional
RISK_FRAC  = 0.02     # target risk per futures trade, as a share of equity

def day(t): return datetime.datetime.fromtimestamp(t, datetime.UTC).date()

BREADTH = EN.BREADTH

def signals(bars, since, sym, gate=None, long_only=True, aM=3.0, don=50, cost_bp=3.0):
    H=[b["h"] for b in bars]; L=[b["l"] for b in bars]; C=[b["c"] for b in bars]
    f,s,A = ema(C,50), ema(C,150), atr(H,L,C,14)
    out=[]; pos=None
    for i in range(152,len(bars)):
        a=A[i]
        if a is None or a<=0: continue
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
            if day(bars[ei]["t"])>=since:
                out.append(dict(sym=sym, dir=d, entry=day(bars[ei]["t"]), exit=day(bars[i]["t"]),
                                ep=ep, xp=done, r0=r0,
                                R=(((done-ep) if d>0 else (ep-done))-C[i]*cost_bp/10000.0)/r0))
            pos=None
        if pos is None:
            bu=C[i]>h1 and up; bd=(C[i]<l1 and dn) and not long_only
            if bu or bd:
                if gate is not None:
                    b=BREADTH.get(day(bars[i]["t"]))
                    if not b or not gate(b): continue
                d=1 if bu else -1; r0=aM*a
                pos=(d,C[i],C[i]-d*r0,r0,i)
    return out

def lot_spot(sym, d):
    EN.SYM = sym
    return EN.lot_of(d)

def option_legs(sym, t, days_index):
    EN.SYM = sym
    return EN.trade_option(t, days_index)

def simulate(sigs, days_index, capital, margin_pct=MARGIN_PCT, allow_futures=True,
             matched_risk=True):
    """Chronological, shared capital, positions may overlap.

    matched_risk sizes options to the SAME risk budget as futures. A long
    option's maximum loss is its premium, so risking 2% of equity means an
    outlay of 2% of equity -- not the 25% ceiling, which is what a small
    account is forced into and is a different policy, not a bigger version of
    the same one. Comparing a 2%-risk futures book against a 25%-outlay option
    book measures the leverage, not the instrument.
    """
    events=[]
    for s in sigs:
        events.append((s["entry"], "open", s))
        events.append((s["exit"],  "close", s))
    events.sort(key=lambda e: (e[0], 0 if e[1]=="close" else 1))
    eq=capital; free=capital; open_pos={}; done=[]; pk=capital; dd=0.0
    n_fut=n_opt=n_skip=0
    for d, kind, s in events:
        key=id(s)
        if kind=="open":
            li=lot_spot(s["sym"], d)
            if li is None: n_skip+=1; continue
            lot, spot = li
            notional=spot*lot
            margin=notional*margin_pct
            # how many futures lots does a 2%-of-equity risk budget allow?
            risk_per_lot=s["r0"]*lot
            want=int((eq*RISK_FRAC)//risk_per_lot) if risk_per_lot>0 else 0
            if allow_futures and want>=1 and margin*want<=free:
                open_pos[key]=dict(kind="fut", lots=want, lot=lot, margin=margin*want, s=s)
                free-=margin*want; n_fut+=1
                continue
            r=option_legs(s["sym"], s, days_index)
            if r is None: n_skip+=1; continue
            paid, got, olot, first = r
            per=first*olot
            budget = eq*RISK_FRAC if matched_risk else min(eq*RISK_CAP, free)
            lots=int(min(budget, free)//per) if per>0 else 0
            if lots<1: n_skip+=1; continue
            open_pos[key]=dict(kind="opt", lots=lots, lot=olot, paid=paid, got=got,
                               outlay=per*lots, s=s)
            free-=per*lots; n_opt+=1
        else:
            p=open_pos.pop(key, None)
            if p is None: continue
            if p["kind"]=="fut":
                pnl=(s["xp"]-s["ep"])*p["lot"]*p["lots"]*s["dir"]
                free+=p["margin"]
            else:
                pnl=(p["got"]-p["paid"])*p["lot"]*p["lots"]
                free+=p["outlay"]
            eq+=pnl; free+=pnl
            done.append(dict(sym=s["sym"], kind=p["kind"], pnl=pnl, eq=eq, R=s["R"]))
            pk=max(pk,eq); dd=max(dd,(pk-eq)/pk*100)
    return dict(trades=done, eq=eq, dd=dd, n_fut=n_fut, n_opt=n_opt, n_skip=n_skip)

if __name__ == "__main__":
    nf=json.load(open(os.path.join(SC,"niftyd.json")))
    bn=json.load(open(os.path.join(SC,"idx","BANKNIFTY.json")))
    days=sorted({day(b["t"]) for b in nf} | {day(b["t"]) for b in bn})
    since=datetime.date(2021,1,1)
    G30=lambda b: b["pct_rvol"]>0.30

    ns=signals(nf, since, "NIFTY", gate=G30, long_only=True)
    bs=signals(bn, since, "BANKNIFTY", long_only=True)
    both=sorted(ns+bs, key=lambda s: s["entry"])
    ov=sum(1 for a in ns for b in bs if a["entry"]<=b["exit"] and b["entry"]<=a["exit"])
    print(f"BASKET — NIFTY (volume surge gated) + BANKNIFTY (bare), long only, since {since}")
    print(f"  NIFTY {len(ns)} signals, BANKNIFTY {len(bs)} signals, {len(both)} total, "
          f"{ov} overlapping pairs")
    print(f"  every trade risks {RISK_FRAC*100:.0f}% of equity, whether it is futures or options\n")

    def row(lbl, r, cap, w=22):
        t=r["trades"]; w_=sum(1 for x in t if x["pnl"]>0)
        wr=f"{w_/len(t)*100:.0f}%" if t else "-"
        return (f"  {lbl:>{w}}{r['n_fut']:>5}{r['n_opt']:>5}{r['n_skip']:>6}{wr:>7}"
                f"{r['eq']:>14,.0f}{(r['eq']/cap-1)*100:>+8.1f}%{r['dd']:>7.1f}%")
    H=lambda w=22: (f"  {'':>{w}}{'fut':>5}{'opt':>5}{'skip':>6}{'win':>7}"
                    f"{'final':>14}{'return':>9}{'maxDD':>8}")

    print("MATCHED RISK  (2% of equity per trade, futures or options alike)")
    print(H())
    for cap in (100_000, 500_000, 1_000_000, 2_500_000, 5_000_000, 10_000_000):
        print(row(f"{cap:,}", simulate(both, days, cap), cap))
    print()
    print("  options only, same 2% risk -- what the premium costs you")
    print(H())
    for cap in (2_500_000, 5_000_000, 10_000_000):
        print(row(f"{cap:,}", simulate(both, days, cap, allow_futures=False), cap))
    print()
    print("THE 25% PREMIUM CEILING  (what a small account is forced into)")
    print(H())
    for cap in (100_000, 500_000, 2_500_000):
        print(row(f"{cap:,}", simulate(both, days, cap, matched_risk=False), cap))
    print()
    print("EACH LEG ALONE at 10,000,000, matched risk")
    print(H())
    for lbl, ss in (("NIFTY only", ns), ("BANKNIFTY only", bs), ("basket", both)):
        print(row(lbl, simulate(ss, days, 10_000_000), 10_000_000))
    print()
    print("MARGIN SENSITIVITY at 10,000,000")
    print(H())
    for m in (0.10, 0.12, 0.15, 0.20):
        print(row(f"{m*100:.0f}% of notional",
                  simulate(both, days, 10_000_000, margin_pct=m), 10_000_000))
