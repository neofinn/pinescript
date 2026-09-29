"""ES and NQ futures. The modelling error that dominated the options work is gone.

Every option number in this project rested on Black-Scholes off a volatility
index, with no smile, no skew, and a premium that no one quoted. On futures
there is no strike to choose, no implied vol to estimate and no pricing model at
all: profit is (exit - entry) x multiplier x contracts, and the only assumptions
left are the spread and the commission, both of which are published.

That removes, in one move:
  * the IV assumption that flipped the SPY/QQQ result's sign at 1.25x
  * the derived lot sizes used for Indian stock options
  * the synthetic volume needed for Indian indices, which print none
  * the expiry-day gamma that made the NIFTY results hostage to one contract

CONTRACT TERMS are published, not derived. Minis and micros are both listed
because the micro is what makes a staged live rollout possible: one MES is a
tenth of one ES, so a real-money stage can risk tens of dollars rather than
hundreds.
"""
from __future__ import annotations

# multiplier: dollars per index point. tick: minimum price increment.
# comm: round-turn commission + exchange/NFA fees, a realistic retail figure.
CONTRACT = {
    "ES":  dict(mult=50.0, tick=0.25, comm=4.94, name="E-mini S&P 500"),
    "NQ":  dict(mult=20.0, tick=0.25, comm=4.94, name="E-mini Nasdaq 100"),
    "MES": dict(mult=5.0,  tick=0.25, comm=1.44, name="Micro E-mini S&P"),
    "MNQ": dict(mult=2.0,  tick=0.25, comm=1.44, name="Micro E-mini Nasdaq"),
}


def round_turn_cost(sym, contracts=1, spread_ticks=1.0):
    """Commission plus one spread crossed, per round turn.

    A marketable entry and a marketable exit each cross half the spread, so a
    round turn pays one full spread. ES and NQ are both one tick wide in normal
    conditions; widen spread_ticks for the open, the close, and events.
    """
    c = CONTRACT[sym]
    return contracts * (c["comm"] + spread_ticks * c["tick"] * c["mult"])


def pnl(sym, side, entry, exit_, contracts=1, spread_ticks=1.0):
    c = CONTRACT[sym]
    gross = side * (exit_ - entry) * c["mult"] * contracts
    return gross - round_turn_cost(sym, contracts, spread_ticks)


def size_for_risk(sym, risk_dollars, stop_points, spread_ticks=1.0):
    """Contracts such that being stopped costs about risk_dollars.

    The cost of the round turn is inside the risk, not added after it -- that
    was a real bug in the options run, where the cap was tested before costs
    and every capped trade breached it.
    """
    c = CONTRACT[sym]
    per = stop_points * c["mult"] + c["comm"] + spread_ticks * c["tick"] * c["mult"]
    if per <= 0:
        return 0
    return int(risk_dollars // per)
