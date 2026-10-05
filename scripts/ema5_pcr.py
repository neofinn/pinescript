"""The 5 EMA setup, with a Put-Call Ratio filter. NIFTY and BANKNIFTY.

The 5 EMA rule as it is normally taught:

  SHORT   a candle forms entirely ABOVE the 5 EMA -- its LOW does not touch
          the average. Rest a sell-stop at that candle's LOW; the stop-loss is
          that candle's HIGH.
  LONG    a candle forms entirely BELOW the 5 EMA -- its HIGH does not touch.
          Rest a buy-stop at that candle's HIGH; stop-loss is its LOW.

The order sits pending. If another qualifying candle forms first, the order
moves to it. The thesis is that a candle detached from the average is
over-extended and will revert, so this is a MEAN-REVERSION setup, not a
breakout -- which matters, because every other pattern tested in this repo has
been a continuation one.

PCR here is real, not a proxy: it is rebuilt from NSE's own F&O bhavcopy as
sum(put open interest) / sum(call open interest). Two readings are carried,
near-expiry and all-expiry, because they differ and "PCR" rarely says which.
PCR is a DAILY number published after the close, so it is applied to the NEXT
session only -- using the same day's PCR intraday would be look-ahead.

Conventional reading: high PCR = more puts open = bearish positioning, which is
read as bullish (support below), and low PCR as bearish. The contrarian and
momentum readings are both tested rather than assumed.
"""
from __future__ import annotations
import datetime as dt, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from inside_bar_short import execute, stats                    # noqa: F401


def ema(xs, n):
    k = 2.0 / (n + 1)
    out, e = [None] * len(xs), None
    for i, x in enumerate(xs):
        e = x if e is None else (x - e) * k + e
        if i >= n - 1:
            out[i] = e
    return out


def arm_5ema(bars, side="short", ema_len=5, gap_atr=0.0, atr_list=None,
             allow=None):
    """Armed triggers for `execute`.

    gap_atr optionally requires the candle to be detached by at least this many
    ATR, not merely untouching -- "entirely above" by one tick is a weak claim.

    allow is an optional {date -> bool} gate, which is how the PCR filter is
    applied without entangling it with the price logic.
    """
    e = ema([b["c"] for b in bars], ema_len)
    n = len(bars)
    out = [None] * n
    for i in range(n):
        if e[i] is None:
            continue
        b = bars[i]
        if allow is not None:
            d = dt.datetime.utcfromtimestamp(b["t"]).date()
            if not allow.get(d, False):
                continue
        pad = (atr_list[i] or 0.0) * gap_atr if (gap_atr and atr_list) else 0.0
        if side == "short":
            if b["l"] <= e[i] + pad:
                continue
            trigger, stop = b["l"], b["h"]
        else:
            if b["h"] >= e[i] - pad:
                continue
            trigger, stop = b["h"], b["l"]
        out[i] = dict(i=i, trigger=trigger, inside_high=stop,
                      ref_high=stop, ref_low=trigger)
    return out


def run(bars, side="short", ema_len=5, rr=2.0, cost_bps=2.0, max_hold=24,
        valid_bars=1, gap_atr=0.0, atr_list=None, allow=None):
    a = arm_5ema(bars, side, ema_len, gap_atr, atr_list, allow)
    return execute(bars, a, rr=rr, stop_at="ref", valid_bars=valid_bars,
                   on_close=False, cost_bps=cost_bps, max_hold=max_hold,
                   side=side)


def load_pcr(path):
    """{symbol: {date: {...}}} from the bhavcopy-derived file."""
    import json
    raw = json.load(open(path))
    out = {}
    for k, v in raw.items():
        d = dt.date.fromisoformat(k)
        for sym, rec in v.items():
            out.setdefault(sym, {})[d] = rec
    return out


def pcr_gate(pcr_sym, field, lo=None, hi=None):
    """Yesterday's PCR decides today. Returns {date -> bool}.

    The shift by one session is the whole reason this is honest: the bhavcopy
    that PCR comes from is published after the close.
    """
    days = sorted(pcr_sym)
    gate = {}
    for a, b in zip(days, days[1:]):
        v = pcr_sym[a].get(field)
        if v is None:
            continue
        ok = True
        if lo is not None and v < lo: ok = False
        if hi is not None and v > hi: ok = False
        gate[b] = ok
    return gate
