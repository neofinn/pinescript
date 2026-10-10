"""Swing-high inside-bar short on gold, bar-by-bar, matching swing_inside_short.pine.

Rule, as asked:
  On the 30-minute chart, a candle makes a swing high (the "mother" candle).
  The next candle is small and sits inside it. When price breaks that inside
  candle's low, go short.

How each piece is made concrete (all of them are inputs in the Pine script):
  swing high   mother high is the highest high of the last `lookback` bars
  inside bar   next bar's high <= mother high and low >= mother low, and its
               range is at most `max_ratio` of the mother's range ("small")
  entry        sell stop at inside-bar low, live for `valid` bars after the
               inside bar; cancelled if price trades above the mother high first
  stop         mother high + `buf` (fraction of price)
  target       entry - `rr` x risk
  fills        a bar that touches both stop and target is scored as a loss
  cost         `cost_bp` basis points of price per round turn, charged in R

Usage: python3 scripts/swing_inside_short.py <bars.json> [label]
"""
from __future__ import annotations
import json, random, sys, statistics as st


def signals(b, lookback, max_ratio):
    """Indices i where bar i is the mother and bar i+1 is the inside bar."""
    out = []
    for i in range(lookback, len(b) - 1):
        m, x = b[i], b[i + 1]
        if m["h"] < max(y["h"] for y in b[i - lookback + 1:i + 1]):
            continue
        mr = m["h"] - m["l"]
        if mr <= 0:
            continue
        if x["h"] > m["h"] or x["l"] < m["l"]:
            continue
        if (x["h"] - x["l"]) > max_ratio * mr:
            continue
        out.append(i)
    return out


def trade(b, i, valid, rr, buf, cost_bp, entry_override=None):
    """Simulate one setup. Returns R result or None if never triggered."""
    m, x = b[i], b[i + 1]
    stop = m["h"] * (1 + buf)
    entry = x["l"] if entry_override is None else entry_override
    risk = stop - entry
    if risk <= 0:
        return None
    tgt = entry - rr * risk
    k = i + 2
    filled = None
    while k < len(b) and k <= i + 1 + valid:
        y = b[k]
        if y["h"] > m["h"] and y["l"] > entry:        # invalidated before trigger
            return None
        if y["l"] <= entry:
            filled = k
            break
        k += 1
    if filled is None:
        return None
    y = b[filled]
    fill = min(entry, y["o"])                          # gap-down opens fill lower
    risk_f = stop - fill
    tgt = fill - rr * risk_f
    cost_r = fill * cost_bp / 1e4 / risk_f
    # fill bar: if it also reached the stop, assume the stop came first
    if y["h"] >= stop:
        return -1 - cost_r
    if y["l"] <= tgt:
        return rr - cost_r
    for y in b[filled + 1:]:
        if y["h"] >= stop:
            return -1 - cost_r
        if y["l"] <= tgt:
            return rr - cost_r
    return None                                        # still open at data end


def stats(rs):
    if not rs:
        return dict(n=0, win=0, pf=0, exp=0, tot=0, dd=0)
    w = [r for r in rs if r > 0]
    l = [-r for r in rs if r <= 0]
    eq = pk = dd = 0
    for r in rs:
        eq += r; pk = max(pk, eq); dd = max(dd, pk - eq)
    return dict(n=len(rs), win=100 * len(w) / len(rs),
                pf=(sum(w) / sum(l)) if l else float("inf"),
                exp=st.mean(rs), tot=sum(rs), dd=dd)


def run(b, lookback=10, max_ratio=0.6, valid=3, rr=2.0, buf=0.0003, cost_bp=1.0):
    rs = []
    last_exit = -1
    for i in signals(b, lookback, max_ratio):
        if i <= last_exit:                              # one position at a time
            continue
        r = trade(b, i, valid, rr, buf, cost_bp)
        if r is not None:
            rs.append(r)
            last_exit = i + 1
    return rs


def control(b, n, rr, buf, cost_bp, draws=200, seed=7):
    """Same stop/target geometry, mother bar chosen at random instead of by rule."""
    rng = random.Random(seed)
    idx = list(range(20, len(b) - 3))
    exps = []
    for _ in range(draws):
        rs = []
        for i in rng.sample(idx, min(n * 3, len(idx))):
            # short from the next bar's low with a stop at this bar's high: same shape
            r = trade(b, i, 3, rr, buf, cost_bp)
            if r is not None:
                rs.append(r)
            if len(rs) == n:
                break
        if rs:
            exps.append(st.mean(rs))
    return exps


def fmt(s):
    return (f"{s['n']:>4} trades  win {s['win']:5.1f}%  PF {s['pf']:5.2f}  "
            f"exp {s['exp']:+.3f}R  total {s['tot']:+6.1f}R  maxDD {s['dd']:5.1f}R")


if __name__ == "__main__":
    b = json.load(open(sys.argv[1]))
    label = sys.argv[2] if len(sys.argv) > 2 else sys.argv[1]
    print(f"== {label}: {len(b)} bars ==")
    base = dict(lookback=10, max_ratio=0.6, valid=3, rr=2.0, buf=0.0003, cost_bp=1.0)
    s = stats(run(b, **base))
    print("default   ", fmt(s))
    ctl = control(b, max(s["n"], 5), base["rr"], base["buf"], base["cost_bp"])
    if ctl and s["n"]:
        pct = 100 * sum(e < s["exp"] for e in ctl) / len(ctl)
        print(f"random-mother control: median exp {st.median(ctl):+.3f}R, "
              f"strategy sits at the {pct:.0f}th percentile of {len(ctl)} draws")
    print("-- swing lookback (bars) --")
    for lb in (5, 10, 20, 50, 100):
        print(f"  {lb:>3}    ", fmt(stats(run(b, **{**base, 'lookback': lb}))))
    print("-- inside bar size, max fraction of mother range --")
    for mr in (0.3, 0.5, 0.6, 0.8, 1.0):
        print(f"  {mr:>4}   ", fmt(stats(run(b, **{**base, 'max_ratio': mr}))))
    print("-- reward:risk --")
    for rr in (1.0, 1.5, 2.0, 3.0):
        print(f"  1:{rr:<4} ", fmt(stats(run(b, **{**base, 'rr': rr}))))
    print("-- round-turn cost (bp) --")
    for c in (0.0, 1.0, 2.0, 5.0):
        print(f"  {c:>4}   ", fmt(stats(run(b, **{**base, 'cost_bp': c}))))
    half = len(b) // 2
    print("-- time split --")
    print("  1st half", fmt(stats(run(b[:half], **base))))
    print("  2nd half", fmt(stats(run(b[half:], **base))))
