"""Evaluate the NIFTY dual strategy against live data, mirroring the Pine logic.

The strategy decides on the daily close, so while NSE is open anything computed
here is provisional: today's high, low, close and every constituent's volume are
all still moving. The confirmed state as of the last completed session is
reported alongside it, because that is the one that was actually actionable.
"""
import urllib.request, json, os, sys, time, datetime

SC = os.path.dirname(os.path.abspath(__file__))
H = {"User-Agent": "Mozilla/5.0"}
IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))

# same twenty the Pine script reads, in the same order
NAMES = ("HDFCBANK ICICIBANK RELIANCE INFY BHARTIARTL ITC TCS LT AXISBANK "
         "KOTAKBANK SBIN HINDUNILVR BAJFINANCE MARUTI SUNPHARMA NTPC HCLTECH "
         "TITAN ULTRACEMCO TATAMOTORS").split()

VOL_LEN, VOL_MULT = 20, 1.5
PCT_LEN, GATE_PCT = 504, 70
DON, PB, EF, ES, ATR_LEN, STOP_ATR = 50, 20, 50, 150, 14, 3.0

def fetch(sym, rng="2y", iv="1d", tries=4):
    u = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range={rng}&interval={iv}"
    for a in range(tries):
        try:
            d = json.load(urllib.request.urlopen(urllib.request.Request(u, headers=H), timeout=45))
            r = d["chart"]["result"][0]; ts = r["timestamp"]; q = r["indicators"]["quote"][0]
            bars = [{"t": t, "o": q["open"][i], "h": q["high"][i], "l": q["low"][i],
                     "c": q["close"][i], "v": q["volume"][i] or 0}
                    for i, t in enumerate(ts) if q["close"][i] is not None]
            return bars, r.get("meta", {})
        except Exception as e:
            if a == tries - 1: return None, None
            time.sleep(2 ** a)

def ema(v, n):
    out=[None]*len(v); k=2/(n+1); e=None
    for i,x in enumerate(v):
        e = x if e is None else x*k+e*(1-k); out[i]=e
    return out

def atr(H_, L_, C_, n=14):
    tr=[H_[0]-L_[0]]+[max(H_[i]-L_[i],abs(H_[i]-C_[i-1]),abs(L_[i]-C_[i-1])) for i in range(1,len(H_))]
    out=[None]*len(H_); s=None
    for i,t in enumerate(tr):
        s=t if s is None else (s*(n-1)+t)/n
        out[i]=s if i>=n-1 else None
    return out

def pctile(arr, p):
    """percentile_nearest_rank, the same rule Pine uses."""
    a = sorted(x for x in arr if x is not None)
    if not a: return None
    k = max(1, int(round(p/100.0 * len(a))))
    return a[min(k, len(a)) - 1]

def day(t): return datetime.datetime.fromtimestamp(t, IST).date()

