"""Inside-bar breakdown at a high, on 30-minute candles. Short only.

The pattern, stated exactly as given:

  1. a candle makes the high
  2. a SMALL candle forms INSIDE it -- high below the high, low above the low
  3. when that inside candle's low is broken, go short

Four things in that description are underdetermined, so each is a parameter
rather than a silent choice, and each is swept:

  "the high"      a true all-time high almost never occurs inside a 60-day
                  window, so the reference is a new high over a LOOKBACK.
                  lookback=0 means the strict running maximum of the series.
  "small"         inside is necessary but not sufficient; size_max caps the
                  inside bar's range as a fraction of the reference bar's.
                  1.0 means "inside is enough".
  "once broken"   taken literally: a trade on the break of the low, not on a
                  close below it. That is the aggressive reading and it will
                  produce more trades and more failures than the close version,
                  which is also tested.
  staleness       a setup cannot wait forever. valid_bars is how many candles
                  the trigger stays live.

Fill assumptions, all of them pessimistic on purpose:

  * a stop-sell that gaps fills at the bar OPEN, not at the trigger price. This
    project measured 40-51% of option trades gapping through their stop; the
    same effect exists here and is now modelled rather than waved at.
  * a bar that touches both the stop and the target is scored a LOSS.
  * the entry bar's own high counts against the stop. It may have printed
    before the break, so this is stricter than reality, and it is the direction
    to be strict in.

`execute` is shared by the strategy and by every control, so a control differs
from the strategy in exactly one thing: which bars it fires on.
"""
from __future__ import annotations
import datetime as dt
import random


