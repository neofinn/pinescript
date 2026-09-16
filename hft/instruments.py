"""Per-index contract specifications.

SENSEX is the odd one: it trades on BSE, not NSE. Different exchange, different
market-data endpoint, different expiry calendar. The strategy is identical but
the feed is not, and pointing an NSE reader at it returns nothing rather than
failing loudly, so it carries its own venue tag.

Lot sizes here are DEFAULTS and they go stale. NIFTY has been 25, 50, 75 and 65;
BANKNIFTY 25, 40, 20, 15 and 30. Every one of those changes silently corrupts
position sizing if it is read from a constant instead of from the feed. Call
`refresh_from_feed` at startup and let these be the fallback, not the source.
"""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class Spec:
    symbol: str
    venue: str                 # "NSE" or "BSE"
    lot: int                   # CHECK THIS DAILY
    tick: float
    strike_step: float
    # how far either side of the money to quote-watch
    strikes_each_side: int = 6
    # the lag this index's option quotes typically run at, in ms. Wider index,
    # slower quotes: BANKNIFTY and SENSEX move more per tick than NIFTY, and
    # their makers reprice less often.
    expected_lag_ms: float = 12.0
    enabled: bool = True
    tokens: dict = field(default_factory=dict)


NIFTY = Spec("NIFTY", "NSE", lot=65, tick=0.05, strike_step=50.0,
             strikes_each_side=6, expected_lag_ms=10.0)
BANKNIFTY = Spec("BANKNIFTY", "NSE", lot=30, tick=0.05, strike_step=100.0,
                 strikes_each_side=6, expected_lag_ms=14.0)
SENSEX = Spec("SENSEX", "BSE", lot=20, tick=0.05, strike_step=100.0,
              strikes_each_side=6, expected_lag_ms=16.0)

ALL = {s.symbol: s for s in (NIFTY, BANKNIFTY, SENSEX)}


def capital_split(capital: float, specs: list[Spec],
                  spots: dict[str, float]) -> dict[str, float]:
    """Split by inverse NOTIONAL per lot, not inverse lot size.

    Lot size alone is meaningless without the index level behind it. The
    exchanges deliberately size contracts to comparable notional -- NIFTY at
    65 x 23,200, BANKNIFTY at 30 x 52,000 and SENSEX at 20 x 76,000 are all
    near 1.5 million -- so weighting by 1/lot hands SENSEX three times NIFTY's
    budget for identical exposure. Weighting by 1/notional gives the near-equal
    split the numbers actually warrant.
    """
    live = [s for s in specs if s.enabled]
    if not live:
        return {}
    w = {}
    for s in live:
        notional = max(s.lot, 1) * max(spots.get(s.symbol, 0.0), 1.0)
        w[s.symbol] = 1.0 / notional
    tot = sum(w.values())
    return {k: capital * v / tot for k, v in w.items()}