if __name__ == "__main__":
    print("Fetching NIFTY and 20 constituents ...", flush=True)
    nf, meta = fetch("%5ENSEI")
    if nf is None: sys.exit("could not fetch NIFTY")
    last_day = day(nf[-1]["t"])
    now_ist = datetime.datetime.now(IST)
    mkt_open = (now_ist.weekday() < 5 and
                datetime.time(9,15) <= now_ist.time() <= datetime.time(15,30))
    print(f"  NIFTY bars {len(nf)}, latest bar dated {last_day}")
    print(f"  now {now_ist:%Y-%m-%d %H:%M} IST — market {'OPEN' if mkt_open else 'closed'}")
    # chartPreviousClose is the close before the REQUESTED RANGE, not yesterday's.
    # Reading it as a previous close makes a two-year move look like an overnight gap.
    if meta: print(f"  last price {meta.get('regularMarketPrice')}")

    # constituent signed surge, exactly as the Pine f_dir() computes it
    up_hist, dn_hist = {}, {}
    got = 0
    for nm in NAMES:
        b, _ = fetch(nm + ".NS")
        if not b: print(f"  !! {nm} unavailable — excluded"); continue
        got += 1
        V=[x["v"] for x in b]; C=[x["c"] for x in b]
        for i in range(VOL_LEN+1, len(b)):
            d = day(b[i]["t"])
            w = V[i-VOL_LEN:i]; m = sum(w)/len(w) if w else 0
            if m <= 0 or V[i] <= 0: continue
            up_hist.setdefault(d, [0,0]); dn_hist.setdefault(d, [0,0])
            up_hist[d][1] += 1; dn_hist[d][1] += 1
            if V[i]/m > VOL_MULT:
                if C[i] > C[i-1]: up_hist[d][0] += 1
                elif C[i] < C[i-1]: dn_hist[d][0] += 1
        time.sleep(0.15)
    print(f"  constituents fetched: {got}/20\n")

    dates = [day(x["t"]) for x in nf]
    upS = [(up_hist[d][0]/up_hist[d][1] if d in up_hist and up_hist[d][1] >= 10 else None)
           for d in dates]
    dnS = [(dn_hist[d][0]/dn_hist[d][1] if d in dn_hist and dn_hist[d][1] >= 10 else None)
           for d in dates]

    Hs=[x["h"] for x in nf]; Ls=[x["l"] for x in nf]; Cs=[x["c"] for x in nf]
    f_, s_, A = ema(Cs,EF), ema(Cs,ES), atr(Hs,Ls,Cs,ATR_LEN)
    e20 = ema(Cs,PB)

    def state(i, label):
        upv, dnv = upS[i], dnS[i]
        uThr = pctile([x for x in upS[max(0,i-PCT_LEN):i] if x is not None], GATE_PCT)
        dThr = pctile([x for x in dnS[max(0,i-PCT_LEN):i] if x is not None], GATE_PCT)
        hiN = max(Hs[i-DON:i]); loN = min(Ls[i-DON:i])
        up = f_[i] > s_[i]; dn = s_[i] > f_[i]
        gateL = upv is not None and uThr is not None and upv > uThr
        gateS = dnv is not None and dThr is not None and dnv > dThr
        boLong  = up and Cs[i] > hiN
        pbLong  = up and Cs[i-1] <= e20[i-1] and Cs[i] > e20[i]
        pbShort = dn and Cs[i-1] >= e20[i-1] and Cs[i] < e20[i]
        print(f"=== {label}  ({dates[i]})")
        print(f"  close {Cs[i]:>10,.2f}   ATR14 {A[i]:>8,.1f}   1R = 3xATR = {3*A[i]:>8,.1f} pts")
        print(f"  trend           EMA50 {f_[i]:>10,.1f}  EMA150 {s_[i]:>10,.1f}   "
              f"-> {'UPTREND' if up else 'DOWNTREND' if dn else 'flat'}")
        print(f"  pullback EMA20  {e20[i]:>10,.1f}   close is "
              f"{'above' if Cs[i] > e20[i] else 'below'}")
        print(f"  breakout level  {hiN:>10,.1f}  (50-bar high, prior bars)   "
              f"{'CLEARED' if Cs[i] > hiN else f'{hiN-Cs[i]:,.0f} pts away'}")
        print(f"  up-volume   {('n/a' if upv is None else f'{upv*100:>5.1f}%'):>8}   "
              f"needs > {('n/a' if uThr is None else f'{uThr*100:.1f}%')}   "
              f"-> {'PASS' if gateL else 'fail'}")
        print(f"  down-volume {('n/a' if dnv is None else f'{dnv*100:>5.1f}%'):>8}   "
              f"needs > {('n/a' if dThr is None else f'{dThr*100:.1f}%')}   "
              f"-> {'PASS' if gateS else 'fail'}")
        sig = []
        if gateL and boLong:  sig.append("BUY  (breakout + up-volume)")
        if gateL and pbLong:  sig.append("BUY  (pullback, optional entry - off by default)")
        if gateS and pbShort: sig.append("SELL (failed rally + down-volume)")
        print(f"  SIGNAL: {'  |  '.join(sig) if sig else 'none'}")
        if sig and 'BUY  (breakout' in sig[0]:
            print(f"          stop would sit at {Cs[i]-3*A[i]:,.1f}")
        print()

    # Intraday, every constituent's volume is only a fraction of a full day, so
    # rvol is mechanically depressed and the gate reads low for reasons that have
    # nothing to do with the market. Report how far through the session we are.
    if mkt_open:
        o = now_ist.replace(hour=9, minute=15, second=0, microsecond=0)
        c = now_ist.replace(hour=15, minute=30, second=0, microsecond=0)
        frac = (now_ist - o).total_seconds() / (c - o).total_seconds()
        print(f"  NOTE: {frac*100:.0f}% of the session elapsed. Constituent volume is")
        print(f"        partial, so today's volume gate reads low by construction")
        print(f"        and cannot be acted on until the close.\n")

    state(len(nf)-2, "LAST CONFIRMED SESSION")
    if last_day == now_ist.date():
        state(len(nf)-1, "TODAY, PROVISIONAL — bar still forming" if mkt_open
              else "TODAY, CLOSED")
    else:
        print(f"=== no bar for {now_ist.date()} yet in the feed "
              f"(latest is {last_day})")
