"""Opening-range breakout on the first 30-minute candle. 1:2 reward:risk.

The rule as given: the first M30 candle of the session sets a range. A break of
its high goes long, a break of its low goes short, the stop is the other side
of that range, and the target is twice the risk.

Two things decide whether this is measured correctly, and both are easy to get
wrong:

  SESSIONS   "the first 30-minute candle" means the first candle of the
             REGULAR session, not the first bar of the UTC day. NQ trades
             nearly 24 hours, so its first UTC bar is an overnight bar with
             no relation to the open. Sessions here are resolved in each
             market's own local time with a real timezone database, so the
             daylight-saving shifts are handled rather than approximated.
  RISK       with the stop at the opposite side of the range, the risk IS the
             opening range. A wide opening range therefore means a wide stop
             and a distant target; a narrow one means both are close. The
             range width is not a free parameter, it is the instrument.

Fills: the break level, or the bar's OPEN when the bar gapped through it. A bar
touching both stop and target is scored a loss. Unresolved trades exit at the
session close.
"""
from __future__ import annotations
import datetime as dt
from zoneinfo import ZoneInfo

# symbol -> (timezone, session open, session close)
SESSION = {
    **{k: ("America/New_York", (9, 30), (16, 0)) for k in
       ("NQ","ES","YM","RTY","GC","CL","QQQ","NDX","IXIC","SPY","SPX",
        "AAPL","NVDA","TSLA","MSFT","AMZN")},
    "DAX":   ("Europe/Berlin", (9, 0), (17, 30)),
    "FTSE":  ("Europe/London", (8, 0), (16, 30)),
    "NIFTY": ("Asia/Kolkata", (9, 15), (15, 30)),
    "BANKNIFTY": ("Asia/Kolkata", (9, 15), (15, 30)),
}


def opening_ranges(bars, sym):
    """[(or_bar_index, [session bar indices after it])] per session."""
    tzname, (oh, om), (ch, cm) = SESSION[sym]
    tz = ZoneInfo(tzname)
    byday = {}
    for i, b in enumerate(bars):
        lt = dt.datetime.fromtimestamp(b["t"], tz)
        mins = lt.hour * 60 + lt.minute
        if not (oh * 60 + om <= mins < ch * 60 + cm):
            continue
        byday.setdefault(lt.date(), []).append((mins, i))
    out = []
    for d in sorted(byday):
        rows = sorted(byday[d])
        if len(rows) < 3:
            continue
        # the opening range is the FIRST bar of the regular session
        if rows[0][0] != oh * 60 + om:
            continue              # a late or truncated session, skipped
        out.append((rows[0][1], [i for _, i in rows[1:]]))
    return out


def run(bars, sym, rr=2.0, cost_bps=1.0, first_only=True, stop_mode="range",
        atr_mult=1.0, min_range_bps=0.0):
    """stop_mode 'range' puts the stop at the other side of the opening range,
    which is the rule as stated. 'half' halves that distance, which keeps the
    entry and target but risks less -- reported because the full range is a
    wide stop on a volatile open."""
    trades = []
    for or_i, rest in opening_ranges(bars, sym):
        ob = bars[or_i]
        hi, lo = ob["h"], ob["l"]
        rng = hi - lo
        if rng <= 0 or (min_range_bps and rng / ob["c"] * 10000 < min_range_bps):
            continue
        done = False
        for k, j in enumerate(rest):
            if done and first_only:
                break
            b = bars[j]
            up, dn = b["h"] >= hi, b["l"] <= lo
            if not (up or dn):
                continue
            side = ("long" if b["c"] >= b["o"] else "short") if (up and dn) \
                else ("long" if up else "short")
            sgn = 1 if side == "long" else -1
            level = hi if side == "long" else lo
            entry = max(level, b["o"]) if sgn > 0 else min(level, b["o"])
            stop = (lo if side == "long" else hi) if stop_mode == "range" else \
                   (entry - sgn * rng * 0.5)
            r = (entry - stop) * sgn
            if r <= 0:
                continue
            targ = entry + sgn * rr * r
            px = None
            for m in rest[k:]:
                x = bars[m]
                hit_s = x["l"] <= stop if sgn > 0 else x["h"] >= stop
                hit_t = x["h"] >= targ if sgn > 0 else x["l"] <= targ
                if hit_s:
                    px = stop; break          # the loss wins an ambiguous bar
                if hit_t:
                    px = targ; break
            if px is None:
                px = bars[rest[-1]]["c"]
            net = (px - entry) * sgn - entry * cost_bps / 10_000.0
            trades.append(dict(r=net / r, side=side, rng_bps=rng/ob["c"]*10000,
                               t=bars[j]["t"], bar=k))
            done = True
    return trades


def stats(trades):
    if not trades:
        return dict(n=0, tot_r=0.0, avg_r=0.0, pf=0.0, win=0.0)
    rs = [t["r"] for t in trades]
    w = sum(r for r in rs if r > 0); l = -sum(r for r in rs if r <= 0)
    return dict(n=len(rs), tot_r=sum(rs), avg_r=sum(rs)/len(rs),
                pf=(w/l if l else 99.9),
                win=100.0*sum(1 for r in rs if r > 0)/len(rs))
