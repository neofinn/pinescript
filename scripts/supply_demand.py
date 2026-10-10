"""Supply/demand zones on gold, bar by bar, matching mt5/GoldSupplyDemand.mq5.

Zone (demand; supply is the mirror):
  base     1..max_base candles, each with range <= base_atr x ATR
  leg-out  the next candle: range >= leg_atr x ATR, body >= 60% of its range,
           and it closes above the highest high of the base
  proximal highest body (max of open/close) of the base  -> entry (buy limit)
  distal   lowest low of base and leg-out                -> stop goes below it
  height   proximal - distal must be <= max_h x ATR

Trade the first touch only: a buy limit at proximal, stop at distal - buf x ATR,
target rr x risk. The order lives for `life` bars and is cancelled if a bar
closes below distal before it fills. Optional trend filter: demand only when
the leg-out closes above EMA(ema), supply only below. One position at a time.
A bar that touches both stop and target is scored as a loss.

Usage: python3 scripts/supply_demand.py <bars.json> [label]
"""
from __future__ import annotations
import json, sys, statistics as st


def atr(b, n=14):
    out, prev = [None] * len(b), None
    for i, x in enumerate(b):
        tr = x["h"] - x["l"] if i == 0 else max(x["h"] - x["l"], abs(x["h"] - b[i-1]["c"]),
                                                 abs(x["l"] - b[i-1]["c"]))
        prev = tr if prev is None else (prev * (n - 1) + tr) / n
        out[i] = prev if i >= n else None
    return out


def ema(b, n):
    out, k, v = [None] * len(b), 2 / (n + 1), None
    for i, x in enumerate(b):
        v = x["c"] if v is None else v + k * (x["c"] - v)
        out[i] = v if i >= n else None
    return out


def zones(b, a, e, max_base=3, base_atr=0.8, leg_atr=1.5, max_h=2.0, trend=True):
    """Yield (i_legout, side, proximal, distal) as each leg-out candle closes."""
    for i in range(max(2, max_base + 1), len(b)):
        A = a[i - 1]
        if A is None:
            continue
        L = b[i]
        rng = L["h"] - L["l"]
        if rng < leg_atr * A or abs(L["c"] - L["o"]) < 0.6 * rng:
            continue
        # the longest run of small candles right before the leg-out, up to max_base
        k = 0
        while k < max_base and (b[i-1-k]["h"] - b[i-1-k]["l"]) <= base_atr * A:
            k += 1
        if k == 0:
            continue
        base = b[i-k:i]
        if L["c"] > L["o"] and L["c"] > max(x["h"] for x in base):
            if trend and (e[i] is None or L["c"] < e[i]):
                continue
            prox = max(max(x["o"], x["c"]) for x in base)
            dist = min(min(x["l"] for x in base), L["l"])
            side = 1
        elif L["c"] < L["o"] and L["c"] < min(x["l"] for x in base):
            if trend and (e[i] is None or L["c"] > e[i]):
                continue
            prox = min(min(x["o"], x["c"]) for x in base)
            dist = max(max(x["h"] for x in base), L["h"])
            side = -1
        else:
            continue
        if abs(prox - dist) > max_h * A or prox == dist:
            continue
        yield i, side, prox, dist, A


def run(b, rr=2.0, buf=0.1, life=48, cost_bp=1.0, **zk):
    a, e = atr(b), ema(b, 200)
    rs, busy_until = [], -1
    for i, side, prox, dist, A in zones(b, a, e, **zk):
        if i <= busy_until:
            continue
        stop = dist - side * buf * A
        risk = abs(prox - stop)
        tgt = prox + side * rr * risk
        cost_r = prox * cost_bp / 1e4 / risk
        filled = None
        for k in range(i + 1, min(len(b), i + 1 + life)):
            y = b[k]
            if (side == 1 and y["l"] <= prox) or (side == -1 and y["h"] >= prox):
                filled = k
                break
            if (side == 1 and y["c"] < dist) or (side == -1 and y["c"] > dist):
                break
        if filled is None:
            continue
        r = None
        for k in range(filled, len(b)):
            y = b[k]
            hit_stop = y["l"] <= stop if side == 1 else y["h"] >= stop
            hit_tgt = y["h"] >= tgt if side == 1 else y["l"] <= tgt
            if hit_stop:
                r = -1 - cost_r
            elif hit_tgt:
                r = rr - cost_r
            if r is not None:
                busy_until = k
                break
        if r is not None:
            rs.append((side, r))
    return rs


def fmt(rs):
    if not rs:
        return "   0 trades"
    r = [x for _, x in rs]
    w = [x for x in r if x > 0]
    l = [-x for x in r if x <= 0]
    eq = pk = dd = 0
    for x in r:
        eq += x; pk = max(pk, eq); dd = max(dd, pk - eq)
    pf = sum(w) / sum(l) if l else float("inf")
    return (f"{len(r):>4} trades  win {100*len(w)/len(r):5.1f}%  PF {pf:5.2f}  "
            f"exp {st.mean(r):+.3f}R  total {sum(r):+6.1f}R  maxDD {dd:5.1f}R")


if __name__ == "__main__":
    b = json.load(open(sys.argv[1]))
    print(f"== {sys.argv[2] if len(sys.argv) > 2 else sys.argv[1]}: {len(b)} bars ==")
    base = dict(rr=2.0, buf=0.1, life=48, cost_bp=1.0, trend=True)
    rs = run(b, **base)
    print("default     ", fmt(rs))
    print("  longs     ", fmt([x for x in rs if x[0] == 1]))
    print("  shorts    ", fmt([x for x in rs if x[0] == -1]))
    print("no trend    ", fmt(run(b, **{**base, "trend": False})))
    for rr in (1.0, 1.5, 3.0):
        print(f"rr 1:{rr:<4}   ", fmt(run(b, **{**base, "rr": rr})))
    for lg in (1.2, 2.0):
        print(f"leg {lg} ATR  ", fmt(run(b, **{**base, "leg_atr": lg})))
    for c in (0.0, 3.0):
        print(f"cost {c}bp   ", fmt(run(b, **{**base, "cost_bp": c})))
    h = len(b) // 2
    print("1st half    ", fmt(run(b[:h], **base)))
    print("2nd half    ", fmt(run(b[h:], **base)))
