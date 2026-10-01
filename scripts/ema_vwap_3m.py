"""EMA / session-VWAP cross on 3-minute gold, bar by bar.

Signal   EMA(n) crosses session VWAP on a closed bar; enter at the next bar's
         open in the direction of the cross. VWAP resets at the CME session
         open (22:00 UTC), or after any gap longer than 30 minutes.
Exits    sar    always in the market, reverse on the opposite cross
         brk    stop 1 x ATR(14), target rr x ATR, the cross ignored once in
         xstop  stop 1 x ATR, exit on the opposite cross
R        1R = ATR(14) at entry, so every mode is on the same scale.
Cost     cost_bp of price per round turn. A bar that touches both stop and
         target is scored as a loss.

Usage: python3 scripts/ema_vwap_3m.py <3m bars.json> [label]
"""
from __future__ import annotations
import json, sys, datetime as dt, statistics as st
from supply_demand import atr


def ema(b, n):
    out, k, v = [], 2 / (n + 1), None
    for x in b:
        v = x["c"] if v is None else v + k * (x["c"] - v)
        out.append(v)
    return out


def vwap(b):
    out, pv, vv, prev = [], 0.0, 0.0, None
    for x in b:
        h = dt.datetime.utcfromtimestamp(x["t"]).hour
        new = prev is None or x["t"] - prev > 1800 or \
            (h == 22 and dt.datetime.utcfromtimestamp(prev).hour != 22)
        if new:
            pv = vv = 0.0
        tp = (x["h"] + x["l"] + x["c"]) / 3
        v = x["v"] or 1
        pv += tp * v; vv += v
        out.append(pv / vv)
        prev = x["t"]
    return out


def crosses(b, n):
    e, w = ema(b, n), vwap(b)
    sig = [0] * len(b)
    for i in range(1, len(b)):
        if e[i - 1] <= w[i - 1] and e[i] > w[i]:
            sig[i] = 1
        elif e[i - 1] >= w[i - 1] and e[i] < w[i]:
            sig[i] = -1
    return sig


def in_hours(t, hours):
    return hours is None or hours[0] <= dt.datetime.utcfromtimestamp(t).hour < hours[1]


def run(b, n=9, mode="brk", rr=2.0, cost_bp=1.0, hours=None):
    a, sig = atr(b), crosses(b, n)
    rs, i = [], 15
    pos = None                                   # (side, entry, risk, i_entry)
    while i < len(b) - 1:
        s = sig[i]
        if mode == "sar":
            if s and a[i]:
                if pos:
                    side, e, R, _ = pos
                    px = b[i + 1]["o"]
                    rs.append(side * (px - e) / R - e * cost_bp / 1e4 / R)
                    pos = None
                if in_hours(b[i + 1]["t"], hours):
                    pos = (s, b[i + 1]["o"], a[i], i + 1)
            i += 1
            continue
        if not s or not a[i] or not in_hours(b[i + 1]["t"], hours):
            i += 1
            continue
        side, e, R = s, b[i + 1]["o"], a[i]
        stop, tgt = e - side * R, e + side * rr * R
        cost = e * cost_bp / 1e4 / R
        res, j = None, i + 1
        while j < len(b):
            y = b[j]
            if (side == 1 and y["l"] <= stop) or (side == -1 and y["h"] >= stop):
                res = -1 - cost
                break
            if mode == "brk" and ((side == 1 and y["h"] >= tgt) or (side == -1 and y["l"] <= tgt)):
                res = rr - cost
                break
            if mode == "xstop" and sig[j] == -side and j + 1 < len(b):
                res = side * (b[j + 1]["o"] - e) / R - cost
                j += 1
                break
            j += 1
        if res is None:
            break
        rs.append(res)
        i = j
    return rs


def fmt(rs):
    if not rs:
        return "    0 trades"
    w = [x for x in rs if x > 0]
    l = [-x for x in rs if x <= 0]
    pf = sum(w) / sum(l) if l else float("inf")
    eq = pk = dd = 0
    for x in rs:
        eq += x; pk = max(pk, eq); dd = max(dd, pk - eq)
    return (f"{len(rs):>5} trades  win {100*len(w)/len(rs):5.1f}%  PF {pf:5.2f}  "
            f"exp {st.mean(rs):+.3f}R  total {sum(rs):+7.1f}R  maxDD {dd:6.1f}R")


if __name__ == "__main__":
    b = json.load(open(sys.argv[1]))
    print(f"== {sys.argv[2] if len(sys.argv) > 2 else sys.argv[1]}: {len(b)} bars ==")
    h = len(b) // 2
    rows = []
    for n in (9, 20):
        rows += [(f"EMA{n:<2} stop-and-reverse", dict(n=n, mode="sar")),
                 (f"EMA{n:<2} 1 ATR stop, 1:1", dict(n=n, mode="brk", rr=1.0)),
                 (f"EMA{n:<2} 1 ATR stop, 1:2", dict(n=n, mode="brk", rr=2.0)),
                 (f"EMA{n:<2} 1 ATR stop, exit on cross", dict(n=n, mode="xstop"))]
    rows += [("EMA9  1:2, London/NY 12-17 UTC", dict(n=9, mode="brk", rr=2.0, hours=(12, 17))),
             ("EMA9  1:2, zero cost", dict(n=9, mode="brk", rr=2.0, cost_bp=0.0)),
             ("EMA9  exit on cross, zero cost", dict(n=9, mode="xstop", cost_bp=0.0))]
    for name, kw in rows:
        r1, r2 = run(b[:h], **kw), run(b[h:], **kw)
        print(f"{name:<34} {fmt(run(b, **kw))}")
        print(f"{'':<34}   halves exp {st.mean(r1) if r1 else 0:+.3f}R / {st.mean(r2) if r2 else 0:+.3f}R")
