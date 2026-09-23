"""Volume profile and orderflow, and nothing else.

No moving average, no RSI, no VWAP, no ATR, no session-time filter, no volume
surge. Every number in this file comes from one of exactly two places:

  THE PROFILE   where volume traded by price -- POC, value area, high- and
                low-volume nodes, naked POCs from earlier sessions.
  THE FLOW      which side was aggressing -- bar delta, imbalance, and
                cumulative session delta.

That constraint changes the EXIT, not just the entry, and this is the part
worth stating plainly. The earlier test in this repo put a 2.0 ATR stop and a
1.5R target on profile entries. ATR is a volatility model from outside the
profile; bolting it on means the result measures the pair, not the profile. A
profile trader does not size a stop in ATR -- the stop goes past the level that
was supposed to hold, and the target is the next level. So here:

  stop    one row beyond the structure the trade is leaning on
  target  the next profile level in the trade's direction
  flat    at the session close, because a developing profile does not survive
          the bell -- and that is a property of the profile, not a time filter

The scale unit everywhere is the VALUE AREA WIDTH, which is profile-derived,
rather than ATR, which is not.
"""
from __future__ import annotations
import datetime as dt

import volume_profile as vp


# ── the two state layers ─────────────────────────────────────────────────
def flow_state(bars):
    """Bar delta, imbalance, cumulative session delta, and its extremes.

    The tick rule again: a bar closing near its high is counted as buying. It
    tracks a 1-minute reconstruction at r = 0.68, so it is a proxy and a small
    reading is noise. cvd is reset each session because carrying it across the
    bell measures the calendar, not the auction.
    """
    n = len(bars)
    delta = [0.0] * n
    imb = [0.0] * n
    cvd = [0.0] * n
    cvd_hi = [0.0] * n
    cvd_lo = [0.0] * n
    px_hi = [0.0] * n
    px_lo = [0.0] * n
    for idxs in vp.sessions_of(bars):
        c = 0.0
        ch = cl = None
        ph = pl = None
        for i in idxs:
            b = bars[i]
            rng = b["h"] - b["l"]
            v = b["v"] or 0
            up = (b["c"] - b["l"]) / rng if rng > 0 else 0.5
            d = v * up - v * (1 - up)
            delta[i] = d
            imb[i] = d / v if v > 0 else 0.0
            c += d
            cvd[i] = c
            ch = c if ch is None else max(ch, c)
            cl = c if cl is None else min(cl, c)
            ph = b["h"] if ph is None else max(ph, b["h"])
            pl = b["l"] if pl is None else min(pl, b["l"])
            cvd_hi[i], cvd_lo[i] = ch, cl
            px_hi[i], px_lo[i] = ph, pl
    return dict(delta=delta, imb=imb, cvd=cvd, cvd_hi=cvd_hi, cvd_lo=cvd_lo,
                px_hi=px_hi, px_lo=px_lo)


def profile_state(bars, nbins=60, va_pct=0.70):
    """Developing and prior-session levels, nodes, naked POCs, row width."""
    n = len(bars)
    dpoc, dvah, dval = vp.developing(bars, nbins, va_pct=va_pct)
    ppoc, pvah, pval = vp.prior_levels(bars, nbins, va_pct=va_pct)
    npoc = vp.naked_pocs(bars, nbins)
    hvn = [[] for _ in range(n)]
    lvn = [[] for _ in range(n)]
    row = [None] * n
    prev = None
    for idxs in vp.sessions_of(bars):
        if prev is not None:
            for i in idxs:
                hvn[i], lvn[i], row[i] = prev
        p = vp.build([bars[j] for j in idxs], nbins, va_pct=va_pct)
        prev = (p.get("hvn", []), p.get("lvn", []), p.get("width"))
    return dict(dpoc=dpoc, dvah=dvah, dval=dval, ppoc=ppoc, pvah=pvah,
                pval=pval, npoc=npoc, hvn=hvn, lvn=lvn, row=row)


def state(bars, nbins=60, va_pct=0.70):
    s = profile_state(bars, nbins, va_pct)
    s.update(flow_state(bars))
    s["bars"] = bars
    s["n"] = len(bars)
    s["ses"] = [0] * len(bars)
    for k, idxs in enumerate(vp.sessions_of(bars)):
        for i in idxs:
            s["ses"][i] = k
    return s


# ── helpers, all profile-derived ─────────────────────────────────────────
def va_width(s, i):
    a, b = s["dvah"][i], s["dval"][i]
    return (a - b) if (a is not None and b is not None and a > b) else None


def nearest_above(levels, px):
    up = [p for p in levels if p > px]
    return min(up) if up else None


def nearest_below(levels, px):
    dn = [p for p in levels if p < px]
    return max(dn) if dn else None


# ── the five combined signals ────────────────────────────────────────────
# Each one needs BOTH layers to fire. A profile level alone does not trigger
# any of them, and neither does a flow reading alone. That is the point of the
# exercise -- if the pair carries nothing the price layer does not, these
# should look exactly like the profile-only versions already tested.
#
# Each returns (side, stop, target) or None. Entry is the next bar's open.

