"""Fibonacci retracement entries on gold, bar by bar.

Swing     pivot highs/lows with `piv` bars on each side, known only `piv` bars
          after the pivot (no look-ahead).
Impulse   up: a confirmed pivot low followed by a confirmed pivot high, leg size
          >= min_leg x ATR. Down is the mirror.
Entry     buy limit at the `level` retracement of the leg (0.5 = 50%,
          0.618 = 61.8% ...), placed when the swing high is confirmed. Skipped if
          price already traded through the level before confirmation.
          Cancelled after `life` bars, or if price makes a new high first.
Stop      `stop` retracement of the leg (1.0 = beyond the swing low).
Target    `tgt` on the Fibonacci scale: 0.0 = back to the swing high,
          -0.272 / -0.618 = extensions beyond it.
1R = entry-to-stop distance. A bar that touches both stop and target counts
as a loss. One position at a time.

Usage: python3 scripts/fib_retracement.py <bars.json> [label] [cost_bp]
"""
from __future__ import annotations
import json, sys, random, statistics as st
from supply_demand import atr


def pivots(b, piv):
    """(confirm_index, pivot_index, kind, price) in confirmation order."""
    out = []
    for i in range(piv, len(b) - piv):
        hs = [x["h"] for x in b[i - piv:i + piv + 1]]
        ls = [x["l"] for x in b[i - piv:i + piv + 1]]
        if b[i]["h"] == max(hs):
            out.append((i + piv, i, "H", b[i]["h"]))
        if b[i]["l"] == min(ls):
            out.append((i + piv, i, "L", b[i]["l"]))
    return sorted(out)


def setups(b, piv=5, min_leg=3.0):
    a = atr(b)
    last = {"H": None, "L": None}
    for conf, idx, kind, px in pivots(b, piv):
        other = "L" if kind == "H" else "H"
        prev = last[other]
        last[kind] = (idx, px)
        if prev is None or prev[0] >= idx or a[conf] is None:
            continue
        leg = abs(px - prev[1])
        if leg < min_leg * a[conf]:
            continue
        side = 1 if kind == "H" else -1          # swing high confirmed -> buy the pullback
        yield conf, idx, side, prev[1], px       # (confirm, extreme idx, side, origin, extreme)


def run(b, level=0.618, stop=1.0, tgt=0.0, life=48, cost_bp=1.0, piv=5, min_leg=3.0):
    rs, busy = [], -1
    for conf, idx, side, origin, ext in setups(b, piv, min_leg):
        if conf <= busy or conf + 1 >= len(b):
            continue
        leg = ext - origin                         # signed
        entry = ext - level * leg
        sl = ext - stop * leg
        tp = ext - tgt * leg
        risk = abs(entry - sl)
        if risk <= 0:
            continue
        # skip if the pullback already reached the level before we could know the swing
        between = b[idx + 1:conf + 1]
        if between and ((side == 1 and min(x["l"] for x in between) <= entry) or
                        (side == -1 and max(x["h"] for x in between) >= entry)):
            continue
        cost = entry * cost_bp / 1e4 / risk
        filled = None
        for k in range(conf + 1, min(len(b), conf + 1 + life)):
            y = b[k]
            if (side == 1 and y["h"] > ext) or (side == -1 and y["l"] < ext):
                break                               # new extreme first: setup void
            if (side == 1 and y["l"] <= entry) or (side == -1 and y["h"] >= entry):
                filled = k
                break
        if filled is None:
            continue
        res = None
        for k in range(filled, len(b)):
            y = b[k]
            if (side == 1 and y["l"] <= sl) or (side == -1 and y["h"] >= sl):
                res = -1 - cost
            elif (side == 1 and y["h"] >= tp) or (side == -1 and y["l"] <= tp):
                res = abs(tp - entry) / risk - cost
            if res is not None:
                busy = k
                break
        if res is not None:
            rs.append(res)
    return rs


def control(b, n, rr, draws=200, seed=3):
    """Random entries with the same reward:risk and a 1 ATR stop."""
    a, rng, exps = atr(b), random.Random(seed), []
    for _ in range(draws):
        rs = []
        for i in sorted(rng.sample(range(30, len(b) - 2), n)):
            side = rng.choice((1, -1)); e = b[i + 1]["o"]; R = a[i]
            sl, tp = e - side * R, e + side * rr * R
            for y in b[i + 1:]:
                if (side == 1 and y["l"] <= sl) or (side == -1 and y["h"] >= sl):
                    rs.append(-1); break
                if (side == 1 and y["h"] >= tp) or (side == -1 and y["l"] <= tp):
                    rs.append(rr); break
        if rs:
            exps.append(st.mean(rs))
    return exps


def fmt(rs):
    if not rs:
        return "    0 trades"
    w = [x for x in rs if x > 0]; l = [-x for x in rs if x <= 0]
    pf = sum(w) / sum(l) if l else float("inf")
    return (f"{len(rs):>4} trades  win {100*len(w)/len(rs):5.1f}%  PF {pf:5.2f}  "
            f"exp {st.mean(rs):+.3f}R  total {sum(rs):+6.1f}R")


if __name__ == "__main__":
    b = json.load(open(sys.argv[1]))
    c = float(sys.argv[3]) if len(sys.argv) > 3 else 1.0
    print(f"== {sys.argv[2] if len(sys.argv) > 2 else sys.argv[1]}: {len(b)} bars, cost {c}bp ==")
    h = len(b) // 2
    m = lambda z: st.mean(z) if z else 0.0
    rows = []
    for level, stop in ((0.382, 0.618), (0.5, 0.786), (0.618, 0.786), (0.618, 1.0), (0.786, 1.0)):
        for tgt in (0.0, -0.272):
            rows.append((level, stop, tgt))
    for level, stop, tgt in rows:
        kw = dict(level=level, stop=stop, tgt=tgt, cost_bp=c)
        rs = run(b, **kw)
        name = f"entry {level*100:4.1f}%  stop {stop*100:5.1f}%  tgt {'swing' if tgt == 0 else 'ext 127%'}"
        print(f"{name:<40} {fmt(rs)}  halves {m(run(b[:h], **kw)):+.3f} / {m(run(b[h:], **kw)):+.3f}")
