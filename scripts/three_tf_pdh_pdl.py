"""The 3-timeframe system, tested as specified.

  Daily   mark PDH / PDL from the previous session
  15M     wait for a CLOSE beyond the level (not a wick)
  5M      wait for price to retest the level, then take a hammer or a
          bullish engulfing in the breakout direction
  Stop    below the signal candle's low (above its high for shorts)
  Target  a fixed multiple of that risk

Shorts are the mirror: close below PDL, retest, shooting star or bearish
engulfing.

The binding limit is data. Yahoo serves about sixty days of 5-minute bars and
no more, so this is three months of calendar however many trades it produces.
"""
import urllib.request, json, datetime, collections, sys, time

H = {"User-Agent": "Mozilla/5.0"}

def fetch(sym, rng, iv, tries=4):
    u = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range={rng}&interval={iv}"
    for a in range(tries):
        try:
            d = json.load(urllib.request.urlopen(urllib.request.Request(u, headers=H), timeout=60))
            r = d["chart"]["result"][0]; ts = r["timestamp"]; q = r["indicators"]["quote"][0]
            return [{"t": t, "o": q["open"][i], "h": q["high"][i], "l": q["low"][i],
                     "c": q["close"][i], "v": q["volume"][i] or 0}
                    for i, t in enumerate(ts) if q["close"][i] is not None]
        except Exception:
            if a == tries-1: return None
            time.sleep(2**a)

def sess(t, anchor=0):
    d = datetime.datetime.fromtimestamp(t, datetime.UTC)
    return (d - datetime.timedelta(hours=anchor)).date()

# ── candle patterns, as normally defined ───────────────────────────────────
def hammer(b, prev=None):
    body = abs(b["c"] - b["o"]); rng = b["h"] - b["l"]
    if rng <= 0 or body <= 0: return False
    lower = min(b["o"], b["c"]) - b["l"]
    upper = b["h"] - max(b["o"], b["c"])
    return lower >= 2*body and upper <= body and b["c"] >= b["o"]

def shooting_star(b, prev=None):
    body = abs(b["c"] - b["o"]); rng = b["h"] - b["l"]
    if rng <= 0 or body <= 0: return False
    upper = b["h"] - max(b["o"], b["c"])
    lower = min(b["o"], b["c"]) - b["l"]
    return upper >= 2*body and lower <= body and b["c"] <= b["o"]

def bull_engulf(b, prev):
    if prev is None: return False
    return (b["c"] > b["o"] and prev["c"] < prev["o"]
            and b["c"] >= prev["o"] and b["o"] <= prev["c"])

def bear_engulf(b, prev):
    if prev is None: return False
    return (b["c"] < b["o"] and prev["c"] > prev["o"]
            and b["c"] <= prev["o"] and b["o"] >= prev["c"])

