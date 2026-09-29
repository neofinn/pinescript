"""Statutory cost stack. Zero brokerage is not zero cost.

Removing brokerage removes the one line item that was flat per order. What is
left is almost entirely proportional to premium, and that changes the shape of
the problem rather than just its size:

  * A flat per-lot fee sets a break-even in TICKS that is fixed per contract,
    and is worst for the smallest lot -- SENSEX, because the fee spreads over
    the fewest units.
  * A proportional fee sets a break-even that is a fixed PERCENTAGE OF PREMIUM,
    identical across indices, and worst for the most expensive option. Lot size
    drops out of the arithmetic entirely.

STT is the item that matters and it is not negotiable. At 0.15% of premium on
the sell leg it is roughly 63% of the whole round trip, so an exchange-member
seat with zero brokerage still pays about 0.24% of premium to open and close.
That is the number a scalp has to clear.

Rates below are the published ones as at 2026-09. They move -- STT went
0.0625% -> 0.1% on 2024-10-01 and 0.1% -> 0.15% on 2026-04-01, and NSE added
Rs300/crore to the options transaction charge on 2026-03-01. Check them against
your own contract notes before trusting any number this module produces; a
stale rate here quietly biases every backtest that imports it.
"""
from __future__ import annotations
from dataclasses import dataclass

CRORE = 10_000_000.0


@dataclass(frozen=True)
class CostModel:
    """All rates are fractions of premium turnover unless named otherwise."""
    venue: str
    stt_sell: float          # sell leg only
    txn: float               # per leg
    sebi: float              # per leg
    ipft: float              # per leg
    stamp_buy: float         # buy leg only
    gst: float               # on (brokerage + txn + sebi + ipft)
    brokerage_per_order: float = 0.0
    flat_per_lot: float = 0.0   # if set, replaces everything above

    # ── one leg ────────────────────────────────────────────────────────────
    def leg_cost(self, premium: float, lot_size: int, lots: int,
                 side: int) -> float:
        """Cost of a single fill. `side` +1 bought, -1 sold."""
        if self.flat_per_lot > 0.0:
            return self.flat_per_lot * lots
        turnover = premium * lot_size * lots
        pct = self.txn + self.sebi + self.ipft
        cost = turnover * pct + self.brokerage_per_order
        cost += self.gst * (turnover * pct + self.brokerage_per_order)
        if side < 0:
            cost += turnover * self.stt_sell
        else:
            cost += turnover * self.stamp_buy
        return cost

    # ── the whole trip, as a fraction of premium ───────────────────────────
    def round_trip_frac(self) -> float:
        """Buy then sell (or sell then buy) -- STT lands once either way."""
        if self.flat_per_lot > 0.0:
            return 0.0
        pct = (self.txn + self.sebi + self.ipft) * 2.0
        return (self.stt_sell + self.stamp_buy + pct + self.gst * pct)

    def breakeven_ticks(self, premium: float, tick: float = 0.05) -> float:
        """How far the option has to move before a round trip pays for itself."""
        if self.flat_per_lot > 0.0:
            return 0.0
        return self.round_trip_frac() * premium / tick

    def breakdown(self, premium: float, lot_size: int) -> list[tuple[str, float, float]]:
        """(name, rupees per round trip on one lot, share of total)."""
        t = premium * lot_size
        pct2 = 2.0
        items = [
            ("STT (sell leg, 0.15%)", t * self.stt_sell),
            ("exchange txn", t * self.txn * pct2),
            ("GST 18%", self.gst * (t * (self.txn + self.sebi + self.ipft) * pct2
                                    + self.brokerage_per_order * pct2)),
            ("stamp duty (buy leg)", t * self.stamp_buy),
            ("IPFT", t * self.ipft * pct2),
            ("SEBI turnover", t * self.sebi * pct2),
            ("brokerage", self.brokerage_per_order * pct2),
        ]
        tot = sum(v for _, v in items)
        return [(n, v, v / tot if tot else 0.0) for n, v in items]


# Published rates as at 2026-09. STT 0.15% on option sale since 2026-04-01;
# NSE options transaction charge 0.03553% of premium since 2026-03-01.
NSE_MEMBER = CostModel(
    venue="NSE",
    stt_sell=0.0015,          # 0.15% of premium, sell leg
    txn=0.0003553,            # 0.03553% of premium, per leg
    sebi=0.000001,            # Rs10 per crore
    ipft=0.000005,            # Rs50 per crore
    stamp_buy=0.00003,        # 0.003% / Rs300 per crore, buy leg
    gst=0.18,
    brokerage_per_order=0.0,  # exchange member, own seat
)

BSE_MEMBER = CostModel(
    venue="BSE",
    stt_sell=0.0015,
    txn=0.000325,             # 0.0325% of premium, per leg
    sebi=0.000001,
    ipft=0.000005,
    stamp_buy=0.00003,
    gst=0.18,
    brokerage_per_order=0.0,
)

# What a retail seat paid, kept for comparison: Rs20 per executed order on top.
NSE_RETAIL = CostModel(
    venue="NSE", stt_sell=0.0015, txn=0.0003553, sebi=0.000001, ipft=0.000005,
    stamp_buy=0.00003, gst=0.18, brokerage_per_order=20.0,
)

# The flat model this repo used before the cost stack was worked out. It is
# wrong in shape, not just in level, and is kept only so the difference can be
# shown rather than asserted.
FLAT_25 = CostModel(venue="-", stt_sell=0, txn=0, sebi=0, ipft=0, stamp_buy=0,
                    gst=0, flat_per_lot=25.0)

BY_VENUE = {"NSE": NSE_MEMBER, "BSE": BSE_MEMBER}
