"""Volume profile from OHLCV bars, and the honest label for what that is.

A REAL volume profile is built from trades: every print lands at one price, and
the histogram is exact. Nothing in an OHLCV feed carries that. What can be
built is volume-BY-price under an assumption about how a bar's volume was
distributed across its own range, and that assumption is the whole error term:

  * uniform spread  -- a bar's volume is smeared evenly from low to high. This
    is what TradingView's own Volume Profile does when it has no tick data, so
    it is the right default if the goal is to reproduce what the user sees.
  * close-weighted   -- all of a bar's volume at its close. Cheap, and wrong in
    a specific way: it invents a spike at whatever price the clock happened to
    stop on.

The finer the bar, the smaller the assumption matters, which is measurable:
build the same session from 1-minute bars and from 5-minute bars and compare
the POC. `calibrate()` in the test harness does exactly that, and the answer is
reported rather than assumed.

Everything here is CAUSAL by construction. A developing profile at bar i is
built from bars [session_start .. i] and never from the session's later bars;
prior-session levels are complete only because that session has closed. A
profile that peeks at the rest of the day is the most common way this indicator
gets backtested into looking predictive.
"""
from __future__ import annotations
import datetime as dt


def bin_edges(lo: float, hi: float, nbins: int) -> tuple[float, float]:
    """Return (base, width) for a histogram of nbins over [lo, hi]."""
    if hi <= lo:
        hi = lo + 1e-9
    return lo, (hi - lo) / nbins


def add_bar(hist: list[float], base: float, width: float, bar: dict,
            mode: str = "uniform") -> None:
    """Distribute one bar's volume into the histogram, in place.

    Uniform spread weights each bin by how much of the bar's range falls in it,
    so a bar that straddles a bin boundary is split in proportion -- not pushed
    whole into whichever bin its midpoint lands in.
    """
    v = bar["v"] or 0
    if v <= 0 or width <= 0:
        return
    n = len(hist)
    if mode == "close":
        k = min(n - 1, max(0, int((bar["c"] - base) / width)))
        hist[k] += v
        return
    lo, hi = bar["l"], bar["h"]
    if hi <= lo:
        k = min(n - 1, max(0, int((bar["c"] - base) / width)))
        hist[k] += v
        return
    a = max(0, min(n - 1, int((lo - base) / width)))
    b = max(0, min(n - 1, int((hi - base) / width)))
    span = hi - lo
    placed = 0.0
    for k in range(a, b + 1):
        s, e = base + k * width, base + (k + 1) * width
        overlap = min(hi, e) - max(lo, s)
        if overlap > 0:
            share = v * overlap / span
            hist[k] += share
            placed += share
    # Whatever traded outside the grid goes to the edge row nearest it, split
    # by how much of the bar fell off each end. Clamping the row INDEX without
    # this drops that volume silently -- the profile still draws, the rows are
    # simply too light, and nothing in the output says so. build() picks the
    # grid from the bars themselves so it never overflows, but add_bar is
    # callable against a fixed grid and then it does.
    left = max(0.0, (base - lo)) / span * v
    right = max(0.0, (hi - (base + n * width))) / span * v
    if left > 0:
        hist[0] += left
    if right > 0:
        hist[n - 1] += right


def value_area(hist: list[float], pct: float = 0.70) -> tuple[int, int, int]:
    """Market Profile value area: expand from the POC, taking the heavier side.

    Returns (poc_index, low_index, high_index). The pairwise expansion is the
    CBOT rule -- compare the two bins above against the two below and take the
    larger pair -- which is why the value area is usually asymmetric about the
    POC and cannot be replaced by a standard deviation.
    """
    n = len(hist)
    if n == 0:
        return 0, 0, 0
    total = sum(hist)
    poc = max(range(n), key=lambda i: hist[i])
    if total <= 0:
        return poc, poc, poc
    lo = hi = poc
    acc = hist[poc]
    target = total * pct
    while acc < target and (lo > 0 or hi < n - 1):
        up = hist[hi + 1] + (hist[hi + 2] if hi + 2 < n else 0) if hi < n - 1 else -1
        dn = hist[lo - 1] + (hist[lo - 2] if lo - 2 >= 0 else 0) if lo > 0 else -1
        if up >= dn and hi < n - 1:
            step = min(2, n - 1 - hi)
            for _ in range(step):
                hi += 1
                acc += hist[hi]
        elif lo > 0:
            step = min(2, lo)
            for _ in range(step):
                lo -= 1
                acc += hist[lo]
        else:
            break
    return poc, lo, hi


