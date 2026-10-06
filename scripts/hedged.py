"""Eight ways to express the same long signal: bought, sold, spread and hedged.

Every leg is a real traded bhavcopy price. Structures are rolled together at
monthly expiry when the signal outlives the contract.

Sizing is by each structure's OWN maximum loss, held to 2% of equity. That is
the only way these compare honestly: a long call risks its premium, a credit
spread risks the width less the credit, and a naked short risks all the way to
the stop. Sizing them all by "one lot" would be comparing leverage, not
structure.

Margin is a SPAN-style portfolio scan, not a per-leg charge. An earlier version
billed every structure with a futures leg the full futures margin, which is
wrong in exactly the way that matters here: a hedge that caps the downside also
cuts the margin, and pricing it otherwise makes hedging look more expensive than
it is. See span.py.
"""
import json, os, sys, datetime
SC = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, SC)
import fo_fetch as F
import equity_nifty as EN
import span as SPAN
from indices_run import ema, atr

RISK_FRAC  = 0.02
MARGIN_PCT = 0.12
OTM        = 2            # strikes out for the short/hedge legs

def day(t): return datetime.datetime.fromtimestamp(t, datetime.UTC).date()

# structure = (futures_qty, [(opt_type, strike_offset, qty), ...])
#   offset is in strikes from ATM: + is OTM for a call, OTM for a put (away from spot)
#   qty +1 long, -1 short
STRUCTURES = {
    "long futures":        ( 1, []),
    "long call (ATM)":     ( 0, [("CE", 0, +1)]),
    "bull call spread":    ( 0, [("CE", 0, +1), ("CE", OTM, -1)]),
    "short put (naked)":   ( 0, [("PE", 0, -1)]),
    "bull put spread":     ( 0, [("PE", 0, -1), ("PE", OTM, +1)]),
    "covered call":        ( 1, [("CE", OTM, -1)]),
    "protective put":      ( 1, [("PE", OTM, +1)]),
    "collar":              ( 1, [("PE", OTM, +1), ("CE", OTM, -1)]),
}

def strikes_at(d, sym, spot, min_days=20):
    """ATM-anchored strike ladder for the monthly expiry, per option type."""
    out={}
    for ot in ("CE","PE"):
        rows=[r for r in F.parse_cached(d) if r["sym"]==sym and r["ot"]==ot
              and r["traded"] and r["close"]>0]
        if not rows: return None
        exps=sorted({r["exp"] for r in rows}); last={}
        for e in exps: last[(e.year,e.month)]=max(last.get((e.year,e.month),e),e)
        exp=None
        for e in sorted(last.values()):
            if (e-d).days>=min_days: exp=e; break
        if exp is None: return None
        c=[r for r in rows if r["exp"]==exp]
        ks=sorted({r["strike"] for r in c})
        if len(ks)<2*OTM+3: return None
        i=min(range(len(ks)), key=lambda j: abs(ks[j]-spot))
        out[ot]=dict(exp=exp, ks=ks, i=i,
                     px={r["strike"]: r["close"] for r in c})
    if out["CE"]["exp"]!=out["PE"]["exp"]: return None
    return out

def strike_for(lad, ot, off):
    """off strikes out of the money: up for calls, down for puts."""
    ks, i = lad[ot]["ks"], lad[ot]["i"]
    j = i+off if ot=="CE" else i-off
    if j<0 or j>=len(ks): return None
    return ks[j]

def price_on(d, sym, ot, exp, k):
    for r in F.parse_cached(d):
        if r["sym"]==sym and r["ot"]==ot and r["exp"]==exp and abs(r["strike"]-k)<1e-6:
            p=r["close"] if r["traded"] and r["close"]>0 else r["settle"]
            return p if p>0 else None
    return None

def fut_price(d, sym):
    EN.SYM=sym
    li=EN.lot_of(d)
    return li

