"""Fast option theoretical value.

This is the hot path's most expensive computation, so it is written for speed
rather than elegance: a rational approximation to the normal CDF instead of
scipy, math.exp/log bound to locals, and no object construction. scipy.stats
.norm.cdf is roughly two orders of magnitude slower than this and allocates.

Accuracy of the Hart/Abramowitz-Stegun form used here is about 7.5e-8 absolute,
which is far finer than any tick you will trade against.

IV is not solved per tick. It is solved on a slow cadence from the underlying's
own options and held; re-solving inside the tick loop would dominate the budget
for no benefit, since IV does not move meaningfully between consecutive ticks.
"""
from __future__ import annotations
from math import exp, log, sqrt, erf

_INV_SQRT2 = 0.7071067811865476


def norm_cdf(x: float) -> float:
    """erf is a C builtin and is the fastest correct route in CPython."""
    return 0.5 * (1.0 + erf(x * _INV_SQRT2))


def bs_call(s: float, k: float, t: float, iv: float, r: float = 0.065,
            q: float = 0.0) -> float:
    if t <= 0.0 or iv <= 0.0 or s <= 0.0:
        return s - k if s > k else 0.0
    sq = iv * sqrt(t)
    d1 = (log(s / k) + (r - q + 0.5 * iv * iv) * t) / sq
    d2 = d1 - sq
    return s * exp(-q * t) * norm_cdf(d1) - k * exp(-r * t) * norm_cdf(d2)


def bs_put(s: float, k: float, t: float, iv: float, r: float = 0.065,
           q: float = 0.0) -> float:
    if t <= 0.0 or iv <= 0.0 or s <= 0.0:
        return k - s if k > s else 0.0
    sq = iv * sqrt(t)
    d1 = (log(s / k) + (r - q + 0.5 * iv * iv) * t) / sq
    d2 = d1 - sq
    return k * exp(-r * t) * norm_cdf(-d2) - s * exp(-q * t) * norm_cdf(-d1)


def bs_delta_call(s: float, k: float, t: float, iv: float, r: float = 0.065,
                  q: float = 0.0) -> float:
    if t <= 0.0 or iv <= 0.0 or s <= 0.0:
        return 1.0 if s > k else 0.0
    d1 = (log(s / k) + (r - q + 0.5 * iv * iv) * t) / (iv * sqrt(t))
    return exp(-q * t) * norm_cdf(d1)


def bs_delta_put(s: float, k: float, t: float, iv: float, r: float = 0.065,
                 q: float = 0.0) -> float:
    return bs_delta_call(s, k, t, iv, r, q) - exp(-q * t)


def implied_vol(price: float, s: float, k: float, t: float, is_call: bool,
                r: float = 0.065, q: float = 0.0, tol: float = 1e-5,
                iters: int = 60) -> float | None:
    """Bisection. Called off the hot path only.

    Bisection rather than Newton because vega collapses for deep OTM and near
    expiry -- exactly the contracts a 9:15 book is full of -- and Newton
    diverges there, which is when a wrong answer is most expensive.
    """
    if price <= 0.0 or t <= 0.0 or s <= 0.0:
        return None
    f = bs_call if is_call else bs_put
    intrinsic = (s - k) if is_call else (k - s)
    if price < max(intrinsic, 0.0) - tol:
        return None                      # below intrinsic: stale or crossed
    lo, hi = 1e-4, 5.0
    for _ in range(iters):
        mid = (lo + hi) * 0.5
        if f(s, k, t, mid, r, q) > price:
            hi = mid
        else:
            lo = mid
        if hi - lo < tol:
            break
    return (lo + hi) * 0.5


def bs_theta_call(s: float, k: float, t: float, iv: float, r: float = 0.065,
                  q: float = 0.0) -> float:
    """Per YEAR, and negative. Divide by 6.25*252 for per trading hour.

    A scalp holds for seconds, so theta per trade looks negligible -- until you
    notice it is charged on every trade and the target is one or two index
    points. At 3 days to expiry it is the largest number in the greeks.
    """
    if t <= 0.0 or iv <= 0.0 or s <= 0.0:
        return 0.0
    from math import log, sqrt, exp, pi
    d1 = (log(s / k) + (r - q + 0.5 * iv * iv) * t) / (iv * sqrt(t))
    d2 = d1 - iv * sqrt(t)
    pdf = exp(-0.5 * d1 * d1) / sqrt(2.0 * pi)
    return (-s * exp(-q * t) * pdf * iv / (2.0 * sqrt(t))
            - r * k * exp(-r * t) * norm_cdf(d2)
            + q * s * exp(-q * t) * norm_cdf(d1))


def bs_theta_put(s: float, k: float, t: float, iv: float, r: float = 0.065,
                 q: float = 0.0) -> float:
    if t <= 0.0 or iv <= 0.0 or s <= 0.0:
        return 0.0
    from math import log, sqrt, exp, pi
    d1 = (log(s / k) + (r - q + 0.5 * iv * iv) * t) / (iv * sqrt(t))
    d2 = d1 - iv * sqrt(t)
    pdf = exp(-0.5 * d1 * d1) / sqrt(2.0 * pi)
    return (-s * exp(-q * t) * pdf * iv / (2.0 * sqrt(t))
            + r * k * exp(-r * t) * norm_cdf(-d2)
            - q * s * exp(-q * t) * norm_cdf(-d1))


def bs_gamma(s: float, k: float, t: float, iv: float, r: float = 0.065,
             q: float = 0.0) -> float:
    """Same for calls and puts. Convexity is what an OTM strip is buying."""
    if t <= 0.0 or iv <= 0.0 or s <= 0.0:
        return 0.0
    from math import log, sqrt, exp, pi
    d1 = (log(s / k) + (r - q + 0.5 * iv * iv) * t) / (iv * sqrt(t))
    pdf = exp(-0.5 * d1 * d1) / sqrt(2.0 * pi)
    return exp(-q * t) * pdf / (s * iv * sqrt(t))
