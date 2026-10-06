"""What one lakh can actually trade on BANKNIFTY, in futures and in options.

Contract specs are read from NSE's own bhavcopy rather than assumed -- lot size
has changed repeatedly and a stale constant would quietly invalidate every
rupee figure below.

Margin is the one number bhavcopy does not carry. SPAN plus exposure on index
futures has run in the low teens as a percentage of notional, so it is shown
across a range instead of pinned to a single guess.
"""
import json, os, sys, datetime
SC = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, SC)
import fo_fetch as F
from indices_run import ema, atr, stat
from banknifty_1y import swing, day, HDR, show

CAPITAL = 100_000

def specs(d):
    """(spot, lot, futures close, ATM call premium) from the day's bhavcopy."""
    t = F.raw(d)
    if not t: return None
    lines = t.splitlines(); hdr = [c.strip() for c in lines[0].split(",")]
    if "TradDt" not in hdr: return None
    ix = {c: i for i, c in enumerate(hdr)}
    fut, opt = [], []
    for L in lines[1:]:
        f = L.split(",")
        if len(f) < len(hdr) - 4: continue
        if f[ix["TckrSymb"]] != "BANKNIFTY": continue
        tp = f[ix["FinInstrmTp"]]
        if tp == "IDF": fut.append(f)
        elif tp == "IDO": opt.append(f)
    if not fut: return None
    fut.sort(key=lambda f: f[ix["XpryDt"]])
    spot = float(fut[0][ix["UndrlygPric"]]); lot = int(fut[0][ix["NewBrdLotQty"]])
    fpx = float(fut[0][ix["ClsPric"]])
    exps = sorted({f[ix["XpryDt"]] for f in opt})
    prem = None
    for e in exps:
        ce = [f for f in opt if f[ix["OptnTp"]] == "CE" and f[ix["XpryDt"]] == e
              and float(f[ix["TtlTradgVol"]] or 0) > 0 and float(f[ix["ClsPric"]] or 0) > 0]
        if not ce: continue
        days = (datetime.date.fromisoformat(e) - d).days
        if days < 7: continue
        prem = min(ce, key=lambda f: abs(float(f[ix["StrkPric"]]) - spot))
        prem = float(prem[ix["ClsPric"]]); break
    return spot, lot, fpx, prem

if __name__ == "__main__":
    d = datetime.date(2026, 9, 11)
    sp, lot, fpx, prem = specs(d)
    notional = sp * lot
    print(f"BANKNIFTY CONTRACT, as NSE published it on {d}")
    print(f"  spot                {sp:>14,.0f}")
    print(f"  lot size            {lot:>14}        (from bhavcopy, not assumed)")
    print(f"  one futures lot     {notional:>14,.0f}  INR notional")
    print(f"  one ATM call lot    {prem*lot:>14,.0f}  INR premium  ({prem/sp*100:.2f}% of spot)")
    print()
    print(f"AGAINST {CAPITAL:,} OF CAPITAL")
    print(f"  {'margin rate':<16}{'margin / lot':>16}{'lots affordable':>18}")
    for r in (0.10, 0.12, 0.15, 0.20):
        m = notional * r
        print(f"  {r*100:>5.0f}% of notional{m:>16,.0f}{CAPITAL/m:>18.2f}")
    print(f"\n  -> one lakh is {CAPITAL/notional*100:.1f}% of one lot's notional. No margin rate")
    print("     in that range admits a single BANKNIFTY futures lot.")
    print()
    print(f"  buying the ATM call instead costs {prem*lot:,.0f}, which one lakh does cover:")
    print(f"     {int(CAPITAL//(prem*lot))} lot(s), using {int(CAPITAL//(prem*lot))*prem*lot/CAPITAL*100:.0f}% of capital,")
    print(f"     and the premium is the whole risk -- {prem*lot/CAPITAL*100:.1f}% of the account per lot.")
    print()

    # what the system's own stop implies, in rupees
    hb = json.load(open(os.path.join(SC, "intra", "BANKNIFTY.json")))
    C = [b["c"] for b in hb]; H = [b["h"] for b in hb]; L = [b["l"] for b in hb]
    A = atr(H, L, C, 14)
    a = A[-1]
    print("THE SYSTEM'S OWN RISK UNIT, PRICED")
    print(f"  hourly ATR now      {a:>14,.0f}  points")
    print(f"  1R = 3x ATR         {3*a:>14,.0f}  points")
    print(f"  1R in futures       {3*a*lot:>14,.0f}  INR per lot   "
          f"= {3*a*lot/CAPITAL*100:.0f}% of a one lakh account")
    daily = json.load(open(os.path.join(SC, "idx", "BANKNIFTY.json")))
    dA = atr([b["h"] for b in daily], [b["l"] for b in daily], [b["c"] for b in daily], 14)
    print(f"  daily ATR now       {dA[-1]:>14,.0f}  points")
    print(f"  1R daily            {3*dA[-1]*lot:>14,.0f}  INR per lot   "
          f"= {3*dA[-1]*lot/CAPITAL*100:.0f}% of a one lakh account")
    print()
    print("  capital needed to risk a sane 2% per trade on one lot:")
    print(f"     hourly system     {3*a*lot/0.02:>14,.0f}  INR")
    print(f"     daily  system     {3*dA[-1]*lot/0.02:>14,.0f}  INR")
