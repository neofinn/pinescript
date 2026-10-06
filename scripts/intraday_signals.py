"""The pre-registered signal universe. Fixed before any of it was run.

Chosen because each has prior support in intraday trading rather than because
it looked good on this data -- that ordering is what makes the search a test
instead of a fishing trip. Retail staples and desk-flavoured ideas are both
here, and they are judged the same way.

Every signal returns a list in {-1, 0, 1} aligned to the bars, and NONE of them
reads a value the bar had not already produced: `i` may use data up to and
including bar i, never i+1. Execution then enters at bar i+1's open.
"""
from __future__ import annotations


def _blank(n): return [0] * n


# ── mean reversion ────────────────────────────────────────────────────────
def rsi2_reversion(x, lo=10, hi=90):
    """Connors' RSI(2). The canonical short-horizon reversion signal."""
    s, r = _blank(x["n"]), x["rsi2"]
    for i in range(x["n"]):
        if r[i] is None: continue
        if r[i] < lo: s[i] = 1
        elif r[i] > hi: s[i] = -1
    return s


def bollinger_reversion(x, k=2.0):
    s, c, m, sd = _blank(x["n"]), x["c"], x["sma20"], x["sd20"]
    for i in range(x["n"]):
        if m[i] is None or not sd[i]: continue
        if c[i] < m[i] - k * sd[i]: s[i] = 1
        elif c[i] > m[i] + k * sd[i]: s[i] = -1
    return s


def vwap_reversion(x, k=1.5):
    """Price stretched from session VWAP. Desks execute toward VWAP, which is
    the mechanism usually claimed for a pull back to it."""
    s, c, vw, atr = _blank(x["n"]), x["c"], x["vwap"], x["atr"]
    for i in range(x["n"]):
        if vw[i] is None or not atr[i]: continue
        d = (c[i] - vw[i]) / atr[i]
        if d < -k: s[i] = 1
        elif d > k: s[i] = -1
    return s


def range_position(x, lo=0.05, hi=0.95):
    s, c, hh, ll = _blank(x["n"]), x["c"], x["hh20"], x["ll20"]
    for i in range(x["n"]):
        if hh[i] is None or hh[i] <= ll[i]: continue
        p = (c[i] - ll[i]) / (hh[i] - ll[i])
        if p < lo: s[i] = 1
        elif p > hi: s[i] = -1
    return s


# ── momentum / breakout ───────────────────────────────────────────────────
def channel_breakout(x):
    s, c, hh, ll = _blank(x["n"]), x["c"], x["hh20"], x["ll20"]
    for i in range(1, x["n"]):
        if hh[i-1] is None: continue
        if c[i] > hh[i-1]: s[i] = 1
        elif c[i] < ll[i-1]: s[i] = -1
    return s


def opening_range_breakout(x):
    """First 30 minutes' range, broken later in the day."""
    s, c, oh, ol = _blank(x["n"]), x["c"], x["or_hi"], x["or_lo"]
    for i in range(x["n"]):
        if oh[i] is None: continue
        if c[i] > oh[i]: s[i] = 1
        elif c[i] < ol[i]: s[i] = -1
    return s


def initial_balance_breakout(x):
    """First hour's range -- the Market Profile initial balance."""
    s, c, ih, il = _blank(x["n"]), x["c"], x["ib_hi"], x["ib_lo"]
    for i in range(x["n"]):
        if ih[i] is None: continue
        if c[i] > ih[i]: s[i] = 1
        elif c[i] < il[i]: s[i] = -1
    return s


def ema_cross(x):
    s, f, sl = _blank(x["n"]), x["ema9"], x["ema21"]
    for i in range(1, x["n"]):
        if f[i-1] <= sl[i-1] and f[i] > sl[i]: s[i] = 1
        elif f[i-1] >= sl[i-1] and f[i] < sl[i]: s[i] = -1
    return s


def momentum_atr(x, k=1.0, look=6):
    s, c, atr = _blank(x["n"]), x["c"], x["atr"]
    for i in range(look, x["n"]):
        if not atr[i]: continue
        d = (c[i] - c[i-look]) / atr[i]
        if d > k: s[i] = 1
        elif d < -k: s[i] = -1
    return s


