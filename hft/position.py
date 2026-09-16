"""Position book: one lot per strike, breadth instead of depth.

The rule is deliberate. Ten lots on one strike and one lot on ten strikes carry
the same notional and completely different risk. Stacked on a single contract
you are exposed to that contract's maker pulling, to that strike's liquidity,
and to one exit having to clear ten lots through a book that showed you size for
one. Spread across strikes, each position is the size the quote actually showed,
and a bad fill on one is a bad fill on one.

It also matches what the strategy is. Lag is a per-contract phenomenon: each
maker reprices on their own clock, so ten stale quotes is ten opportunities,
while one stale quote taken ten times is one opportunity and nine slippages.
"""
from __future__ import annotations
from .clock import now_ns


class Position:
    __slots__ = ("token", "symbol", "strike", "is_call", "lots", "entry_px",
                 "entry_ns", "entry_theo", "entry_edge", "lot_size", "side")

    def __init__(self, token: int, symbol: str, strike: float, is_call: bool,
                 side: int, lots: int, entry_px: float, entry_theo: float,
                 entry_edge: float, lot_size: int) -> None:
        self.token = token
        self.symbol = symbol
        self.strike = strike
        self.is_call = is_call
        self.side = side
        self.lots = lots
        self.entry_px = entry_px
        self.entry_ns = now_ns()
        self.entry_theo = entry_theo
        self.entry_edge = entry_edge
        self.lot_size = lot_size

    def age_ns(self) -> int:
        return now_ns() - self.entry_ns

    def mtm(self, mark: float) -> float:
        return self.side * (mark - self.entry_px) * self.lots * self.lot_size


class Book:
    """At most `lots_per_strike` on any one contract, `max_strikes` open."""

    __slots__ = ("lots_per_strike", "max_strikes", "_pos", "opened", "closed")

    def __init__(self, lots_per_strike: int = 1, max_strikes: int = 8) -> None:
        self.lots_per_strike = lots_per_strike
        self.max_strikes = max_strikes
        self._pos: dict[int, Position] = {}
        self.opened = 0
        self.closed = 0

    def can_open(self, token: int) -> bool:
        if token in self._pos:
            return False                      # never add to a winner or a loser
        return len(self._pos) < self.max_strikes

    def open(self, p: Position) -> None:
        self._pos[p.token] = p
        self.opened += 1

    def close(self, token: int) -> Position | None:
        p = self._pos.pop(token, None)
        if p is not None:
            self.closed += 1
        return p

    def get(self, token: int) -> Position | None:
        return self._pos.get(token)

    def open_tokens(self):
        return list(self._pos.keys())

    def count(self) -> int:
        return len(self._pos)

    def flat(self) -> bool:
        return not self._pos

    def net_delta(self, deltas: dict[int, float]) -> float:
        tot = 0.0
        for tok, p in self._pos.items():
            d = deltas.get(tok)
            if d is not None:
                tot += p.side * d * p.lots * p.lot_size
        return tot
