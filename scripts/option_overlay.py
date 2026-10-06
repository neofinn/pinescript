"""Re-price each underlying trade as the option trade it would actually be.

There is no historical intraday option data here, so this is a MODEL -- but it
is calibrated to the real chain rather than invented: strike spacing, ATM
bid-ask and the expected move all come from CBOE quotes pulled today.

The IV solve is degenerate on a near-dated contract: only sigma*sqrt(T) is
pinned by the price, so 15.4% at one day and 8.4% at three days fit the same
quote identically. What is therefore carried forward is the EXPECTED MOVE, and
the annualised vol consistent with a one-day contract is used with a one-day
clock, which keeps the pair self-consistent.

The costs an option adds to a directional signal are all one-way:

  spread    paid on entry AND exit, and it is a percentage of PREMIUM, not of
            the underlying -- 1.1% of a $2.37 option, twice, is 2.2% of the
            position before anything moves.
  theta     charged for the whole hold regardless of outcome, and on a 0DTE it
            is charged against a life measured in hours.
  convexity cuts both ways: it pays for the big moves and it is exactly what
            you are being charged for in premium.
"""
from __future__ import annotations
import math, statistics
from hft.pricing import bs_call, bs_put, bs_delta_call

MIN_Y = 1.0 / (365.0 * 24.0 * 60.0)      # one minute, in years


def contract_for(spot: float, step: float, is_call: bool, offset: int = 0):
    """Nearest listed strike, optionally N strikes out of the money."""
    atm = round(spot / step) * step
    return atm + (offset * step if is_call else -offset * step)


def price(spot, strike, t_years, iv, is_call):
    t = max(t_years, MIN_Y)
    return bs_call(spot, strike, t, iv) if is_call else bs_put(spot, strike, t, iv)


def trade_pnl(s_in, s_out, hold_bars, bars_to_close, *, iv, spread_frac,
              step, bar_min=5.0, dte=0, commission=0.0065, offset=0,
              side=1):
    """One underlying trade -> one option round trip, per share.

    `side` +1 buys calls, -1 buys puts. Both are LONG premium, which is what
    the clipped strategies do -- they buy direction.
    """
    is_call = side > 0
    k = contract_for(s_in, step, is_call, offset)
    # time to expiry at entry: what is left of today, plus whole days for DTE
    t_in = max(bars_to_close * bar_min, 1.0) / (365.0 * 24.0 * 60.0) + dte / 365.0
    t_out = max(t_in - hold_bars * bar_min / (365.0 * 24.0 * 60.0), MIN_Y)

    mid_in = price(s_in, k, t_in, iv, is_call)
    mid_out = price(s_out, k, t_out, iv, is_call)
    if mid_in <= 0.01:
        return None                       # not a tradeable contract
    half = mid_in * spread_frac * 0.5
    buy = mid_in + half + commission
    half_o = max(mid_out, 0.0) * spread_frac * 0.5
    sell = max(mid_out - half_o - commission, 0.0)
    return dict(k=k, buy=buy, sell=sell, net=sell - buy,
                ret=(sell - buy) / buy, mid_in=mid_in, mid_out=mid_out,
                intrinsic=max((s_out - k) if is_call else (k - s_out), 0.0))


def summarise(rows):
    if not rows:
        return dict(n=0, pf=0.0, win=0.0, ret=0.0, med=0.0, tot=0.0)
    w = sum(r["net"] for r in rows if r["net"] > 0)
    l = -sum(r["net"] for r in rows if r["net"] <= 0)
    outlay = sum(r["buy"] for r in rows)
    return dict(n=len(rows), pf=(w / l) if l else float("inf"),
                win=sum(1 for r in rows if r["net"] > 0) / len(rows) * 100,
                tot=sum(r["net"] for r in rows),
                ret=sum(r["net"] for r in rows) / outlay * 100 if outlay else 0.0,
                med=statistics.median(r["ret"] for r in rows) * 100)
