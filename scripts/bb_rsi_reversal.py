"""Bollinger Band + RSI reversal (from an Instagram reel), bar by bar.

Rules as given in the reel
  buy   RSI(14) < 24 and the candle closes below the lower Bollinger Band (20, 2)
  sell  RSI(14) > 76 and the candle closes above the upper band
The reel gives no exit, so several are tested. Entry is at the next bar's open.
  mid    exit when price touches the middle band (SMA 20); stop 1.5 x ATR
  rr1    stop 1 x ATR, target 1 x ATR
  rr2    stop 1 x ATR, target 2 x ATR
  wide   stop 3 x ATR, exit at the middle band (the high win-rate setting)
1R = the stop distance. A bar that touches both stop and target counts as a
loss. One position at a time.

Usage: python3 scripts/bb_rsi_reversal.py <bars.json> [label] [cost_bp]
"""
from __future__ import annotations
import json, sys, math, statistics as st
from supply_demand import atr


def bands(b, n=20, k=2.0):
    mid, up, lo = [None] * len(b), [None] * len(b), [None] * len(b)
    for i in range(n - 1, len(b)):
        w = [x["c"] for x in b[i - n + 1:i + 1]]
        m = sum(w) / n
        sd = math.sqrt(sum((x - m) ** 2 for x in w) / n)
        mid[i], up[i], lo[i] = m, m + k * sd, m - k * sd
    return mid, up, lo


def rsi(b, n=14):
    out, up, dn = [None] * len(b), 0.0, 0.0
    for i in range(1, len(b)):
        ch = b[i]["c"] - b[i - 1]["c"]
        u, d = max(ch, 0), max(-ch, 0)
        if i <= n:
            up += u / n; dn += d / n
        else:
            up = (up * (n - 1) + u) / n; dn = (dn * (n - 1) + d) / n
        if i >= n:
            out[i] = 100.0 if dn == 0 else 100 - 100 / (1 + up / dn)
    return out


def run(b, exit="mid", lo_th=24, hi_th=76, cost_bp=1.0):
    mid, up, lo = bands(b)
    r, a = rsi(b), atr(b)
    stop_k, tgt_k = {"mid": (1.5, None), "rr1": (1, 1), "rr2": (1, 2), "wide": (3, None)}[exit]
    rs, i = [], 21
    while i < len(b) - 1:
        if None in (r[i], lo[i], a[i]):
            i += 1; continue
        side = 1 if (r[i] < lo_th and b[i]["c"] < lo[i]) else \
              -1 if (r[i] > hi_th and b[i]["c"] > up[i]) else 0
        if not side:
            i += 1; continue
        e = b[i + 1]["o"]; R = stop_k * a[i]
        stop = e - side * R
        tgt = None if tgt_k is None else e + side * tgt_k * a[i]
        cost = e * cost_bp / 1e4 / R
        res = None
        for j in range(i + 1, len(b)):
            y = b[j]
            if (side == 1 and y["l"] <= stop) or (side == -1 and y["h"] >= stop):
                res = -1 - cost; break
            if tgt is not None:
                if (side == 1 and y["h"] >= tgt) or (side == -1 and y["l"] <= tgt):
                    res = tgt_k / stop_k - cost; break
            elif mid[j] is not None and ((side == 1 and y["h"] >= mid[j]) or (side == -1 and y["l"] <= mid[j])):
                px = max(mid[j], y["o"]) if side == 1 else min(mid[j], y["o"])
                res = side * (px - e) / R - cost; break
        if res is None:
            break
        rs.append((side, res))
        i = j + 1
    return rs


def fmt(rs):
    if not rs:
        return "    0 trades"
    x = [r for _, r in rs]
    w = [v for v in x if v > 0]; l = [-v for v in x if v <= 0]
    eq = pk = dd = 0
    for v in x:
        eq += v; pk = max(pk, eq); dd = max(dd, pk - eq)
    pf = sum(w) / sum(l) if l else float("inf")
    return (f"{len(x):>4} trades  win {100*len(w)/len(x):5.1f}%  PF {pf:5.2f}  "
            f"exp {st.mean(x):+.3f}R  total {sum(x):+6.1f}R  maxDD {dd:5.1f}R")


if __name__ == "__main__":
    b = json.load(open(sys.argv[1]))
    c = float(sys.argv[3]) if len(sys.argv) > 3 else 1.0
    print(f"== {sys.argv[2] if len(sys.argv) > 2 else sys.argv[1]}: {len(b)} bars, cost {c}bp ==")
    h = len(b) // 2
    for ex, name in (("mid", "exit at middle band, 1.5 ATR stop"), ("rr1", "1 ATR stop, 1:1"),
                     ("rr2", "1 ATR stop, 1:2"), ("wide", "3 ATR stop, exit at middle band")):
        rs = run(b, exit=ex, cost_bp=c)
        h1, h2 = run(b[:h], exit=ex, cost_bp=c), run(b[h:], exit=ex, cost_bp=c)
        m = lambda z: st.mean([r for _, r in z]) if z else 0
        print(f"{name:<36} {fmt(rs)}")
        print(f"{'':<36}   longs {fmt([x for x in rs if x[0]==1])[:40]} | halves {m(h1):+.3f}R / {m(h2):+.3f}R")
