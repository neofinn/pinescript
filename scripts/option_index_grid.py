"""Index-only: ATM / ATM+1 / ATM+2, with IV and open interest as factors.

Calls are bought on long signals and puts on short signals, so both sides of
the book are priced from the same 62% signal rather than only the long half.

IV is recovered from the ATM premium by inversion -- NSE's archive publishes
a price and an open interest, never a greek -- using the project's own
Black-Scholes module.
"""
import sys, os, json, datetime
sys.path.insert(0, "/home/user/index-option-brain")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import option_index as O
from index_option_brain.analytics.pricing import implied_volatility
from index_option_brain.contracts.enums import OptionType

SC = os.path.dirname(os.path.abspath(__file__))
DIVY = 0.012                      # NIFTY trailing dividend yield, roughly

def entry_context(t):
    """IV, OI and PCR as they stood on the signal bar."""
    e = datetime.date.fromisoformat(t["entry"])
    exp = O.pick_exp(e, "NIFTY")
    spot = O.SPOT.get(e)
    if exp is None or spot is None: return None
    ot = "CE" if t["dir"] > 0 else "PE"
    k = O.atm(e, "NIFTY", ot, exp, spot, 0)
    if k is None: return None
    p, _ = O.px(e, "NIFTY", ot, exp, k)
    if not p: return None
    yrs = max((exp - e).days, 1) / 365.0
    iv = implied_volatility(market_price=p, spot=spot, strike=k, years=yrs,
                            option_type=OptionType(ot), dividend_yield=DIVY)
    ce, pe = O.chain_oi(e, "NIFTY", exp)
    return dict(iv=None if iv is None else iv * 100, pcr=(pe / ce) if ce > 0 else None,
                oi=O.oi_at(e, "NIFTY", ot, exp, k), spot=spot, days=(exp - e).days)

def build():
    T = O.T
    rows = []
    for t in T:
        e = datetime.date.fromisoformat(t["entry"]); x = datetime.date.fromisoformat(t["exit"])
        ot = "CE" if t["dir"] > 0 else "PE"
        ctx = entry_context(t)
        if ctx is None: continue
        r = dict(entry=t["entry"], dir=t["dir"], ot=ot, R=t["R"], pct=t["pct"], **ctx)
        for off in (0, 1, 2):
            try: v, legs, su = O.leg(e, x, ot, offset=off)
            except Exception: v = None
            r[f"off{off}"] = v
            r[f"rolls{off}"] = len(legs) if v is not None and not isinstance(legs, str) else 0
        rows.append(r)
    return rows

def st(v, lbl, w=30):
    v = [x for x in v if x is not None]
    if len(v) < 4: return f"  {lbl:<{w}}{len(v):>6}   too few"
    win = [x for x in v if x > 0]; gl = abs(sum(x for x in v if x <= 0))
    pf = sum(win) / gl if gl > 0 else 99.0
    med = sorted(v)[len(v) // 2]
    return (f"  {lbl:<{w}}{len(v):>6}{len(win)/len(v)*100:>7.1f}%"
            f"{sum(v)/len(v):>+9.1f}%{med:>+9.1f}%{pf:>7.2f}")
H = lambda w=30: f"  {'':<{w}}{'trds':>6}{'win':>8}{'mean':>10}{'median':>10}{'PF':>7}"

if __name__ == "__main__":
    cache = os.path.join(SC, "optgrid.json")
    if os.path.exists(cache) and "--rebuild" not in sys.argv:
        rows = json.load(open(cache))
    else:
        rows = build(); json.dump(rows, open(cache, "w"), indent=1)
    print(f"NIFTY ONLY — {len(rows)} signals priced from real bhavcopy\n")

    print("STRIKE LADDER   (calls on long signals, puts on short signals)")
    print(H())
    for off in (0, 1, 2):
        print(st([r[f"off{off}"] for r in rows], f"ATM+{off}"))
    print()
    for side, lbl in (("CE", "calls (long signals)"), ("PE", "puts (short signals)")):
        for off in (0, 1, 2):
            print(st([r[f"off{off}"] for r in rows if r["ot"] == side], f"{lbl}  ATM+{off}"))
    print()

    ivs = sorted(r["iv"] for r in rows if r["iv"] is not None)
    lo, hi = ivs[len(ivs)//3], ivs[2*len(ivs)//3]
    print(f"IMPLIED VOL AT ENTRY   terciles at {lo:.1f}% and {hi:.1f}%  "
          f"(range {ivs[0]:.1f}-{ivs[-1]:.1f}%)")
    print(H())
    for off in (0, 1, 2):
        for name, sel in (("IV low", lambda r: r["iv"] is not None and r["iv"] <= lo),
                          ("IV mid", lambda r: r["iv"] is not None and lo < r["iv"] <= hi),
                          ("IV high", lambda r: r["iv"] is not None and r["iv"] > hi)):
            print(st([r[f"off{off}"] for r in rows if sel(r)], f"ATM+{off}  {name}"))
        print()

    pcrs = sorted(r["pcr"] for r in rows if r["pcr"] is not None)
    pmed = pcrs[len(pcrs)//2]
    print(f"OPEN INTEREST   chain PCR median {pmed:.2f}   "
          f"(PCR = put OI / call OI across the expiry)")
    print(H())
    for off in (0, 1, 2):
        print(st([r[f"off{off}"] for r in rows if r["pcr"] is not None and r["pcr"] > pmed],
                 f"ATM+{off}  PCR above median"))
        print(st([r[f"off{off}"] for r in rows if r["pcr"] is not None and r["pcr"] <= pmed],
                 f"ATM+{off}  PCR below median"))
    print()
    ois = sorted(r["oi"] for r in rows if r["oi"])
    omed = ois[len(ois)//2]
    print(f"  strike-level OI, median {omed:,.0f}")
    for off in (0, 1, 2):
        print(st([r[f"off{off}"] for r in rows if r["oi"] and r["oi"] > omed],
                 f"ATM+{off}  strike OI above median"))