def absorption_at_edge(s, i):
    """Aggressive flow INTO a value-area edge that does not give way.

    Buyers lifting offers at the high while price closes back inside is the
    textbook absorption read: size is being taken and price is not paying for
    it. Needs both layers by construction -- the edge is the profile, the
    aggression is the flow.
    """
    b = s["bars"][i]
    vah, val, poc = s["dvah"][i], s["dval"][i], s["dpoc"][i]
    if vah is None or s["row"][i] is None:
        return None
    r = s["row"][i]
    if b["h"] >= vah and b["c"] < vah and s["imb"][i] > 0.15:
        return (-1, b["h"] + r, poc)
    if b["l"] <= val and b["c"] > val and s["imb"][i] < -0.15:
        return (1, b["l"] - r, poc)
    return None


def delta_breakout(s, i):
    """Value-area break with the flow behind it AND cvd at a session extreme.

    The cvd condition is what separates a break the auction is funding from a
    break that is one bar of noise poking out of the range.
    """
    b = s["bars"][i]
    vah, val = s["dvah"][i], s["dval"][i]
    if vah is None or s["row"][i] is None:
        return None
    r = s["row"][i]
    w = va_width(s, i)
    if w is None:
        return None
    if (b["c"] > vah and s["imb"][i] > 0 and s["cvd"][i] >= s["cvd_hi"][i]):
        tgt = nearest_above(s["npoc"][i] + s["hvn"][i], b["c"]) or (b["c"] + w)
        return (1, vah - r, tgt)
    if (b["c"] < val and s["imb"][i] < 0 and s["cvd"][i] <= s["cvd_lo"][i]):
        tgt = nearest_below(s["npoc"][i] + s["hvn"][i], b["c"]) or (b["c"] - w)
        return (-1, val + r, tgt)
    return None


def lvn_delta_traverse(s, i):
    """Crossing a thin price with flow in the same direction.

    Little volume traded there, so there is little resting interest to slow
    price down -- but only if someone is actually pushing, which is the flow
    half. Target is the next node that is NOT thin; stop is the far side of
    the gap just crossed.
    """
    if i == 0 or s["row"][i] is None:
        return None
    b, p = s["bars"][i], s["bars"][i - 1]
    r = s["row"][i]
    for lv in s["lvn"][i]:
        if p["c"] <= lv < b["c"] and s["imb"][i] > 0.10:
            tgt = nearest_above(s["hvn"][i], b["c"])
            if tgt:
                return (1, lv - r, tgt)
        if p["c"] >= lv > b["c"] and s["imb"][i] < -0.10:
            tgt = nearest_below(s["hvn"][i], b["c"])
            if tgt:
                return (-1, lv + r, tgt)
    return None


def cvd_divergence(s, i):
    """New session price extreme that the cumulative delta does not confirm.

    Price prints a new high, the flow behind it does not -- the move is being
    made by fewer and fewer aggressive buyers. Located at the profile's value
    edge so it is a divergence AT a level rather than anywhere on the chart.
    """
    b = s["bars"][i]
    vah, val, poc = s["dvah"][i], s["dval"][i], s["dpoc"][i]
    if vah is None or s["row"][i] is None or i == 0:
        return None
    r = s["row"][i]
    new_hi = b["h"] >= s["px_hi"][i] and s["ses"][i] == s["ses"][i - 1]
    new_lo = b["l"] <= s["px_lo"][i] and s["ses"][i] == s["ses"][i - 1]
    if new_hi and b["h"] >= vah and s["cvd"][i] < s["cvd_hi"][i - 1]:
        return (-1, b["h"] + r, poc)
    if new_lo and b["l"] <= val and s["cvd"][i] > s["cvd_lo"][i - 1]:
        return (1, b["l"] - r, poc)
    return None


def naked_poc_flow(s, i):
    """Flow pointing at an untouched POC from an earlier session.

    The magnet story needs someone pulling. Stop goes past the nearest node on
    the other side, so the trade is wrong when structure says it is wrong.
    """
    b = s["bars"][i]
    w = va_width(s, i)
    if w is None or not s["npoc"][i] or s["row"][i] is None:
        return None
    r = s["row"][i]
    p = min(s["npoc"][i], key=lambda q: abs(q - b["c"]))
    d = p - b["c"]
    if abs(d) < r or abs(d) > w:
        return None
    if d > 0 and s["imb"][i] > 0.10:
        stop = nearest_below(s["hvn"][i] + s["lvn"][i], b["c"])
        return (1, (stop - r) if stop else b["c"] - w * 0.5, p)
    if d < 0 and s["imb"][i] < -0.10:
        stop = nearest_above(s["hvn"][i] + s["lvn"][i], b["c"])
        return (-1, (stop + r) if stop else b["c"] + w * 0.5, p)
    return None


REGISTRY = {
    "absorption_at_edge": absorption_at_edge,
    "delta_breakout": delta_breakout,
    "lvn_delta_traverse": lvn_delta_traverse,
    "cvd_divergence": cvd_divergence,
    "naked_poc_flow": naked_poc_flow,
}
