"""BANKNIFTY with volume surge built from its own constituent banks.

BANKNIFTY's printed volume fails the quality check outright (corr with absolute
return is -0.01), so the gate cannot come from the index. It comes from the
twelve banks, exactly as the NIFTY gate came from the fifty.
"""
import json, os, datetime, sys
SC = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SC)
from indices_run import ema, atr, run, stat, line, HDR, vol_quality

BANKS = ("HDFCBANK ICICIBANK SBIN KOTAKBANK AXISBANK INDUSINDBK "
         "BANKBARODA PNB IDFCFIRSTB FEDERALBNK AUBANK CANBK").split()

def day(ts): return datetime.datetime.fromtimestamp(ts, datetime.UTC).date()

def bank_surge(dates, look=20):
    """{date: share of banks trading above 1.5x their own 20-day volume mean}"""
    hits = {d: [0, 0] for d in dates}
    for s in BANKS:
        p = os.path.join(SC, "n50", f"{s}.json")
        if not os.path.exists(p): continue
        bars = json.load(open(p)); V = [b["v"] for b in bars]
        for i, b in enumerate(bars):
            if i < look: continue
            d = day(b["t"])
            if d not in hits: continue
            w = V[i-look:i]; m = sum(w)/len(w) if w else 0
            if m > 0 and V[i] > 0:
                hits[d][1] += 1
                if V[i]/m > 1.5: hits[d][0] += 1
    return {d: (a/b if b >= 6 else None) for d, (a, b) in hits.items()}

if __name__ == "__main__":
    bn = json.load(open(os.path.join(SC, "idx", "BANKNIFTY.json")))
    dates = [day(b["t"]) for b in bn]
    S = bank_surge(dates)
    have = sum(1 for d in dates if S.get(d) is not None)
    print(f"BANKNIFTY — {len(bn)} bars, banks available on {have} of them")
    print(f"  BANKNIFTY's own volume: corr(vol,|ret|) = {vol_quality(bn):+.3f}  (void, hence the banks)\n")
    SV = [S.get(d) for d in dates]

    print("LONG ONLY, stop 3x ATR, 1R risk, reward uncapped, 3bp cost")
    print(HDR(24))
    print(line("no gate", run(bn, long_only=True), 24))
    for th in (0.10, 0.20, 0.25, 0.30, 0.40, 0.50):
        g = (lambda t: lambda x: x > t)(th)
        print(line(f"bank surge > {int(th*100)}%", run(bn, long_only=True, gate=g, RV=SV), 24))
    print()
    print("BOTH SIDES")
    print(HDR(24))
    print(line("no gate", run(bn), 24))
    for th in (0.20, 0.30, 0.40):
        g = (lambda t: lambda x: x > t)(th)
        print(line(f"bank surge > {int(th*100)}%", run(bn, gate=g, RV=SV), 24))
    print()
    print("BY PERIOD  (long only, bank surge > 30%)")
    print(HDR(24))
    g30 = lambda x: x > 0.30
    for lbl, y0, y1 in (("2007-2012",2007,2012),("2013-2018",2013,2018),("2019-2026",2019,2026)):
        idx=[i for i,d in enumerate(dates) if y0<=d.year<=y1]
        if len(idx) < 300: continue
        sub=bn[idx[0]:idx[-1]+1]; sv=SV[idx[0]:idx[-1]+1]
        print(line(f"{lbl} no gate", run(sub, long_only=True), 24))
        print(line(f"{lbl} + surge", run(sub, long_only=True, gate=g30, RV=sv), 24))