def backtest(m5, m15, daily, target_r=2.0, retest_tol=0.0015, side="both",
             cost_bp=1.0, anchor=0, expire_bars=60, need_pattern=True):
    """One position at a time. A setup expires at the end of its session."""
    pdh = {}; pdl = {}
    dd = sorted({sess(b["t"], anchor) for b in daily})
    dmap = {sess(b["t"], anchor): b for b in daily}
    for i in range(1, len(dd)):
        prev = dmap[dd[i-1]]
        pdh[dd[i]] = prev["h"]; pdl[dd[i]] = prev["l"]

    # 15M breakout state, per session
    broke_up = {}; broke_dn = {}
    for b in m15:
        d = sess(b["t"], anchor)
        if d not in pdh: continue
        if b["c"] > pdh[d] and d not in broke_up: broke_up[d] = b["t"]
        if b["c"] < pdl[d] and d not in broke_dn: broke_dn[d] = b["t"]

    out = []; pos = None; armedL = armedS = None
    prev5 = None
    for i, b in enumerate(m5):
        d = sess(b["t"], anchor)
        cost = b["c"] * cost_bp / 10000.0
        if pos:
            dirn, ep, sl, tp = pos
            hit_sl = (b["l"] <= sl) if dirn > 0 else (b["h"] >= sl)
            hit_tp = (b["h"] >= tp) if dirn > 0 else (b["l"] <= tp)
            done = None
            if hit_sl and hit_tp: done = sl          # same bar: assume the stop
            elif hit_sl: done = sl
            elif hit_tp: done = tp
            if done is not None:
                risk = abs(ep - sl)
                R = (((done-ep) if dirn > 0 else (ep-done)) - cost) / risk if risk > 0 else 0
                out.append(dict(R=R, dir=dirn, d=str(d)))
                pos = None
            else:
                prev5 = b; continue
        if d not in pdh: prev5 = b; continue
        lvl_u, lvl_d = pdh[d], pdl[d]
        # arm only after the 15M close beyond the level
        upOK = d in broke_up and b["t"] > broke_up[d]
        dnOK = d in broke_dn and b["t"] > broke_dn[d]
        if pos is None:
            sigL = sigS = False
            if upOK and side in ("both","long"):
                retest = b["l"] <= lvl_u * (1 + retest_tol)
                pat = hammer(b, prev5) or bull_engulf(b, prev5) if need_pattern else True
                sigL = retest and pat and b["c"] > lvl_u * (1 - retest_tol)
            if dnOK and side in ("both","short"):
                retest = b["h"] >= lvl_d * (1 - retest_tol)
                pat = shooting_star(b, prev5) or bear_engulf(b, prev5) if need_pattern else True
                sigS = retest and pat and b["c"] < lvl_d * (1 + retest_tol)
            if sigL or sigS:
                dirn = 1 if sigL else -1
                ep = b["c"]
                sl = b["l"] if dirn > 0 else b["h"]
                risk = abs(ep - sl)
                if risk > 0:
                    tp = ep + dirn * target_r * risk
                    pos = (dirn, ep, sl, tp)
        prev5 = b
    return out

def stat(v):
    if len(v) < 5: return None
    w=[x for x in v if x>0]; gl=abs(sum(x for x in v if x<=0))
    pf=sum(w)/gl if gl>0 else 99.0
    eq=pk=dd=0.0
    for x in v: eq+=x; pk=max(pk,eq); dd=max(dd,pk-eq)
    return len(v), len(w)/len(v)*100, sum(v), sum(v)/len(v), pf, dd
def line(lbl,t,w=34):
    r=stat([x["R"] for x in t])
    if not r: return f"  {lbl:<{w}}{len(t):>6}   too few"
    n,wr,net,ex,pf,dd=r
    return f"  {lbl:<{w}}{n:>6}{wr:>7.1f}%{net:>+9.1f}R{ex:>+8.3f}R{pf:>7.2f}{dd:>8.1f}R"
HD=lambda w=34: f"  {'':<{w}}{'trds':>6}{'win':>8}{'netR':>10}{'exp':>9}{'PF':>7}{'maxDD':>8}"

if __name__ == "__main__":
    for lbl, sym, anchor in (("GOLD GC=F", "GC%3DF", 22), ("NIFTY", "%5ENSEI", 0)):
        print(f"\n{'='*74}\n{lbl}")
        m5  = fetch(sym, "60d", "5m")
        m15 = fetch(sym, "60d", "15m")
        dly = fetch(sym, "1y", "1d")
        if not (m5 and m15 and dly): print("  data unavailable"); continue
        days = sorted({sess(b['t'], anchor) for b in m5})
        print(f"  {len(m5)} 5m bars, {len(m15)} 15m bars, {len(days)} sessions "
              f"({days[0]} -> {days[-1]})\n")
        print(HD())
        for tr in (2.0, 3.0):
            for sd in ("long","short","both"):
                print(line(f"target 1:{tr:.0f} RR   {sd}",
                           backtest(m5,m15,dly,target_r=tr,side=sd,anchor=anchor)))
            print()
        print("  pattern requirement — does the candle confirmation earn its place?")
        print(HD())
        print(line("with hammer/engulfing",
                   backtest(m5,m15,dly,target_r=2.0,anchor=anchor,need_pattern=True)))
        print(line("plain retest, no pattern",
                   backtest(m5,m15,dly,target_r=2.0,anchor=anchor,need_pattern=False)))