def nodes(hist: list[float], base: float, width: float, k: float = 1.5):
    """High- and low-volume nodes: local extrema against the mean bin.

    An HVN is price the market kept coming back to (acceptance); an LVN is
    price it passed through (rejection). Both are defined here against the
    profile's OWN mean, so a quiet session does not simply have no nodes.
    """
    n = len(hist)
    if n < 3:
        return [], []
    mean = sum(hist) / n
    hv, lv = [], []
    for i in range(1, n - 1):
        px = base + (i + 0.5) * width
        if hist[i] > mean * k and hist[i] >= hist[i - 1] and hist[i] >= hist[i + 1]:
            hv.append(px)
        if hist[i] < mean / k and hist[i] <= hist[i - 1] and hist[i] <= hist[i + 1]:
            lv.append(px)
    return hv, lv


def build(bars: list[dict], nbins: int = 60, mode: str = "uniform",
          va_pct: float = 0.70) -> dict:
    """Complete profile for a finished set of bars."""
    if not bars:
        return {}
    lo = min(b["l"] for b in bars)
    hi = max(b["h"] for b in bars)
    base, width = bin_edges(lo, hi, nbins)
    hist = [0.0] * nbins
    for b in bars:
        add_bar(hist, base, width, b, mode)
    poc_i, lo_i, hi_i = value_area(hist, va_pct)
    hv, lv = nodes(hist, base, width)
    return dict(hist=hist, base=base, width=width, lo=lo, hi=hi,
                poc=base + (poc_i + 0.5) * width,
                val=base + lo_i * width,
                vah=base + (hi_i + 1) * width,
                hvn=hv, lvn=lv, volume=sum(hist))


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


def developing(bars, nbins=60, mode="uniform", va_pct=0.70, min_bars=6):
    """Per-bar developing profile: POC/VAH/VAL as they stood AT each bar.

    The histogram is rebuilt when the session's range expands, because the bin
    grid is anchored to that range -- a new high re-bins everything. That is
    the real behaviour of a developing profile and it is why the level moves
    even on bars that add little volume.

    min_bars suppresses the first few bars of a session, where a "value area"
    over two candles is a number without a meaning.
    """
    n = len(bars)
    poc = [None] * n; vah = [None] * n; val = [None] * n
    for idxs in sessions_of(bars):
        lo = hi = None
        for k, i in enumerate(idxs):
            lo = bars[i]["l"] if lo is None else min(lo, bars[i]["l"])
            hi = bars[i]["h"] if hi is None else max(hi, bars[i]["h"])
            if k + 1 < min_bars:
                continue
            p = build([bars[j] for j in idxs[:k + 1]], nbins, mode, va_pct)
            poc[i], vah[i], val[i] = p["poc"], p["vah"], p["val"]
    return poc, vah, val


def prior_levels(bars, nbins=60, mode="uniform", va_pct=0.70):
    """Yesterday's completed profile, carried across today.

    Known at the open and fixed all day, so there is no question of leakage --
    which is exactly why these levels, not the developing ones, are the
    defensible thing to trade against.
    """
    n = len(bars)
    ppoc = [None] * n; pvah = [None] * n; pval = [None] * n
    prev = None
    for idxs in sessions_of(bars):
        if prev is not None:
            for i in idxs:
                ppoc[i], pvah[i], pval[i] = prev["poc"], prev["vah"], prev["val"]
        prev = build([bars[j] for j in idxs], nbins, mode, va_pct)
    return ppoc, pvah, pval


def naked_pocs(bars, nbins=60, mode="uniform", lookback=20):
    """Untouched POCs from earlier sessions, nearest-first at each bar.

    A POC stops being naked the moment price trades through it. Tracking that
    requires walking forward bar by bar; computing it from the finished series
    would mark levels as naked that today already cleared.
    """
    n = len(bars)
    out = [[] for _ in range(n)]
    pending = []          # list of (price, session_index)
    for sid, idxs in enumerate(sessions_of(bars)):
        for i in idxs:
            b = bars[i]
            pending = [p for p in pending if not (b["l"] <= p[0] <= b["h"])]
            out[i] = [p[0] for p in pending if sid - p[1] <= lookback]
        p = build([bars[j] for j in idxs], nbins, mode)
        if p:
            pending.append((p["poc"], sid))
    return out
