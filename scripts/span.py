"""A SPAN-style portfolio margin: scan the whole structure, charge the worst case.

This is what the earlier model got wrong. Charging each leg its own margin
treats a hedged position as if the hedge were not there -- a long future plus a
protective put was billed the full futures margin, when its downside is capped
at the put strike and SPAN knows it. A collar, bounded on both sides, was billed
the same again.

SPAN revalues the entire portfolio across a grid of underlying and volatility
moves and charges the worst loss it finds. That is reproduced here: options are
revalued with Black-Scholes at their own implied vol, futures move one for one,
and the margin is the worst portfolio outcome plus an exposure charge. The
offsets fall out of the arithmetic instead of being asserted.

Scan parameters follow NSE's published shape -- a price scan near three standard
deviations and a volatility scan alongside it -- but they are parameters here,
and the sensitivity is worth checking before trusting any number that depends
on them.
"""
import sys
sys.path.insert(0, "/home/user/index-option-brain")
from index_option_brain.analytics.pricing import price_option, implied_volatility
from index_option_brain.contracts.enums import OptionType

PRICE_SCAN = 0.06        # +/- 6% of underlying, roughly 3 sigma on a monthly
VOL_SCAN   = 0.10        # +/- 10% relative move in implied vol
EXPOSURE   = 0.02        # exposure margin, share of notional
SHORT_FLOOR = 0.015      # regulatory floor for a short option, share of notional
DIVY       = 0.012

def leg_iv(spot, strike, years, ot, premium):
    iv = implied_volatility(market_price=premium, spot=spot, strike=strike,
                            years=years, option_type=OptionType(ot), dividend_yield=DIVY)
    return iv if iv and iv > 0.01 else 0.15      # a sane fallback, not a silent zero

def revalue(spot, legs, years, shock, vshock):
    """Structure value at a shocked spot and vol, per unit of underlying."""
    s = spot * (1 + shock)
    v = 0.0
    for lg in legs:
        if lg["kind"] == "fut":
            v += lg["qty"] * (s - spot)
        else:
            iv = max(lg["iv"] * (1 + vshock), 0.01)
            p = price_option(spot=s, strike=lg["strike"], years=max(years, 1/365),
                             iv=iv, option_type=OptionType(lg["ot"]),
                             dividend_yield=DIVY).price
            v += lg["qty"] * (p - lg["premium"])
    return v

def span_margin(spot, legs, years, price_scan=PRICE_SCAN, vol_scan=VOL_SCAN):
    """Worst-case loss across the scan grid, plus exposure. Per unit underlying."""
    worst = 0.0
    steps = [i / 3.0 for i in range(-3, 4)]                   # 7 price points
    for f in steps:
        for vs in (-vol_scan, 0.0, vol_scan):
            worst = min(worst, revalue(spot, legs, years, f * price_scan, vs))
    scan = -worst
    # Exposure is charged once on the net directional notional, not per leg.
    # Charging a covered call's short leg separately double counts: the future
    # already carries that exposure, which is what makes the call covered.
    nfut = sum(lg["qty"] for lg in legs if lg["kind"] == "fut")
    nshort_naked = sum(-lg["qty"] for lg in legs
                       if lg["kind"] == "opt" and lg["qty"] < 0) if nfut == 0 else 0.0
    expo = (abs(nfut) + max(nshort_naked, 0.0)) * spot * EXPOSURE
    m = scan + expo
    # a naked short option can never margin below the regulatory floor
    naked_short = any(lg["kind"] == "opt" and lg["qty"] < 0 for lg in legs) and not any(
        lg["kind"] == "fut" for lg in legs)
    if naked_short:
        longs = [lg for lg in legs if lg["kind"] == "opt" and lg["qty"] > 0]
        if not longs: m = max(m, spot * SHORT_FLOOR * 4)
    return max(m, 0.0)
