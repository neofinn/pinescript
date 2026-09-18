"""Pre-registered search over intraday signals. The protocol is the point.

Everything in this project so far has died the same death: test enough cells,
one comes back at p=0.05, and it is the one chance was always going to hand
you. So the universe of signals below is fixed BEFORE anything is run, the data
is split once, selection happens only on the in-sample half, and the
out-of-sample half is spent exactly once on the winner. Every count of cells
tested is reported, because a result without its denominator is not a result.

Two further guards, both learned the hard way earlier in this project:

  * ranking is by the MEDIAN across instruments, not the mean and not the best.
    A mean lets one instrument carry a strategy that does nothing on the other
    eleven, which is how a fitted cell disguises itself as an edge.
  * every signal runs through identical execution -- next-bar-open entry, the
    same ATR stop, the same R multiple, the same cost -- so a difference
    between two rows is a difference between two SIGNALS and nothing else.

Costs are in basis points because the basket spans XLF at 56 and gold at 4400,
and a flat cash cost would quietly make one of them untradeable.
"""
from __future__ import annotations
import datetime as dt
import math
import statistics


# ── primitives ────────────────────────────────────────────────────────────
def ema(vals, n):
    out, k = [0.0] * len(vals), 2.0 / (n + 1)
    e = vals[0]
    for i, v in enumerate(vals):
        e = v * k + e * (1 - k)
        out[i] = e
    return out


def rma(vals, n):
    out = [None] * len(vals)
    if len(vals) < n:
        return out
    out[n - 1] = sum(vals[:n]) / n
    for i in range(n, len(vals)):
        out[i] = (out[i - 1] * (n - 1) + vals[i]) / n
    return out


def true_range(bars):
    tr = []
    for i, b in enumerate(bars):
        tr.append(b["h"] - b["l"] if i == 0 else max(
            b["h"] - b["l"], abs(b["h"] - bars[i-1]["c"]), abs(b["l"] - bars[i-1]["c"])))
    return tr


def rsi(closes, n):
    out = [None] * len(closes)
    gains, losses = [0.0], [0.0]
    for i in range(1, len(closes)):
        d = closes[i] - closes[i-1]
        gains.append(max(d, 0.0)); losses.append(max(-d, 0.0))
    ag, al = rma(gains, n), rma(losses, n)
    for i in range(len(closes)):
        if ag[i] is None or al[i] is None:
            continue
        out[i] = 100.0 if al[i] == 0 else 100 - 100 / (1 + ag[i] / al[i])
    return out


def rolling(vals, n, fn):
    out = [None] * len(vals)
    for i in range(n - 1, len(vals)):
        out[i] = fn(vals[i - n + 1:i + 1])
    return out


def sessions_of(bars):
    out, cur, day = [], [], None
    for i, b in enumerate(bars):
        d = dt.datetime.utcfromtimestamp(b["t"]).date()
        if day is None or d != day:
            if cur:
                out.append(cur)
            cur, day = [], d
        cur.append(i)
    if cur:
        out.append(cur)
    return out


def context(bars):
    """Everything a signal might want, computed once per instrument."""
    c = [b["c"] for b in bars]
    h = [b["h"] for b in bars]
    l = [b["l"] for b in bars]
    v = [b["v"] or 0 for b in bars]
    n = len(bars)
    tr = true_range(bars)
    ctx = dict(bars=bars, c=c, h=h, l=l, v=v, n=n,
               atr=rma(tr, 14), rsi2=rsi(c, 2), rsi14=rsi(c, 14),
               ema9=ema(c, 9), ema21=ema(c, 21), ema50=ema(c, 50),
               ema200=ema(c, 200),
               sma20=rolling(c, 20, lambda w: sum(w) / len(w)),
               sd20=rolling(c, 20, lambda w: statistics.pstdev(w)),
               hh20=rolling(h, 20, max), ll20=rolling(l, 20, min),
               vol20=rolling(v, 20, lambda w: sum(w) / len(w)))
    # session-anchored VWAP and the bar's index within its session
    vwap = [None] * n
    ses_i = [0] * n
    ses_id = [0] * n
    ib_hi = [None] * n     # initial balance (first 12 bars ~ first hour on 5m)
    ib_lo = [None] * n
    or_hi = [None] * n     # opening range (first 6 bars ~ 30 min on 5m)
    or_lo = [None] * n
    for sid, idxs in enumerate(sessions_of(bars)):
        cpv = cv = 0.0
        hi6 = lo6 = hi12 = lo12 = None
        # reset per session: a truncated day must not inherit yesterday's
        # opening range, which would be a silent look-back across the gap
        hi6_f = lo6_f = hi12_f = lo12_f = None
        for k, i in enumerate(idxs):
            b = bars[i]
            src = (b["h"] + b["l"] + b["c"]) / 3.0
            cpv += src * (b["v"] or 0); cv += (b["v"] or 0)
            vwap[i] = cpv / cv if cv > 0 else None
            ses_i[i] = k
            ses_id[i] = sid
            hi6 = b["h"] if hi6 is None else max(hi6, b["h"])
            lo6 = b["l"] if lo6 is None else min(lo6, b["l"])
            if k >= 6 and hi6_f is not None:
                or_hi[i], or_lo[i] = hi6_f, lo6_f
            if k == 5:
                hi6_f, lo6_f = hi6, lo6
            hi12 = b["h"] if hi12 is None else max(hi12, b["h"])
            lo12 = b["l"] if lo12 is None else min(lo12, b["l"])
            if k == 11:
                hi12_f, lo12_f = hi12, lo12
            if k >= 12 and hi12_f is not None:
                ib_hi[i], ib_lo[i] = hi12_f, lo12_f
    ctx.update(vwap=vwap, ses_i=ses_i, ses_id=ses_id, ib_hi=ib_hi, ib_lo=ib_lo,
               or_hi=or_hi, or_lo=or_lo, n_sessions=len(sessions_of(bars)))
    return ctx