def vwap_cross(x):
    s, c, vw = _blank(x["n"]), x["c"], x["vwap"]
    for i in range(1, x["n"]):
        if vw[i] is None or vw[i-1] is None: continue
        if c[i-1] <= vw[i-1] and c[i] > vw[i]: s[i] = 1
        elif c[i-1] >= vw[i-1] and c[i] < vw[i]: s[i] = -1
    return s


# ── flow-flavoured ────────────────────────────────────────────────────────
def volume_thrust(x, mult=2.5):
    """A bar on unusual volume, taken in its own direction."""
    s, v, av, bars = _blank(x["n"]), x["v"], x["vol20"], x["bars"]
    for i in range(x["n"]):
        if not av[i] or v[i] < av[i] * mult: continue
        b = bars[i]
        if b["c"] > b["o"]: s[i] = 1
        elif b["c"] < b["o"]: s[i] = -1
    return s


def volume_climax_fade(x, mult=3.0):
    """Unusual volume faded instead -- exhaustion rather than thrust."""
    s = volume_thrust(x, mult)
    return [-v for v in s]


def gap_fade(x, k=0.5):
    """Session opens away from yesterday's close and is faded."""
    s, bars, atr, si = _blank(x["n"]), x["bars"], x["atr"], x["ses_i"]
    for i in range(1, x["n"]):
        if si[i] != 0 or not atr[i-1]: continue
        g = (bars[i]["o"] - bars[i-1]["c"]) / atr[i-1]
        if g > k: s[i] = -1
        elif g < -k: s[i] = 1
    return s


def first_bar_continuation(x):
    """Direction of the session's first bar, taken on the second."""
    s, bars, si = _blank(x["n"]), x["bars"], x["ses_i"]
    for i in range(x["n"]):
        if si[i] != 1: continue
        b = bars[i-1]
        if b["c"] > b["o"]: s[i] = 1
        elif b["c"] < b["o"]: s[i] = -1
    return s


SIGNALS = {
    "rsi2 reversion":       rsi2_reversion,
    "bollinger reversion":  bollinger_reversion,
    "vwap reversion":       vwap_reversion,
    "range position":       range_position,
    "channel breakout":     channel_breakout,
    "opening range break":  opening_range_breakout,
    "initial balance break": initial_balance_breakout,
    "ema 9/21 cross":       ema_cross,
    "momentum vs atr":      momentum_atr,
    "vwap cross":           vwap_cross,
    "volume thrust":        volume_thrust,
    "volume climax fade":   volume_climax_fade,
    "gap fade":             gap_fade,
    "first bar continue":   first_bar_continuation,
}

# ── filters: not signals, they only gate one ──────────────────────────────
def f_none(x, i): return True
def f_trend_up(x, i): return x["c"][i] > x["ema50"][i]
def f_with_trend(x, i, s): return (s > 0) == (x["c"][i] > x["ema50"][i])
def f_counter_trend(x, i, s): return (s > 0) != (x["c"][i] > x["ema50"][i])
def f_high_vol(x, i):
    a = x["atr"][i]
    return bool(a) and a > (x["c"][i] * 0.0015)
def f_rel_vol(x, i):
    return bool(x["vol20"][i]) and x["v"][i] > x["vol20"][i] * 1.2
def f_first_hour(x, i): return x["ses_i"][i] < 12
def f_after_first_hour(x, i): return x["ses_i"][i] >= 12
def f_not_last_30(x, i): return x["ses_i"][i] < 72

FILTERS = {
    "none":            (f_none, False),
    "with trend":      (f_with_trend, True),
    "counter trend":   (f_counter_trend, True),
    "high volatility": (f_high_vol, False),
    "rel volume >1.2": (f_rel_vol, False),
    "first hour only": (f_first_hour, False),
    "after first hour": (f_after_first_hour, False),
    "not last 30min":  (f_not_last_30, False),
}
