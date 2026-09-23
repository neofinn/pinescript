"""Opening range breakout on NIFTY, gated by constituent volume surge.
Intraday only: every position is closed at the session bell.

Two data facts shape this. The index prints no volume at any timeframe, so the
surge gate is built from the 49 constituents. And intraday volume follows the
clock -- the 14:15 bar runs about twice the 11:15 bar -- so a bar is compared to
the trailing history of its OWN slot, not to a rolling average that would just
be measuring the time of day.

1R is the stop distance. Nothing caps the reward; a trade ends at its stop or
at the close, whichever comes first.
"""
import json, os, glob, datetime, collections, sys

SC = os.path.dirname(os.path.abspath(__file__))
IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
INTRA = os.path.join(SC, "intra")

def sessionise(bars):
    """-> ordered list of (date, [bars]) with a slot index on each bar."""
    s = collections.defaultdict(list)
    for b in bars:
        d = datetime.datetime.fromtimestamp(b["t"], IST)
        s[d.date()].append({**b, "hm": d.strftime("%H:%M")})
    out = []
    for d in sorted(s):
        day = sorted(s[d], key=lambda x: x["t"])
        for i, b in enumerate(day): b["slot"] = i
        out.append((d, day))
    return out

def load_index():
    return sessionise(json.load(open(os.path.join(INTRA, "NIFTY.json"))))

def constituent_rvol():
    """{(date, slot): fraction of names trading above 1.5x their own slot norm}"""
    hits = collections.defaultdict(lambda: [0, 0])       # [surging, counted]
    for p in sorted(glob.glob(os.path.join(INTRA, "*.json"))):
        sym = os.path.basename(p)[:-5]
        if sym == "NIFTY": continue
        sess = sessionise(json.load(open(p)))
        hist = collections.defaultdict(list)             # slot -> trailing volumes
        for d, day in sess:
            for b in day:
                sl = b["slot"]; v = b["v"]
                h = hist[sl]
                if len(h) >= 20 and v > 0:
                    m = sum(h[-20:]) / 20.0
                    if m > 0:
                        hits[(d, sl)][1] += 1
                        if v / m > 1.5: hits[(d, sl)][0] += 1
                if v > 0: h.append(v)
    return {k: (a / b) for k, (a, b) in hits.items() if b >= 20}

def atr_intraday(sess, n=14):
    """True range within the session only -- overnight gaps are not tradeable
    risk for a strategy that is flat every night."""
    out = {}; prev = None; vals = []
    for d, day in sess:
        for b in day:
            tr = b["h"] - b["l"] if b["slot"] == 0 else max(
                b["h"] - b["l"], abs(b["h"] - prev), abs(b["l"] - prev))
            vals.append(tr)
            if len(vals) > n: vals.pop(0)
            out[(d, b["slot"])] = sum(vals) / len(vals) if len(vals) == n else None
            prev = b["c"]
    return out

def run(sess, SURGE, ATR, or_bars=1, stop_mult=1.0, stop_mode="atr",
        gate=None, cost_bp=2.0, long_only=False, last_entry=5):
    """One position at a time, flat at the bell."""
    out = []
    for d, day in sess:
        if len(day) < or_bars + 2: continue
        orh = max(b["h"] for b in day[:or_bars])
        orl = min(b["l"] for b in day[:or_bars])
        pos = None
        for b in day[or_bars:]:
            a = ATR.get((d, b["slot"]))
            if a is None or a <= 0: continue
            cost = b["c"] * cost_bp / 10000.0
            if pos:
                dr, ep, stp, r0 = pos
                hit = (b["l"] <= stp) if dr > 0 else (b["h"] >= stp)
                last = b["slot"] == day[-1]["slot"]
                if hit:
                    px = stp
                elif last:
                    px = b["c"]
                else:
                    continue
                R = ((px - ep) if dr > 0 else (ep - px)) - cost
                out.append(dict(d=str(d), dir=dr, R=R / r0, slot=b["slot"],
                                why="stop" if hit else "bell"))
                pos = None
                continue
            if b["slot"] > last_entry: continue
            up = b["c"] > orh; dnb = b["c"] < orl and not long_only
            if not (up or dnb): continue
            g = SURGE.get((d, b["slot"]))
            if gate is not None and (g is None or not gate(g)): continue
            dr = 1 if up else -1
            r0 = stop_mult * a if stop_mode == "atr" else stop_mult * max(orh - orl, 1e-9)
            if r0 <= 0: continue
            pos = (dr, b["c"], b["c"] - dr * r0, r0)
        # a position open on the final bar is closed by the loop above
    return out

