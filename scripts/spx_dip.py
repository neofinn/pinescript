"""Buying the S&P after a sharp decline: is it tradeable, and does it beat holding?

The forward-return statistic that motivated this (+281 bps over 30 days after a
2-sigma drop, against a +119 bps baseline) is not a strategy. It has no entry
rule, no exit, and its windows overlap, so its sample is far smaller than its
trade count suggests.

This turns it into something with an account attached, and changes the
benchmark. "Better than a random day" is the wrong bar -- you can always just
hold the index. The bar is buy-and-hold over the identical period.

Three things are enforced:

  * causal.  The z-score is known at the close; the trade opens at the NEXT
    bar's open. Nothing is bought at a price that was not yet available.
  * no overlap. One position at a time. A signal that fires while already long
    is ignored, which makes the trades independent and the statistics honest.
  * costs. Charged on entry and exit, in basis points.

The index is a price index, so dividends are excluded from the strategy and
from buy-and-hold alike. That keeps the comparison fair and understates both.
"""
from __future__ import annotations
import math, statistics


def zscore(xs, w):
    n = len(xs)
    z = [None] * n
    for i in range(w, n):
        seg = xs[i - w:i]
        mu = statistics.mean(seg)
        sd = statistics.pstdev(seg)
        z[i] = (xs[i] - mu) / sd if sd else 0.0
    return z


def run(bars, w=60, thr=-2.0, hold=30, cost_bps=2.0, stop_pct=None):
    """Long-only. Signal at close i, enter at open i+1, exit `hold` bars later."""
    c = [b["c"] for b in bars]
    o = [b["o"] for b in bars]
    lo = [b["l"] for b in bars]
    z = zscore(c, w)
    n = len(bars)
    trades, i = [], w
    while i < n - 1:
        if z[i] is not None and z[i] < thr:
            e_i = i + 1
            entry = o[e_i]
            x_i = min(n - 1, e_i + hold - 1)
            exit_px, reason = c[x_i], "time"
            if stop_pct is not None:
                sp = entry * (1 - stop_pct / 100.0)
                for j in range(e_i, x_i + 1):
                    if lo[j] <= sp:
                        exit_px, x_i, reason = sp, j, "stop"
                        break
            r = (exit_px / entry) - 1 - 2 * cost_bps / 10_000.0
            trades.append(dict(i_in=e_i, i_out=x_i, ret=r, reason=reason,
                               t=bars[e_i]["t"], bars=x_i - e_i + 1))
            i = x_i + 1
        else:
            i += 1
    return trades


def equity(trades, n_bars, start=100.0):
    """Compounded, flat between trades."""
    eq, peak, dd = start, start, 0.0
    curve = []
    for t in trades:
        eq *= (1 + t["ret"])
        peak = max(peak, eq)
        dd = max(dd, (peak - eq) / peak)
        curve.append(eq)
    return eq, dd, curve


def buyhold(bars, i0, i1, cost_bps=2.0):
    r = bars[i1]["c"] / bars[i0]["o"] - 1 - 2 * cost_bps / 10_000.0
    peak, dd = bars[i0]["o"], 0.0
    for j in range(i0, i1 + 1):
        peak = max(peak, bars[j]["h"])
        dd = max(dd, (peak - bars[j]["l"]) / peak)
    return r, dd


def summarise(trades, bars, cost_bps=2.0):
    if not trades:
        return None
    n = len(bars)
    i0, i1 = trades[0]["i_in"], trades[-1]["i_out"]
    years = (bars[i1]["t"] - bars[i0]["t"]) / (365.25 * 86400)
    eq, dd, _ = equity(trades, n)
    tot = eq / 100.0 - 1
    cagr = (eq / 100.0) ** (1 / years) - 1 if years > 0 else 0.0
    inmkt = sum(t["bars"] for t in trades) / (i1 - i0 + 1)
    bh_r, bh_dd = buyhold(bars, i0, i1, cost_bps)
    bh_cagr = (1 + bh_r) ** (1 / years) - 1 if years > 0 else 0.0
    rs = [t["ret"] for t in trades]
    sd = statistics.pstdev(rs) if len(rs) > 1 else 0.0
    # annualised Sharpe on the trade series, scaled by trades per year
    tpy = len(rs) / years if years else 0.0
    sharpe = (statistics.mean(rs) / sd * math.sqrt(tpy)) if sd else 0.0
    return dict(n=len(rs), years=years, tot=tot, cagr=cagr, dd=dd,
                inmkt=inmkt, bh=bh_r, bh_cagr=bh_cagr, bh_dd=bh_dd,
                sharpe=sharpe, avg=statistics.mean(rs),
                win=100.0 * sum(1 for r in rs if r > 0) / len(rs),
                # what the money earns per unit of time actually exposed
                cagr_exposed=(eq / 100.0) ** (1 / max(years * inmkt, 1e-9)) - 1)
