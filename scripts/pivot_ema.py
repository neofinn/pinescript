"""Fibonacci pivot points with a 9 EMA, every combination. NIFTY.

Fibonacci pivots, from the PREVIOUS session's high, low and close:

    P  = (H + L + C) / 3
    R1 = P + 0.382 x (H - L)      S1 = P - 0.382 x (H - L)
    R2 = P + 0.618 x (H - L)      S2 = P - 0.618 x (H - L)
    R3 = P + 1.000 x (H - L)      S3 = P - 1.000 x (H - L)

A level is support or resistance depending on which side price is currently
on, so P is not permanently one or the other and is not treated as such here.

Two things a pivot can be traded as, and they are opposites:

    BOUNCE  price reaches the level and closes back away from it -- the level
            holds. Mean reversion.
    BREAK   price closes through the level -- the level fails. Continuation.

The 9 EMA enters three ways: ignored, as an alignment filter (longs only above
it, shorts only below), or deliberately inverted, because "trade with the EMA"
is an assumption worth testing rather than inheriting.

Everything is causal: pivots come from the previous session, the EMA from
closed bars, and entries are at the close of the bar that triggers.
"""
from __future__ import annotations
import datetime as dt

FIB = {"S3": -1.000, "S2": -0.618, "S1": -0.382, "P": 0.0,
       "R1": 0.382, "R2": 0.618, "R3": 1.000}
GROUPS = {"P": ["P"], "1": ["R1", "S1"], "2": ["R2", "S2"], "3": ["R3", "S3"]}


def fib_pivots(h, l, c):
    p = (h + l + c) / 3.0
    rng = h - l
    return {k: p + f * rng for k, f in FIB.items()}


def ema(xs, n):
    k = 2.0 / (n + 1)
    out, e = [None] * len(xs), None
    for i, x in enumerate(xs):
        e = x if e is None else (x - e) * k + e
        out[i] = e if i >= n - 1 else None
    return out


def atr(bars, n=14):
    out, trs = [None] * len(bars), []
    for i, b in enumerate(bars):
        p = bars[i - 1]["c"] if i else b["o"]
        trs.append(max(b["h"] - b["l"], abs(b["h"] - p), abs(b["l"] - p)))
        if i >= n:
            out[i] = sum(trs[i - n + 1:i + 1]) / n
    return out


def sessions(bars):
    out, cur, day = [], [], None
    for i, b in enumerate(bars):
        d = dt.datetime.utcfromtimestamp(b["t"]).date()
        if day is None or d != day:
            if cur:
                out.append((day, cur))
            cur, day = [], d
        cur.append(i)
    if cur:
        out.append((day, cur))
    return out


def run(bars, group="1", mode="bounce", ema_mode="none", ema_len=9,
        target="next", rr=2.0, stop_atr=0.5, cost_bps=2.0, one_per_day=True):
    """One combination. Returns the trade list."""
    e = ema([b["c"] for b in bars], ema_len)
    a = atr(bars)
    ses = sessions(bars)
    trades = []
    for k in range(1, len(ses)):
        _, pidx = ses[k - 1]
        _, idx = ses[k]
        if len(pidx) < 3 or len(idx) < 3:
            continue
        ph = max(bars[i]["h"] for i in pidx)
        pl = min(bars[i]["l"] for i in pidx)
        pc = bars[pidx[-1]]["c"]
        if ph <= pl:
            continue
        piv = fib_pivots(ph, pl, pc)
        ladder = sorted(piv.values())
        taken = False
        for n, i in enumerate(idx[1:], start=1):
            if taken and one_per_day:
                break
            b, prev = bars[i], bars[idx[n - 1]]
            if e[i] is None or a[i] is None:
                continue
            for name in GROUPS[group]:
                lv = piv[name]
                support = prev["c"] > lv          # which side we approach from
                if mode == "bounce":
                    if support and b["l"] <= lv and b["c"] > lv:
                        side = "long"
                    elif (not support) and b["h"] >= lv and b["c"] < lv:
                        side = "short"
                    else:
                        continue
                else:                              # break
                    if (not support) and b["c"] > lv and prev["c"] <= lv:
                        side = "long"
                    elif support and b["c"] < lv and prev["c"] >= lv:
                        side = "short"
                    else:
                        continue
                if ema_mode == "aligned":
                    if (side == "long") != (b["c"] > e[i]):
                        continue
                elif ema_mode == "counter":
                    if (side == "long") == (b["c"] > e[i]):
                        continue
                sgn = 1 if side == "long" else -1
                entry = b["c"]
                stop = lv - sgn * stop_atr * a[i]
                r = (entry - stop) * sgn
                if r <= 0:
                    continue
                if target == "next":
                    nxt = [x for x in ladder if (x > entry if sgn > 0 else x < entry)]
                    if not nxt:
                        continue
                    targ = min(nxt) if sgn > 0 else max(nxt)
                    if (targ - entry) * sgn <= 0:
                        continue
                else:
                    targ = entry + sgn * rr * r
                px = None
                for m in idx[n + 1:]:
                    x = bars[m]
                    hit_s = x["l"] <= stop if sgn > 0 else x["h"] >= stop
                    hit_t = x["h"] >= targ if sgn > 0 else x["l"] <= targ
                    if hit_s:
                        px = stop; break          # the loss wins an ambiguous bar
                    if hit_t:
                        px = targ; break
                if px is None:
                    px = bars[idx[-1]]["c"]
                net = (px - entry) * sgn - entry * cost_bps / 10_000.0
                trades.append(dict(r=net / r, side=side, level=name,
                                   t=b["t"], bar=n))
                taken = True
                break
    return trades


def stats(trades):
    if not trades:
        return dict(n=0, tot_r=0.0, avg_r=0.0, pf=0.0, win=0.0)
    rs = [t["r"] for t in trades]
    w = sum(r for r in rs if r > 0); l = -sum(r for r in rs if r <= 0)
    return dict(n=len(rs), tot_r=sum(rs), avg_r=sum(rs) / len(rs),
                pf=(w / l if l else 99.9),
                win=100.0 * sum(1 for r in rs if r > 0) / len(rs))
