"""Exits for a lag scalp. The target is a condition, not a price.

The trade is that a quote is stale against fair value. The trade is over when
that is no longer true -- which is a moving target, because fair value moves
with the underlying every tick. Setting a fixed rupee take-profit on a lag
scalp asks the wrong question: it holds a position whose reason for existing
evaporated, and cuts one whose mispricing has widened.

So the take-profit adapts to what the position was opened for:

  CONVERGED   the quote caught up. Captured enough of the entry edge; done.
  DECAYED     the mispricing is gone but so is the profit -- fair value moved
              to meet the quote rather than the quote moving to meet fair
              value. Flat, not a win, and worth counting separately because a
              strategy that mostly decays is measuring lag that is not there.
  ADVERSE     fair value moved through the entry. Cut.
  TIMEOUT     it did not converge within a multiple of this instrument's
              expected lag. It was not lag; it was a repricing you were on the
              wrong side of.
  HARD_STOP   absolute loss on the position.

The capture fraction is below 1.0 on purpose. Waiting for full convergence is
waiting for the maker to finish repricing, and the last part of that move is
exactly where they pull the quote.
"""
from __future__ import annotations
from enum import IntEnum


class ExitReason(IntEnum):
    HOLD = 0
    CONVERGED = 1
    DECAYED = 2
    ADVERSE = 3
    TIMEOUT = 4
    HARD_STOP = 5
    SESSION = 6
    RISK = 7


class ExitPolicy:
    __slots__ = ("capture_frac", "adverse_frac", "hard_stop_frac",
                 "lag_multiple", "min_hold_us", "_expected_lag_ns")

    def __init__(self, expected_lag_ms: float, capture_frac: float = 0.60,
                 adverse_frac: float = 1.20, hard_stop_frac: float = 2.5,
                 lag_multiple: float = 6.0, min_hold_us: int = 2_000) -> None:
        self.capture_frac = capture_frac
        self.adverse_frac = adverse_frac
        self.hard_stop_frac = hard_stop_frac
        self.lag_multiple = lag_multiple
        self.min_hold_us = min_hold_us
        self._expected_lag_ns = int(expected_lag_ms * 1e6)

    def scaled(self, spread: float, tick: float, edge: float) -> float:
        """How much of the entry edge must be captured, in price terms.

        A wide spread means the exit itself costs more, so more of the edge has
        to be captured before leaving is worth it. A tight one lets you take
        less and go.
        """
        base = edge * self.capture_frac
        spread_cost = spread * 0.5
        return base if base > spread_cost else spread_cost

    def evaluate(self, side: int, entry_px: float, entry_edge: float,
                 theo: float, bid: float, ask: float, tick: float,
                 age_ns: int) -> tuple[ExitReason, float]:
        """-> (reason, exit price). Called per tick on every open position."""
        if age_ns < self.min_hold_us * 1_000:
            return ExitReason.HOLD, 0.0

        # you exit where you can actually trade, not at the mid
        exit_px = bid if side > 0 else ask
        if exit_px <= 0.0:
            return ExitReason.HOLD, 0.0

        spread = ask - bid if ask > bid else tick
        pnl_px = (exit_px - entry_px) if side > 0 else (entry_px - exit_px)

        if pnl_px <= -self.hard_stop_frac * entry_edge:
            return ExitReason.HARD_STOP, exit_px

        # fair value has moved through where you entered
        drift = (theo - entry_px) if side > 0 else (entry_px - theo)
        if drift <= -self.adverse_frac * entry_edge:
            return ExitReason.ADVERSE, exit_px

        need = self.scaled(spread, tick, entry_edge)
        if pnl_px >= need:
            return ExitReason.CONVERGED, exit_px

        # mispricing closed without paying: fair value came to the quote
        residual = (theo - ask) if side > 0 else (bid - theo)
        if residual < entry_edge * 0.15:
            if age_ns > self._expected_lag_ns:
                return ExitReason.DECAYED, exit_px

        if age_ns > self._expected_lag_ns * self.lag_multiple:
            return ExitReason.TIMEOUT, exit_px

        return ExitReason.HOLD, 0.0
