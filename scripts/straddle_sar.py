"""Two-sided stop orders, stop-and-reverse. One live stop at all times.

The machine:

  FLAT      a buy-stop sits above and a sell-stop sits below.
  FILLED    whichever side fills is the position. The OPPOSITE order is not
            cancelled -- it becomes the protective stop, and it trails.
  STOPPED   when the trailing stop fills it does two jobs at once: it closes
            the position and opens the opposite one. A new stop is placed on
            the other side immediately, so there is always a live order
            waiting for the next move.

That is a stop-and-reverse (SAR) system, and it is always in the market after
the first fill. `sar=False` makes it go flat and re-arm the straddle instead,
which is the variant worth having because it is the one that can sit out a
range.

Fill realism, all pessimistic and all deliberate:

  * a stop order fills at its price, or at the bar's OPEN if the bar gapped
    past it. Never better.
  * costs are charged on every leg. A reversal is two legs -- closing and
    opening -- so a flip costs twice what an entry costs. This is the single
    biggest expense in any SAR system and it is not hidden here.
  * if, while flat, one bar spans BOTH entry levels, the order they filled in
    is unknowable from bar data. The pessimistic reading is taken: the trade
    against the bar's close direction fills first and is immediately stopped,
    then the position flips the other way. Those whipsaws are counted and
    reported separately so the assumption is auditable.

Levels are computed from bars strictly before the current one, so every order
price is knowable before the bar it fills on.
"""
from __future__ import annotations


def atr(bars, n=14):
    out = [None] * len(bars)
    trs = []
    for i, b in enumerate(bars):
        if i == 0:
            tr = b["h"] - b["l"]
        else:
            p = bars[i - 1]["c"]
            tr = max(b["h"] - b["l"], abs(b["h"] - p), abs(b["l"] - p))
        trs.append(tr)
        if i >= n:
            out[i] = sum(trs[i - n + 1:i + 1]) / n
    return out


def run(bars, entry_len=20, trail_len=10, trail="donchian", atr_mult=3.0,
        atr_len=14, cost_bps=1.0, sar=True, start_i=None,
        entry_pad=0.0, trail_delay=0.0, cost_abs=0.0, swap_per_bar=0.0):
    """Returns (trades, info). Each trade is one completed position.

    entry_pad     widens the INITIAL straddle: the buy-stop sits this many ATR
                  ABOVE the channel high and the sell-stop the same distance
                  below the channel low. 0 reproduces the plain channel break.
                  A wider straddle takes fewer, more committed breaks and pays
                  a worse entry price for each -- which of those dominates is
                  the experiment, not an assumption.
    trail_delay   the trail does not start until price has moved this many ATR
                  in favour. Until then the stop stays where it was first set.
                  This is the "give it room before managing it" knob.
    cost_abs      cost per leg in PRICE units, for instruments quoted with a
                  fixed spread (a retail XAUUSD spread is cents per ounce, not
                  basis points). Added to cost_bps rather than replacing it.
    swap_per_bar  financing charged per bar held, in price units. Negative is
                  a cost. Matters on a CFD held for days.
    """
    n = len(bars)
    a = atr(bars, atr_len)
    hi = [b["h"] for b in bars]
    lo = [b["l"] for b in bars]
    warm = max(entry_len, trail_len, atr_len) + 1
    i0 = start_i if start_i is not None else warm

    pos = 0                 # +1 long, -1 short, 0 flat
    entry = stop = 0.0
    ext = 0.0               # best price seen since entry
    trades, whip = [], 0
    cost = cost_bps / 10_000.0

    def book(exit_px, i, reason):
        gross = (exit_px - entry) * pos
        fees = (entry + exit_px) * cost + 2.0 * cost_abs
        carry = swap_per_bar * max(0, i - i_in)
        net = gross - fees + carry
        trades.append(dict(side=pos, entry=entry, exit=exit_px,
                           pnl=net, ret=net / entry, gross=gross, fees=fees,
                           i_in=i_in, i_out=i, reason=reason,
                           bars_held=max(1, i - i_in), t=bars[i_in]["t"]))

    i_in = i0
    for i in range(i0, n):
        b = bars[i]
        up = max(hi[i - entry_len:i])
        dn = min(lo[i - entry_len:i])

        if pos == 0:
            if entry_pad and a[i] is not None:
                up = up + entry_pad * a[i]
                dn = dn - entry_pad * a[i]
            hit_u = b["h"] >= up
            hit_d = b["l"] <= dn
            if hit_u and hit_d:
                whip += 1
                first = -1 if b["c"] >= b["o"] else 1   # the losing one fills first
                px1 = max(up, b["o"]) if first > 0 else min(dn, b["o"])
                px2 = min(dn, b["o"]) if first > 0 else max(up, b["o"])
                pos, entry, i_in = first, px1, i
                book(px2, i, "whipsaw")
                pos = -first
                entry, i_in = px2, i
                ext = b["h"] if pos > 0 else b["l"]
            elif hit_u:
                pos, entry, i_in = 1, max(up, b["o"]), i
                ext = b["h"]
            elif hit_d:
                pos, entry, i_in = -1, min(dn, b["o"]), i
                ext = b["l"]
            if pos != 0:
                stop = _stop(bars, i, pos, ext, lo, hi, trail, trail_len,
                             a, atr_mult)
            continue

        # in a position: the opposite stop order is live and trailing
        ext = max(ext, b["h"]) if pos > 0 else min(ext, b["l"])
        hit = (b["l"] <= stop) if pos > 0 else (b["h"] >= stop)
        if hit:
            px = min(stop, b["o"]) if pos > 0 else max(stop, b["o"])
            book(px, i, "stop")
            if sar:
                pos, entry, i_in = -pos, px, i
                ext = b["l"] if pos < 0 else b["h"]
                stop = _stop(bars, i, pos, ext, lo, hi, trail, trail_len,
                             a, atr_mult)
            else:
                pos = 0
        else:
            moved = (ext - entry) * pos
            room = trail_delay * (a[i] or 0.0)
            if moved >= room:          # only manage once it has earned the room
                s2 = _stop(bars, i, pos, ext, lo, hi, trail, trail_len,
                           a, atr_mult)
                stop = max(stop, s2) if pos > 0 else min(stop, s2)  # never loosens

    if pos != 0:
        book(bars[-1]["c"], n - 1, "eod")
    return trades, dict(whipsaws=whip, bars=n - i0)