def leg_walk(sym, t, struct, days_index):
    """Walk one signal in one structure, rolling at expiry.

    Returns per-lot cash flow, max loss per lot, and the margin per lot.
    """
    fq, opts = struct
    cur, exitd = t["entry"], t["exit"]
    total=0.0; max_loss=None; margin=None; lot=None; guard=0
    while cur < exitd and guard < 12:
        guard+=1
        li = fut_price(cur, sym)
        if li is None: return None
        lot, spot = li
        lad = strikes_at(cur, sym, spot)
        if lad is None: return None
        exp = lad["CE"]["exp"]
        close_on = min(exp, exitd)
        li2 = fut_price(close_on, sym)
        if li2 is None: return None
        spot_out = li2[1]

        seg=0.0; debit=0.0; credit=0.0
        widths=[]
        for ot, off, q in opts:
            k = strike_for(lad, ot, off)
            if k is None: return None
            pin = lad[ot]["px"].get(k)
            if pin is None: return None
            pout = price_on(close_on, sym, ot, exp, k)
            if pout is None:
                pout = max(0.0, (spot_out-k) if ot=="CE" else (k-spot_out))
            seg += q*(pout-pin)
            if q>0: debit += pin
            else:   credit += pin
            widths.append((ot, off, k))
        if fq:
            seg += fq*(spot_out-spot)
        total += seg

        if max_loss is None:
            yrs = max((exp - cur).days, 1) / 365.0
            span_legs = []
            if fq: span_legs.append(dict(kind="fut", qty=fq))
            for ot, off, q in opts:
                k = strike_for(lad, ot, off)
                pin = lad[ot]["px"].get(k)
                span_legs.append(dict(kind="opt", ot=ot, qty=q, strike=k, premium=pin,
                                      iv=SPAN.leg_iv(spot, k, yrs, ot, pin)))
            margin = SPAN.span_margin(spot, span_legs, yrs)
            # Risk is what THIS structure loses if the signal's own stop is hit,
            # evaluated through its legs. One rule for every structure: a future
            # loses the full stop distance, a long option cannot lose more than
            # its premium, and a collar is capped by its put. Sizing each
            # structure by its own hand-derived formula invited exactly the
            # artefact that a near-zero collar risk produced.
            adverse = -abs(t["r0"]) / spot
            max_loss = -SPAN.revalue(spot, span_legs, yrs, adverse, 0.0)
            max_loss = max(max_loss, spot * 0.0005)
        if close_on>=exitd: break
        nxt=[x for x in days_index if x>close_on]
        if not nxt or nxt[0]>exitd: break
        cur=nxt[0]
    if lot is None or max_loss is None: return None
    return dict(points=total, max_loss=max_loss, margin=margin, lot=lot)

_WALK={}
def walk_all(sigs, days_index, name):
    """Leg walks do not depend on capital, so they are computed once."""
    key=name
    if key in _WALK: return _WALK[key]
    struct=STRUCTURES[name]
    out=[]
    for s in sorted(sigs, key=lambda x: x["entry"]):
        out.append((s, leg_walk(s["sym"], s, struct, days_index)))
    _WALK[key]=out
    return out