# ── execution: identical for every signal ─────────────────────────────────
def run(ctx, sig, *, stop_atr=0.75, rr=2.0, cost_bps=0.0, cost_abs=0.0,
        max_hold=60, lo=0, hi=None, tie='stop'):
    """sig[i] in {-1,0,1}. Entry next bar open, ATR stop, R-multiple target."""
    bars, atr, n = ctx["bars"], ctx["atr"], ctx["n"]
    hi = n if hi is None else hi
    ses = ctx["ses_id"]
    trades, pos, ambig = [], None, 0
    for i in range(lo, min(hi, n - 1)):
        if pos is not None:
            b = bars[i]
            s = pos["side"]
            hit_s = b["l"] <= pos["stop"] if s > 0 else b["h"] >= pos["stop"]
            hit_t = b["h"] >= pos["targ"] if s > 0 else b["l"] <= pos["targ"]
            px = None
            if hit_s and hit_t:
                # Both barriers inside one bar. OHLC cannot say which came
                # first, and the choice is not neutral: signals fire at
                # volatile moments, so they meet this case more often than
                # random entries do. Always taking the stop therefore
                # penalises signals relative to the random null, which is why
                # both readings get reported rather than one being picked.
                px = pos["stop"] if tie == "stop" else pos["targ"]
            elif hit_s:
                px = pos["stop"]
            elif hit_t:
                px = pos["targ"]
            elif i - pos["i"] >= max_hold or ses[i] != pos["ses"]:
                px = b["c"]
            if hit_s and hit_t:
                ambig += 1
            if px is not None:
                # Cost in CASH, not basis points. A flat bps charge across a
                # basket spanning XLF at 57 and gold at 4400 is not one
                # assumption, it is twelve different ones -- and at 2bps it was
                # ten times SPY's real penny spread, eating a third of the risk
                # budget and dragging every signal to the same dead band.
                cost = cost_abs + (pos["entry"] + px) * 0.5 * cost_bps / 10_000.0
                trades.append(s * (px - pos["entry"]) - cost)
                pos = None
        if pos is None and sig[i] != 0 and atr[i]:
            s = sig[i]
            e = bars[i + 1]["o"]
            r = atr[i] * stop_atr
            pos = dict(side=s, entry=e, stop=e - s * r, targ=e + s * r * rr,
                       i=i + 1, ses=ses[i + 1])
    return trades, ambig


def score(res):
    trades = res[0] if isinstance(res, tuple) else res
    if not trades:
        return dict(n=0, pf=0.0, win=0.0, net=0.0, med=0.0)
    w = sum(x for x in trades if x > 0)
    l = -sum(x for x in trades if x <= 0)
    return dict(n=len(trades), pf=(w / l) if l else float("inf"),
                win=sum(1 for x in trades if x > 0) / len(trades) * 100,
                net=sum(trades), med=statistics.median(trades))


# Round-trip cash cost per share/contract: one spread crossed each way, which
# is what a marketable order actually pays. Checked against typical quotes;
# widen them if your fills say otherwise.
COST = {"SPY": 0.01, "QQQ": 0.01, "IWM": 0.01, "DIA": 0.02,
        "XLF": 0.01, "XLE": 0.01, "GC=F": 0.20, "CL=F": 0.02,
        "NVDA": 0.02, "AAPL": 0.02, "TSLA": 0.03, "AMD": 0.05}