def stat(t):
    if len(t) < 5: return None
    v = [x["R"] for x in t]
    w = [x for x in v if x > 0]; gl = abs(sum(x for x in v if x <= 0))
    pf = sum(w) / gl if gl > 0 else 99.0
    eq = pk = dd = 0.0
    for r in v: eq += r; pk = max(pk, eq); dd = max(dd, pk - eq)
    return len(v), len(w) / len(v) * 100, sum(v), sum(v) / len(v), pf, dd

def line(lbl, t, w=34):
    r = stat(t)
    if not r: return f"  {lbl:<{w}}{len(t):>6}   too few"
    n, wr, net, ex, pf, dd = r
    return f"  {lbl:<{w}}{n:>6}{wr:>7.1f}%{net:>+9.1f}R{ex:>+8.3f}R{pf:>7.2f}{dd:>8.1f}R"
HDR = lambda w=34: f"  {'':<{w}}{'trds':>6}{'win':>8}{'netR':>10}{'exp':>9}{'PF':>7}{'maxDD':>8}"

if __name__ == "__main__":
    sess = load_index(); ATR = atr_intraday(sess); SURGE = constituent_rvol()
    print(f"NIFTY INTRADAY ORB — {len(sess)} sessions, hourly bars, flat at the bell")
    print("1R = stop distance, reward uncapped, 2bp cost\n")

    print("OPENING RANGE = first bar (09:15), stop 1x intraday ATR")
    print(HDR())
    print(line("no gate", run(sess, SURGE, ATR)))
    for th in (0.15, 0.20, 0.25, 0.30, 0.40):
        print(line(f"+ constituent surge > {int(th*100)}%",
                   run(sess, SURGE, ATR, gate=(lambda th: lambda g: g > th)(th))))
    print()
    print("OPENING RANGE = first two bars (09:15+10:15)")
    print(HDR())
    print(line("no gate", run(sess, SURGE, ATR, or_bars=2)))
    for th in (0.15, 0.20, 0.25, 0.30, 0.40):
        print(line(f"+ constituent surge > {int(th*100)}%",
                   run(sess, SURGE, ATR, or_bars=2, gate=(lambda th: lambda g: g > th)(th))))
    print()
    print("STOP DISTANCE  (OR = 1 bar, surge > 25%)")
    print(HDR())
    g25 = lambda g: g > 0.25
    for m in (0.5, 0.75, 1.0, 1.5, 2.0):
        print(line(f"stop {m}x ATR", run(sess, SURGE, ATR, stop_mult=m, gate=g25)))
    for m in (0.5, 1.0):
        print(line(f"stop {m}x opening range", run(sess, SURGE, ATR, stop_mult=m,
                                                   stop_mode="or", gate=g25)))
    print()
    print("DIRECTION AND EXIT MIX  (OR = 1 bar, stop 1x ATR, surge > 25%)")
    print(HDR())
    t = run(sess, SURGE, ATR, gate=g25)
    print(line("both sides", t))
    print(line("long only", [x for x in t if x["dir"] > 0]))
    print(line("short only", [x for x in t if x["dir"] < 0]))
    print(line("exited on stop", [x for x in t if x["why"] == "stop"]))
    print(line("exited at the bell", [x for x in t if x["why"] == "bell"]))
    print()
    print("HOLDS UP IN BOTH HALVES?")
    print(HDR())
    ds = sorted({x["d"] for x in t}); mid = ds[len(ds)//2]
    print(line(f"first half  (to {mid})", [x for x in t if x["d"] <= mid]))
    print(line(f"second half (from {mid})", [x for x in t if x["d"] > mid]))