def _stop(bars, i, pos, ext, lo, hi, trail, trail_len, a, atr_mult):
    if trail == "atr" and a[i] is not None:
        return ext - atr_mult * a[i] if pos > 0 else ext + atr_mult * a[i]
    j0 = max(0, i - trail_len + 1)
    return min(lo[j0:i + 1]) if pos > 0 else max(hi[j0:i + 1])


def equity(trades, risk_frac=None, start=1.0):
    """Compound the per-trade percentage moves. risk_frac=None means fully
    invested on every position, which is what an always-in SAR actually is."""
    eq, peak, dd = start, start, 0.0
    for t in trades:
        r = t["ret"] if risk_frac is None else risk_frac * t["ret"]
        eq *= (1 + r)
        peak = max(peak, eq)
        dd = max(dd, (peak - eq) / peak)
        if eq <= 0:
            return 0.0, 1.0
    return eq, dd


def summarise(trades, bars, info=None):
    if not trades:
        return None
    yrs = (bars[-1]["t"] - bars[0]["t"]) / (365.25 * 86400)
    eq, dd = equity(trades)
    rets = [t["ret"] for t in trades]
    w = sum(r for r in rets if r > 0)
    l = -sum(r for r in rets if r <= 0)
    hx = bars[-1]["c"] / bars[0]["c"]
    return dict(n=len(trades), years=yrs, final=eq,
                cagr=(eq ** (1 / yrs) - 1) * 100 if yrs > 0 and eq > 0 else -100.0,
                dd=dd * 100, pf=(w / l) if l else float("inf"),
                win=100.0 * sum(1 for r in rets if r > 0) / len(rets),
                avg=sum(rets) / len(rets) * 100,
                hold=hx, hold_cagr=(hx ** (1 / yrs) - 1) * 100 if yrs > 0 else 0.0,
                whip=(info or {}).get("whipsaws", 0))


def shuffle_bars(bars, rng):
    """The right control for a trend system: keep every bar's shape and the
    return distribution, destroy only the ORDER.

    A price-matched random control tests whether the entry level matters. It
    cannot test a trend follower, whose whole thesis is that moves persist.
    Shuffling bar-to-bar moves removes exactly that persistence and leaves
    everything else -- same volatility, same gaps, same bar anatomy, same
    number of bars. A system that only harvests serial correlation scores at
    chance here; one that beats the shuffle is finding something real.
    """
    n = len(bars)
    shp = []
    for i in range(1, n):
        p = bars[i - 1]["c"]
        b = bars[i]
        shp.append((b["o"] / p, b["h"] / p, b["l"] / p, b["c"] / p))
    rng.shuffle(shp)
    out = [dict(bars[0])]
    px = bars[0]["c"]
    for k, (ro, rh, rl, rc) in enumerate(shp, start=1):
        o, h, l, c = px * ro, px * rh, px * rl, px * rc
        h = max(h, o, c)
        l = min(l, o, c)
        out.append(dict(t=bars[k]["t"], o=o, h=h, l=l, c=c, v=bars[k].get("v", 0)))
        px = c
    return out