def aggregate(bars, minutes, base_minutes=5):
    """Session-aware, so a 30m bar never straddles a session boundary."""
    n = max(1, minutes // base_minutes)
    if n == 1:
        return list(bars)
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
    res = []
    for ses in out:
        for k in range(0, len(ses), n):
            g = ses[k:k + n]
            res.append(dict(t=g[0]["t"], o=g[0]["o"],
                            h=max(x["h"] for x in g), l=min(x["l"] for x in g),
                            c=g[-1]["c"], v=sum(x["v"] or 0 for x in g)))
    return res


def setups(bars, lookback=100, size_max=1.0, side="short",
           need_extreme=True, need_inside=True):
    """Index -> the inside-bar setup formed at that bar, or None.

    The reference bar must make a new extreme over the prior `lookback` bars,
    and the next bar must sit entirely inside it. Both are known when bar i
    closes, so the trigger that follows is causal.

    side="long" is the exact mirror: a new LOW, an inside bar, and a break of
    its HIGH. It exists to separate the pattern from the drift. If the short
    loses what the long makes, the pattern carries no information and the
    result is the market rising.

    need_extreme and need_inside switch the two halves of the pattern off
    independently, which is the only way to see which half does the work.
    """
    sgn = 1 if side == "short" else -1

    def ext(b):          # the edge the reference bar must break out to
        return b["h"] * sgn

    def trig(b):         # the price whose break arms the trade
        return b["l"] if sgn > 0 else b["h"]

    def stopside(b):     # the price the stop sits beyond
        return b["h"] if sgn > 0 else b["l"]

    n = len(bars)
    out = [None] * n
    start = max(2, lookback + 1)
    e = [ext(b) for b in bars]
    for i in range(start, n):
        ref = bars[i - 1]
        lo_j = max(0, i - 1 - lookback) if lookback else 0
        if i - 1 <= lo_j:
            continue
        if need_extreme and ext(ref) <= max(e[lo_j:i - 1]):
            continue
        cur = bars[i]
        rng_ref = ref["h"] - ref["l"]
        if rng_ref <= 0:
            continue
        if need_inside:
            if cur["h"] > ref["h"] or cur["l"] < ref["l"]:
                continue                   # not inside
            if (cur["h"] - cur["l"]) > size_max * rng_ref:
                continue                   # not small enough
        out[i] = dict(i=i, side=side, trigger=trig(cur),
                      inside_high=stopside(cur),
                      ref_high=stopside(ref), ref_low=trig(ref))
    return out


def execute(bars, armed_list, rr=2.0, stop_at="inside", valid_bars=3,
            on_close=False, cost_bps=1.0, max_hold=16, side="short",
            stop_mult=1.0):
    """Run a list of armed triggers through one short-only exit model.

    armed_list[i] is the setup armed at the CLOSE of bar i, or None. The
    strategy passes real setups; a control passes displaced or random ones.
    """
    sgn = 1 if side == "short" else -1
    n = len(bars)
    trades, pos, armed = [], None, []
    for i in range(n):
        b = bars[i]
        if pos is not None:
            px = None
            stop_hit = b["h"] >= pos["stop"] if sgn > 0 else b["l"] <= pos["stop"]
            targ_hit = b["l"] <= pos["targ"] if sgn > 0 else b["h"] >= pos["targ"]
            if stop_hit:
                px = pos["stop"]              # loss wins an ambiguous bar
            elif targ_hit:
                px = pos["targ"]
            elif i - pos["i"] >= max_hold:
                px = b["c"]
            if px is not None:
                gross = (pos["entry"] - px) * sgn
                cost = pos["entry"] * cost_bps / 10_000.0
                trades.append(dict(pnl=gross - cost, r=(gross - cost) / pos["risk"],
                                   i_in=pos["i"], i_out=i, risk=pos["risk"],
                                   entry=pos["entry"], t=bars[pos["i"]]["t"]))
                pos = None
        armed = [a for a in armed if i - a["i"] <= valid_bars]
        if pos is None:
            for k, a in enumerate(armed):
                if on_close:
                    fired = (b["c"] < a["trigger"]) if sgn > 0 else (b["c"] > a["trigger"])
                    entry = b["c"]
                elif sgn > 0:
                    fired = b["l"] <= a["trigger"]
                    entry = min(a["trigger"], b["o"])   # gap fills at the open
                else:
                    fired = b["h"] >= a["trigger"]
                    entry = max(a["trigger"], b["o"])
                if not fired:
                    continue
                if stop_at == "inside":
                    stop = a["inside_high"]
                elif stop_at == "ref":
                    stop = a["ref_high"]
                else:                       # a multiple of the reference range
                    stop = entry + sgn * stop_mult * abs(a["ref_high"] - a["ref_low"])
                r = (stop - entry) * sgn
                if r <= 0:
                    continue
                pos = dict(entry=entry, stop=stop, targ=entry - sgn * rr * r,
                           risk=r, i=i)
                armed = []
                # the entry bar's own extreme still counts against the stop
                if (b["h"] >= stop) if sgn > 0 else (b["l"] <= stop):
                    gross = (entry - stop) * sgn
                    cost = entry * cost_bps / 10_000.0
                    trades.append(dict(pnl=gross - cost, r=(gross - cost) / r,
                                       i_in=i, i_out=i, risk=r, entry=entry,
                                       t=b["t"]))
                    pos = None
                break
        a = armed_list[i]
        if a is not None:
            armed.append(dict(a))
    return trades


def run(bars, lookback=100, size_max=1.0, side="short",
        need_extreme=True, need_inside=True, **kw):
    a = setups(bars, lookback, size_max, side, need_extreme, need_inside)
    return execute(bars, a, side=side, **kw)


def shifted(armed_list, offset):
    """Same setups, wrong bars -- the control that holds everything else fixed.

    Trigger prices move with their setup, so the stop distances, the trade
    count and the regime coverage are identical to the strategy's. Only the
    alignment between the setup and the price action is destroyed.
    """
    n = len(armed_list)
    out = [None] * n
    for i, a in enumerate(armed_list):
        if a is None:
            continue
        j = (i + offset) % n
        if out[j] is None:
            out[j] = dict(a, i=j)
    return out


def price_matched(bars, armed_list, rng):
    """Random bars, but each borrowed setup is re-priced to where it lands.

    A shifted setup carries absolute prices from months away, so on a trending
    market its trigger is unreachable and it never fires. This control keeps
    the setup's SHAPE -- trigger and stop as fractions of price -- and places
    it at a random bar, so it fires at the same rate the strategy does.
    """
    n = len(bars)
    live = [a for a in armed_list if a is not None]
    out = [None] * n
    for a in live:
        ref = bars[a["i"]]["c"]
        for _ in range(20):
            j = rng.randrange(2, n - 1)
            if out[j] is None:
                break
        else:
            continue
        p = bars[j]["c"]
        out[j] = dict(i=j,
                      trigger=p * a["trigger"] / ref,
                      inside_high=p * a["inside_high"] / ref,
                      ref_high=p * a["ref_high"] / ref,
                      ref_low=p * a["ref_low"] / ref)
    return out


def stats(trades):
    if not trades:
        return dict(n=0, tot_r=0.0, pf=0.0, win=0.0, avg_r=0.0)
    rs = [t["r"] for t in trades]
    w = sum(r for r in rs if r > 0)
    l = -sum(r for r in rs if r <= 0)
    return dict(n=len(rs), tot_r=sum(rs), pf=(w / l if l else float("inf")),
                win=100.0 * sum(1 for r in rs if r > 0) / len(rs),
                avg_r=sum(rs) / len(rs))
