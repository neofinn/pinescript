"""Volume-surge confluence, with the sample cost made visible.

A filter is only ever judged against a control matched to the TRADE COUNT IT
LEAVES. Cutting 300 trades to 40 raises the variance of the result, and a
higher profit factor on 40 trades is what that variance produces by itself --
this project measured random reaching PF 2.07 at n=33. So every row below
reports the trades remaining, and every control is run at the filtered n.

Two definitions of surge, because they are not the same question:

  naive             volume against the last N bars. Intraday volume is U-shaped
                    -- the first 5-minute bar of an SPY session carries about
                    nine times midday volume and the last carries twelve -- so
                    this partly measures the clock.
  session-adjusted  volume against the median for THAT position in the session,
                    built only from PRIOR sessions. Removes the clock and keeps
                    the surprise. This is the one that answers the question
                    asked.
"""
from __future__ import annotations
import statistics
from intraday_lab import sessions_of


def relvol_naive(bars, look=20):
    v=[x["v"] or 0 for x in bars]; out=[None]*len(bars)
    for i in range(look,len(bars)):
        a=sum(v[i-look:i])/look
        out[i]=v[i]/a if a>0 else None
    return out


def relvol_adjusted(bars, min_hist=3):
    """Per-session-position median from prior sessions only. Using the current
    session's own bars would leak information the bar did not have."""
    v=[x["v"] or 0 for x in bars]; out=[None]*len(bars); hist={}
    for idxs in sessions_of(bars):
        for k,i in enumerate(idxs):
            h=hist.get(k)
            if h and len(h)>=min_hist:
                m=statistics.median(h)
                out[i]=v[i]/m if m>0 else None
            hist.setdefault(k,[]).append(v[i])
    return out


def gate(sig, rv, thresh):
    """Keep only signals on a bar whose relative volume clears the threshold."""
    return [s if (s!=0 and rv[i] is not None and rv[i]>=thresh) else 0
            for i,s in enumerate(sig)]
