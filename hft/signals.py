"""The alpha: options lag their underlying.

An index option's fair value is a deterministic function of the underlying. The
underlying's book updates continuously; each option's quote updates when its
market maker gets round to it. In the first minutes of a session, when the
underlying is moving fastest and quote traffic is heaviest, that gap is at its
widest. The trade is to compute fair value from the underlying faster than the
option quote reprices, and lift or hit the stale side.

Two guards matter more than the signal itself:

  * A stale quote and a WIDE quote look identical to a naive edge calculation.
    Requiring the edge to clear a fraction of the spread separates "mispriced"
    from "nobody is quoting tightly", which is most of what you see at 9:15.
  * Book age. A quote nobody has updated for 200ms is not an opportunity, it is
    a quote that will be pulled the moment you take it. That is adverse
    selection, and it is how this strategy loses money.
"""
from __future__ import annotations
from .book import Book
from .pricing import bs_call, bs_put, bs_delta_call, bs_delta_put

BUY, SELL, NONE = 1, -1, 0


class OptionSignal:
    __slots__ = ("token", "strike", "is_call", "iv", "lot", "tick",
                 "min_edge_ticks", "spread_frac", "max_book_age_ns",
                 "last_side", "last_edge", "last_theo", "last_delta")

    def __init__(self, token: int, strike: float, is_call: bool, iv: float,
                 lot: int, tick: float, min_edge_ticks: float = 2.0,
                 spread_frac: float = 0.55, max_book_age_us: int = 50_000) -> None:
        self.token = token
        self.strike = strike
        self.is_call = is_call
        self.iv = iv
        self.lot = lot
        self.tick = tick
        self.min_edge_ticks = min_edge_ticks
        self.spread_frac = spread_frac
        self.max_book_age_ns = max_book_age_us * 1_000
        self.last_side = NONE
        self.last_edge = 0.0
        self.last_theo = 0.0
        self.last_delta = 0.0

    def evaluate(self, opt: Book, spot: float, t_years: float) -> int:
        """-> BUY / SELL / NONE. No allocation, no branching beyond necessity."""
        if not opt.fresh or spot <= 0.0:
            return NONE
        if opt.age_ns() > self.max_book_age_ns:
            return NONE                       # stale enough to be a trap

        iv = self.iv
        if iv <= 0.0:
            return NONE
        k = self.strike
        theo = (bs_call(spot, k, t_years, iv) if self.is_call
                else bs_put(spot, k, t_years, iv))
        self.last_theo = theo

        spread = opt.spread
        floor = self.min_edge_ticks * self.tick
        need = floor if floor > spread * self.spread_frac else spread * self.spread_frac

        # the ask is cheap against fair value -> lift it
        edge_buy = theo - opt.ask
        if edge_buy > need:
            self.last_side = BUY
            self.last_edge = edge_buy
            self.last_delta = (bs_delta_call(spot, k, t_years, iv) if self.is_call
                               else bs_delta_put(spot, k, t_years, iv))
            return BUY

        # the bid is rich against fair value -> hit it
        edge_sell = opt.bid - theo
        if edge_sell > need:
            self.last_side = SELL
            self.last_edge = edge_sell
            self.last_delta = (bs_delta_call(spot, k, t_years, iv) if self.is_call
                               else bs_delta_put(spot, k, t_years, iv))
            return SELL

        self.last_side = NONE
        self.last_edge = 0.0
        return NONE


class MomentumGuard:
    """Refuse to trade into a violently moving underlying.

    Theoretical value computed from a microprice that is itself mid-move is a
    forecast, not a fair value. When the underlying is running, the option quote
    you think is stale is often correctly anticipating where the underlying is
    going, and taking it is picking up pennies in front of it.
    """

    __slots__ = ("max_move", "window_ns", "_ring", "_n", "_i")

    def __init__(self, max_move_frac: float = 0.0006, window_ms: int = 250,
                 size: int = 256) -> None:
        self.max_move = max_move_frac
        self.window_ns = window_ms * 1_000_000
        self._ring = [(0, 0.0)] * size       # pre-allocated, overwritten in place
        self._n = size
        self._i = 0

    def push(self, ts_ns: int, px: float) -> None:
        self._ring[self._i] = (ts_ns, px)
        self._i = (self._i + 1) % self._n

    def calm(self, ts_ns: int, px: float) -> bool:
        cutoff = ts_ns - self.window_ns
        lo = hi = px
        ring = self._ring
        for j in range(self._n):
            t, p = ring[j]
            if t >= cutoff and p > 0.0:
                if p < lo: lo = p
                if p > hi: hi = p
        return px > 0.0 and (hi - lo) / px <= self.max_move
