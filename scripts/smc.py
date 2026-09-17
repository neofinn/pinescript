"""SMC / ICT components as SEPARATE signal generators, so each can be judged.

The reel lists five confluences stacked together: fair value gap, order block,
liquidity sweep, higher-timeframe bias, session filter. Stacked, they produce a
handful of trades on any retail-sized dataset, and this project has already
measured what that does -- one added filter took the wickless strategy from 77
trades to 33, where random noise reaches PF 2.07 one time in a hundred. A
five-way stack cannot be evaluated at all.

So each is built alone here, tested alone, and only combined afterwards if it
survives. That ordering is the whole point of the file.

Definitions are the standard ICT ones. Where a definition is ambiguous in
common use, the stricter reading is taken and the choice is noted, because a
loose definition is how a pattern comes to "appear everywhere".
"""
from __future__ import annotations


def swings(bars, left=2, right=2):
    """Confirmed swing highs/lows. They arrive `right` bars late, and that lag
    is correct rather than a defect -- a pivot is not knowable before it is
    confirmed, and letting it be known earlier is lookahead."""
    hi = [None] * len(bars)
    lo = [None] * len(bars)
    for i in range(left, len(bars) - right):
        h, l = bars[i]["h"], bars[i]["l"]
        if all(bars[j]["h"] <= h for j in range(i - left, i + right + 1) if j != i):
            hi[i + right] = h          # published only once confirmed
        if all(bars[j]["l"] >= l for j in range(i - left, i + right + 1) if j != i):
            lo[i + right] = l
    return hi, lo


def fvg(bars, atr, min_atr=0.0):
    """Fair value gap: a 3-bar imbalance the middle bar ran straight through.

    Bullish when bar i's low is above bar i-2's high -- the market skipped that
    band entirely. Reported on bar i, the bar that completes it, not on the
    impulse bar, which would be lookahead by one bar.
    """
    sig = [0] * len(bars)
    for i in range(2, len(bars)):
        a = atr[i]
        if a is None:
            continue
        gap_up = bars[i]["l"] - bars[i - 2]["h"]
        gap_dn = bars[i - 2]["l"] - bars[i]["h"]
        if gap_up > 0 and gap_up >= a * min_atr:
            sig[i] = 1
        elif gap_dn > 0 and gap_dn >= a * min_atr:
            sig[i] = -1
    return sig


def order_block(bars, atr, impulse_atr=1.0):
    """The last opposing candle before an impulsive move.

    'Impulsive' is the load-bearing word and it is usually left undefined. Here
    it means the next bar's body exceeds `impulse_atr` x ATR; without a
    threshold every alternation qualifies and order blocks appear everywhere.
    """
    sig = [0] * len(bars)
    for i in range(1, len(bars) - 1):
        a = atr[i]
        if a is None:
            continue
        nxt = bars[i + 1]
        body = abs(nxt["c"] - nxt["o"])
        if body < a * impulse_atr:
            continue
        down = bars[i]["c"] < bars[i]["o"]
        up = bars[i]["c"] > bars[i]["o"]
        if down and nxt["c"] > nxt["o"]:
            sig[i + 1] = 1            # bullish OB, published on the impulse bar
        elif up and nxt["c"] < nxt["o"]:
            sig[i + 1] = -1
    return sig


def liquidity_sweep(bars, hi, lo, lookback=20):
    """Price takes out a prior swing then closes back inside it.

    The close is what makes it a sweep rather than a break: trading through a
    level and staying there is a breakout, and it is the opposite trade.
    """
    sig = [0] * len(bars)
    last_hi = last_lo = None
    ages = {"h": 0, "l": 0}
    for i, b in enumerate(bars):
        if hi[i] is not None:
            last_hi, ages["h"] = hi[i], 0
        if lo[i] is not None:
            last_lo, ages["l"] = lo[i], 0
        ages["h"] += 1
        ages["l"] += 1
        if last_lo is not None and ages["l"] <= lookback:
            if b["l"] < last_lo and b["c"] > last_lo:
                sig[i] = 1            # swept the lows, closed back above
        if last_hi is not None and ages["h"] <= lookback and sig[i] == 0:
            if b["h"] > last_hi and b["c"] < last_hi:
                sig[i] = -1
    return sig


def htf_bias(bars, ema_len=50):
    """Crudest honest version: close against a slow EMA on the same series."""
    out, k = [0] * len(bars), 2.0 / (ema_len + 1)
    e = bars[0]["c"]
    for i, b in enumerate(bars):
        e = b["c"] * k + e * (1 - k)
        out[i] = 1 if b["c"] > e else -1
    return out


def session_filter(bars, start_h, end_h):
    """UTC hour window. Gold's London and New York hours, by default."""
    import datetime as dt
    out = [False] * len(bars)
    for i, b in enumerate(bars):
        h = dt.datetime.utcfromtimestamp(b["t"]).hour
        out[i] = (start_h <= h < end_h) if start_h <= end_h else (h >= start_h or h < end_h)
    return out
