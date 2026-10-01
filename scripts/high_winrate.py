"""Search for gold strategies with >= 90% win rate AND positive expectancy.

A high win rate on its own is cheap: put the target close and the stop far
away. So every row reports win rate next to expectancy (average R per trade,
1R = the initial stop distance) and the worst losing streak, and a candidate
has to clear 90% wins with positive expectancy in BOTH halves of the data.

Families
  control  trend-direction entry on every bar, tiny target, wide stop.
           No signal at all: it shows what the target/stop ratio alone does.
  rsi2     long only above SMA(200); buy the close when RSI(2) < th;
           exit at the first close above SMA(5), or after `hold` bars;
           hard stop k x ATR below entry.
  sd       the supply/demand zones from supply_demand.py with small R:R.

Usage: python3 scripts/high_winrate.py <bars.json> [label]
"""
from __future__ import annotations
import json, sys, statistics as st
from supply_demand import atr, run as sd_run

COST_BP = 1.0


def sma(b, n):
    out, s = [None] * len(b), 0.0
    for i, x in enumerate(b):
        s += x["c"]
        if i >= n:
            s -= b[i - n]["c"]
        out[i] = s / n if i >= n - 1 else None
    return out


def rsi(b, n=2):
    out, up, dn = [None] * len(b), 0.0, 0.0
    for i in range(1, len(b)):
        ch = b[i]["c"] - b[i - 1]["c"]
        u, d = max(ch, 0), max(-ch, 0)
        if i <= n:
            up += u / n; dn += d / n
        else:
            up = (up * (n - 1) + u) / n; dn = (dn * (n - 1) + d) / n
        if i >= n:
            out[i] = 100 if dn == 0 else 100 - 100 / (1 + up / dn)
    return out


def control(b, tgt_atr, stop_atr):
    a, m = atr(b), sma(b, 200)
    rs, i = [], 201
    while i < len(b) - 1:
        if a[i] is None or m[i] is None:
            i += 1; continue
        side = 1 if b[i]["c"] > m[i] else -1
        e = b[i]["c"]; risk = stop_atr * a[i]
        tgt, stop = e + side * tgt_atr * a[i], e - side * risk
        cost = e * COST_BP / 1e4 / risk
        for k in range(i + 1, len(b)):
            y = b[k]
            if (side == 1 and y["l"] <= stop) or (side == -1 and y["h"] >= stop):
                rs.append(-1 - cost); break
            if (side == 1 and y["h"] >= tgt) or (side == -1 and y["l"] <= tgt):
                rs.append(tgt_atr / stop_atr - cost); break
        else:
            break
        i = k + 1
    return rs


def rsi2(b, th=10, hold=10, k=3.0):
    a, m200, m5, r = atr(b), sma(b, 200), sma(b, 5), rsi(b)
    rs, i = [], 201
    while i < len(b) - 1:
        if None in (a[i], m200[i], r[i]) or not (b[i]["c"] > m200[i] and r[i] < th):
            i += 1; continue
        e = b[i]["c"]; risk = k * a[i]; stop = e - risk
        cost = e * COST_BP / 1e4 / risk
        out = None
        for j in range(i + 1, min(len(b), i + 1 + hold)):
            if b[j]["l"] <= stop:
                out = (j, -1 - cost); break
            if m5[j] is not None and b[j]["c"] > m5[j]:
                out = (j, (b[j]["c"] - e) / risk - cost); break
        if out is None:
            j = min(len(b) - 1, i + hold)
            out = (j, (b[j]["c"] - e) / risk - cost)
        rs.append(out[1])
        i = out[0] + 1
    return rs


def fmt(rs):
    if not rs:
        return "   0 trades"
    w = sum(1 for x in rs if x > 0)
    streak = worst = 0
    for x in rs:
        streak = streak + 1 if x <= 0 else 0
        worst = max(worst, streak)
    return (f"{len(rs):>5} trades  win {100*w/len(rs):5.1f}%  exp {st.mean(rs):+.3f}R  "
            f"total {sum(rs):+7.1f}R  worst loss streak {worst}")


def halves(fn, b, **kw):
    h = len(b) // 2
    return fn(b, **kw), fn(b[:h], **kw), fn(b[h:], **kw)


if __name__ == "__main__":
    b = json.load(open(sys.argv[1]))
    print(f"== {sys.argv[2] if len(sys.argv) > 2 else sys.argv[1]}: {len(b)} bars ==")
    rows = []
    for t, s in ((0.1, 1.0), (0.2, 2.0), (0.25, 3.0), (0.5, 5.0)):
        rows.append((f"control  tgt {t} / stop {s} ATR", halves(control, b, tgt_atr=t, stop_atr=s)))
    for th in (5, 10):
        for k in (2.0, 3.0, 5.0):
            rows.append((f"rsi2     <{th:<2} stop {k} ATR", halves(rsi2, b, th=th, k=k)))
    for rr in (0.2, 0.33, 0.5):
        f = lambda x, rr=rr: [r for _, r in sd_run(x, rr=rr)]
        rows.append((f"sd zones rr {rr}", halves(f, b)))
    for name, (full, h1, h2) in rows:
        tag = ""
        if full and all(len(x) and sum(r > 0 for r in x) / len(x) >= 0.9 and st.mean(x) > 0
                        for x in (full, h1, h2)):
            tag = "  <-- CANDIDATE"
        print(f"{name:<30} {fmt(full)}{tag}")
        print(f"{'':<30}   halves: exp {st.mean(h1) if h1 else 0:+.3f}R / "
              f"{st.mean(h2) if h2 else 0:+.3f}R")
