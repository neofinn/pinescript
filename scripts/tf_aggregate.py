"""Aggregate 5m bars to higher timeframes, session-aware.

Bucketing by wall-clock epoch is wrong for a 45-minute bar on a 375-minute
session: 375 does not divide by 45, so an epoch grid puts the session boundary
in the middle of a bar and silently merges the last candle of one day with the
first of the next. Buckets are therefore counted from each session's OWN first
bar, and the short final bar of a session is kept as a short bar rather than
being stitched onto tomorrow.

Volume carries through as a sum, which is what makes the synthetic traded-value
series usable at every timeframe from one construction.
"""
from __future__ import annotations
import datetime as dt


def sessions_of(bars):
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


def aggregate(bars, minutes, base_minutes=5):
    n = max(1, minutes // base_minutes)
    if n == 1:
        return list(bars)
    out = []
    for ses in sessions_of(bars):
        for k in range(0, len(ses), n):
            grp = ses[k:k + n]
            out.append(dict(t=grp[0]["t"], o=grp[0]["o"],
                            h=max(x["h"] for x in grp),
                            l=min(x["l"] for x in grp),
                            c=grp[-1]["c"],
                            v=sum(x["v"] or 0 for x in grp)))
    return out