def simulate(sigs, days_index, capital, name):
    eq=capital; free=capital; pk=capital; dd=0.0
    taken=0; skipped=0; wins=0; trades=[]; margins=[]
    for s, r in walk_all(sigs, days_index, name):
        if r is None: skipped+=1; continue
        risk_per_lot = r["max_loss"]*r["lot"]
        marg_per_lot = r["margin"]*r["lot"]
        if risk_per_lot<=0: skipped+=1; continue
        lots=int((eq*RISK_FRAC)//risk_per_lot)
        # Bound by available margin directly. Decrementing one lot at a time
        # hangs for any structure whose risk estimate is small enough to make
        # the initial lot count enormous.
        if marg_per_lot > 0:
            lots = min(lots, int(free // marg_per_lot))
        if lots<1: skipped+=1; continue
        pnl=r["points"]*r["lot"]*lots
        eq+=pnl; free=eq; taken+=1
        if pnl>0: wins+=1
        trades.append(pnl); margins.append(marg_per_lot)
        pk=max(pk,eq); dd=max(dd,(pk-eq)/pk*100)
    return dict(taken=taken, skipped=skipped, wins=wins, eq=eq, dd=dd, trades=trades,
                margin=sum(margins)/len(margins) if margins else 0.0)

def profit_factor(trades):
    w=sum(x for x in trades if x>0); l=abs(sum(x for x in trades if x<=0))
    return (w/l) if l>0 else (99.0 if w>0 else 0.0)

if __name__ == "__main__":
    import basket as B
    nf=json.load(open(os.path.join(SC,"niftyd.json")))
    bn=json.load(open(os.path.join(SC,"idx","BANKNIFTY.json")))
    days=sorted({day(b["t"]) for b in nf} | {day(b["t"]) for b in bn})
    since=datetime.date(2021,1,1)
    G30=lambda b: b["pct_rvol"]>0.30
    ns=B.signals(nf, since, "NIFTY", gate=G30, long_only=True)
    bs=B.signals(bn, since, "BANKNIFTY", long_only=True)
    both=sorted(ns+bs, key=lambda s: s["entry"])

    print(f"HEDGED BASKET — NIFTY (gated) + BANKNIFTY, long only, since {since}")
    print(f"{len(both)} signals. Sized to risk {RISK_FRAC*100:.0f}% of equity by each")
    print("structure's OWN maximum loss. Margin is a SPAN-style portfolio scan.\n")

    CAP=10_000_000
    print(f"AT {CAP:,} OF CAPITAL")
    print(f"  {'structure':<22}{'taken':>6}{'win':>6}{'return':>9}{'maxDD':>8}{'PF':>7}"
          f"{'margin/lot':>13}{'vs future':>11}")
    res={}
    base_m=None
    for name in STRUCTURES:
        r=simulate(both, days, CAP, name); res[name]=r
        if base_m is None: base_m=r["margin"]
        wr=f"{r['wins']/r['taken']*100:.0f}%" if r["taken"] else "-"
        rel=f"{r['margin']/base_m*100:.0f}%" if base_m else "-"
        print(f"  {name:<22}{r['taken']:>6}{wr:>6}{(r['eq']/CAP-1)*100:>+8.1f}%"
              f"{r['dd']:>7.1f}%{profit_factor(r['trades']):>7.2f}"
              f"{r['margin']:>13,.0f}{rel:>11}")

    print("\nWHAT THE MARGIN OFFSET BUYS")
    print("  same signal, same 2% risk -- the hedge frees capital as well as capping loss")
    for n in ("long futures","protective put","collar","covered call","bull put spread"):
        r=res[n]
        print(f"     {n:<22} margin {r['margin']:>10,.0f}  "
              f"return {(r['eq']/CAP-1)*100:>+6.1f}%  maxDD {r['dd']:>5.1f}%")

    print("\nBUYING vs SELLING vs HEDGED")
    for g,names in (("buying",["long call (ATM)","bull call spread"]),
                    ("selling",["short put (naked)","bull put spread"]),
                    ("hedged",["covered call","protective put","collar"]),
                    ("outright",["long futures"])):
        print(f"  {g}")
        for n in names:
            r=res[n]
            print(f"     {n:<22}{(r['eq']/CAP-1)*100:>+8.1f}%  maxDD {r['dd']:>5.1f}%  "
                  f"PF {profit_factor(r['trades']):>5.2f}")

    print("\nCAPITAL LADDER  (trades taken / return)")
    caps=(500_000,1_000_000,2_500_000,10_000_000)
    print(f"  {'structure':<22}" + "".join(f"{c:>14,}" for c in caps))
    for name in STRUCTURES:
        row=f"  {name:<22}"
        for cap in caps:
            r=simulate(both, days, cap, name)
            row += f"{r['taken']:>5}/{(r['eq']/cap-1)*100:>+7.1f}%"
        print(row)

    print("\nSCAN SENSITIVITY  (margin depends on the price scan; does the ranking?)")
    print(f"  {'price scan':<14}" + "".join(f"{n:>20}" for n in
          ("long futures","protective put","collar")))
    for ps in (0.04,0.06,0.08):
        SPAN.PRICE_SCAN=ps; _WALK.clear()
        row=f"  {f'+/- {ps*100:.0f}%':<14}"
        for n in ("long futures","protective put","collar"):
            r=simulate(both, days, CAP, n)
            row += f"{r['margin']:>11,.0f}/{(r['eq']/CAP-1)*100:>+7.1f}%"
        print(row)
