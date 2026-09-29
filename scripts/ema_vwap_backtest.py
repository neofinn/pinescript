"""Backtest of ema_vwap_cross.pine, replicated block-for-block.

Tested on the UNDERLYING, not on options. That is deliberate: the reel buys
puts, but premium, theta and the bid-ask on an option sit on TOP of whatever
the signal is worth. If the signal has no directional edge in the underlying,
no option structure rescues it; if it does, the option overlay's cost is a
separate, already-measured question. So this isolates the signal.

Session VWAP is rebuilt per session from scratch -- cumulative sum(src*vol) /
sum(vol) reset at each new trading day -- because that is what "Anchor Period:
Session" means, and carrying it across days would quietly turn it into a
different indicator.
"""
from __future__ import annotations
import datetime as dt
import statistics


def to_sessions(bars):
    """Group bars into trading days by their UTC date."""
    out, cur, day = [], [], None
    for b in bars:
        d = dt.datetime.utcfromtimestamp(b["t"]).date()
        if day is None or d != day:
            if cur:
                out.append(cur)
            cur, day = [], d
        cur.append(b)
    if cur:
        out.append(cur)
    return out


def resample(bars, minutes):
    """Exact higher-timeframe bars, bucketed on wall-clock epoch."""
    span, out, cur, key = minutes * 60, [], None, None
    for b in bars:
        k = b["t"] - (b["t"] % span)
        if key is None or k != key:
            if cur:
                out.append(cur)
            key = k
            cur = dict(t=k, o=b["o"], h=b["h"], l=b["l"], c=b["c"], v=b["v"] or 0)
        else:
            cur["h"] = max(cur["h"], b["h"])
            cur["l"] = min(cur["l"], b["l"])
            cur["c"] = b["c"]
            cur["v"] += b["v"] or 0
    if cur:
        out.append(cur)
    return out


def ema_series(bars, n):
    out, k = [0.0] * len(bars), 2.0 / (n + 1)
    e = bars[0]["c"]
    for i, b in enumerate(bars):
        e = b["c"] * k + e * (1 - k)
        out[i] = e
    return out


def atr_series(bars, n=14):
    out, trs = [None] * len(bars), []
    for i, b in enumerate(bars):
        tr = b["h"] - b["l"] if i == 0 else max(
            b["h"] - b["l"], abs(b["h"] - bars[i-1]["c"]), abs(b["l"] - bars[i-1]["c"]))
        trs.append(tr)
        if i == n - 1:
            out[i] = sum(trs[:n]) / n
        elif i >= n:
            out[i] = (out[i-1] * (n-1) + tr) / n
    return out


def backtest(bars, *, ema_len=9, pen_ticks=1.0, tick=0.01, require_close=True,
             use_bias=True, allow_long=True, allow_short=True,
             exit_on_close=True, cost=0.02, use_stop=False, stop_atr=1.5,
             max_bars=0, flat_at_end=True):
    sessions = to_sessions(bars)
    em = ema_series(bars, ema_len)
    at = atr_series(bars, 14)
    pen = pen_ticks * tick

    trades = []
    pos = None
    idx = 0
    n_sig_l = n_sig_s = 0
    ex = dict(ema=0, stop=0, sess=0, time=0)

    for sess in sessions:
        cum_pv = cum_v = 0.0
        for j, b in enumerate(sess):
            i = idx + j
            src = (b["o"] + b["h"] + b["l"] + b["c"]) / 4.0
            v = b["v"] or 0
            cum_pv += src * v
            cum_v += v
            if cum_v <= 0:
                continue
            vw = cum_pv / cum_v
            e = em[i]
            last = (j == len(sess) - 1)

            # ── exits first: a position opened earlier is managed on this bar
            if pos is not None:
                s = pos["side"]
                px = None
                why = None
                if use_stop and pos["stop"] is not None:
                    hit = b["l"] <= pos["stop"] if s > 0 else b["h"] >= pos["stop"]
                    if hit:
                        px, why = pos["stop"], "stop"
                if px is None and max_bars and i - pos["bar"] >= max_bars:
                    px, why = b["c"], "time"
                if px is None:
                    brk = (b["c"] < e) if s > 0 else (b["c"] > e)
                    if not exit_on_close:
                        brk = (b["l"] < e) if s > 0 else (b["h"] > e)
                    if brk:
                        px, why = b["c"], "ema"
                if px is None and last and flat_at_end:
                    px, why = b["c"], "sess"
                if px is not None:
                    trades.append(dict(side=s, entry=pos["entry"], exit=px,
                                       net=s * (px - pos["entry"]) - cost,
                                       bars=i - pos["bar"], why=why))
                    ex[why] += 1
                    pos = None

            # ── entry: wick through VWAP, body back on its own side
            if pos is None and not last:
                bull = b["l"] < vw - pen and (not require_close or b["c"] > vw)
                bear = b["h"] > vw + pen and (not require_close or b["c"] < vw)
                bias_up = (not use_bias) or e > vw
                bias_dn = (not use_bias) or e < vw
                side = 0
                if bull and bias_up and allow_long:
                    side = 1; n_sig_l += 1
                elif bear and bias_dn and allow_short:
                    side = -1; n_sig_s += 1
                if side != 0 and j + 1 < len(sess):
                    entry = sess[j + 1]["o"]          # next bar open
                    a = at[i] or 0.0
                    st = None
                    if use_stop and a > 0:
                        st = (min(entry - a * stop_atr, entry - tick) if side > 0
                              else max(entry + a * stop_atr, entry + tick))
                    pos = dict(side=side, entry=entry, stop=st, bar=i + 1)
        idx += len(sess)
        if pos is not None:                 # never carry across sessions
            pos = None

    return dict(trades=trades, longs=n_sig_l, shorts=n_sig_s, exits=ex,
                sessions=len(sessions), bars=len(bars))


def stats(r):
    t = r["trades"]
    if not t:
        return dict(n=0, win=0.0, pf=0.0, net=0.0, med=0.0, bars=0.0)
    w = sum(x["net"] for x in t if x["net"] > 0)
    l = -sum(x["net"] for x in t if x["net"] <= 0)
    return dict(n=len(t), win=sum(1 for x in t if x["net"] > 0) / len(t) * 100,
                pf=(w / l) if l else float("inf"), net=sum(x["net"] for x in t),
                med=statistics.median(x["net"] for x in t),
                bars=statistics.mean(x["bars"] for x in t))
