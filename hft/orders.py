"""Order types and their state machine. No market orders anywhere.

"Limit orders only" splits into two genuinely different strategies and the
distinction decides everything downstream:

  MARKETABLE (IOC)  a limit priced to cross, immediate-or-cancel. You still
                    take liquidity and pay the spread, but the price is capped:
                    you fill at your limit or better, or not at all. This is
                    what protects against the fill you get when the quote moves
                    between decision and arrival -- the exact failure a market
                    order hands you at whatever price is left.

  PASSIVE           rest at or inside the touch and wait to be hit. Now you
                    EARN the spread instead of paying it, which for a strategy
                    whose edge is a few ticks is the difference between viable
                    and not. The cost is queue position and adverse selection:
                    you are filled when someone wants to trade against you, and
                    the times they most want to are the times you least should.

The lag edge works with either, differently. Marketable takes the stale quote
now. Passive posts at fair value and is filled by whoever is slow. Passive is
better economics and worse certainty, and a strategy that assumes it always
gets its passive fill is measuring a market that does not exist.
"""
from __future__ import annotations
from enum import IntEnum
from .clock import now_ns


class OrdType(IntEnum):
    MARKETABLE = 0        # limit priced to cross, IOC
    PASSIVE = 1           # rest and wait


class OrdState(IntEnum):
    NEW = 0
    RESTING = 1
    PARTIAL = 2
    FILLED = 3
    CANCELLED = 4
    REJECTED = 5
    EXPIRED = 6           # IOC that did not cross


class Order:
    __slots__ = ("oid", "token", "symbol", "side", "lots", "limit_px",
                 "otype", "state", "filled", "avg_px", "created_ns",
                 "queue_ahead", "replaces")

    def __init__(self, oid: int, token: int, symbol: str, side: int, lots: int,
                 limit_px: float, otype: OrdType) -> None:
        self.oid = oid
        self.token = token
        self.symbol = symbol
        self.side = side
        self.lots = lots
        self.limit_px = limit_px
        self.otype = otype
        self.state = OrdState.NEW
        self.filled = 0
        self.avg_px = 0.0
        self.created_ns = now_ns()
        # Size resting ahead of you at your price when you joined. A passive
        # fill model that ignores this assumes you are always first in the
        # queue, which is the most expensive wrong assumption available.
        self.queue_ahead = 0
        self.replaces = 0

    @property
    def live(self) -> bool:
        return self.state in (OrdState.NEW, OrdState.RESTING, OrdState.PARTIAL)

    @property
    def remaining(self) -> int:
        return self.lots - self.filled

    def age_ns(self) -> int:
        return now_ns() - self.created_ns

    def on_fill(self, lots: int, px: float) -> None:
        prev = self.filled
        self.filled += lots
        self.avg_px = ((self.avg_px * prev) + px * lots) / self.filled
        self.state = OrdState.FILLED if self.filled >= self.lots else OrdState.PARTIAL


class OrderStore:
    """Live orders, indexed for the two lookups the hot path actually does."""

    __slots__ = ("_by_id", "_by_token", "_next")

    def __init__(self) -> None:
        self._by_id: dict[int, Order] = {}
        self._by_token: dict[int, list[Order]] = {}
        self._next = 1

    def new(self, token: int, symbol: str, side: int, lots: int,
            limit_px: float, otype: OrdType) -> Order:
        o = Order(self._next, token, symbol, side, lots, limit_px, otype)
        self._next += 1
        self._by_id[o.oid] = o
        self._by_token.setdefault(token, []).append(o)
        return o

    def get(self, oid: int) -> Order | None:
        return self._by_id.get(oid)

    def live_for(self, token: int) -> list[Order]:
        lst = self._by_token.get(token)
        if not lst:
            return []
        return [o for o in lst if o.live]

    def has_live(self, token: int) -> bool:
        lst = self._by_token.get(token)
        if not lst:
            return False
        for o in lst:
            if o.live:
                return True
        return False

    def all_live(self) -> list[Order]:
        return [o for o in self._by_id.values() if o.live]

    def retire(self, o: Order, state: OrdState) -> None:
        o.state = state
        lst = self._by_token.get(o.token)
        if lst and len(lst) > 32:
            self._by_token[o.token] = [x for x in lst if x.live]

    def sweep(self) -> int:
        """Drop finished orders. Off the hot path."""
        dead = [k for k, o in self._by_id.items() if not o.live]
        for k in dead:
            del self._by_id[k]
        for t in list(self._by_token):
            self._by_token[t] = [o for o in self._by_token[t] if o.live]
            if not self._by_token[t]:
                del self._by_token[t]
        return len(dead)


def price_for(otype: OrdType, side: int, bid: float, ask: float, theo: float,
              tick: float, improve_ticks: float = 0.0) -> float:
    """Where the order goes.

    Marketable crosses at the touch, capped there -- never through it.
    Passive joins the near side, optionally improving by a tick to get ahead of
    the queue, but is never posted through fair value: quoting a price you
    yourself think is wrong is how a maker gets picked off.
    """
    if otype is OrdType.MARKETABLE:
        return ask if side > 0 else bid
    if side > 0:
        px = bid + improve_ticks * tick
        cap = theo - tick
        return min(px, cap) if cap > 0 else px
    px = ask - improve_ticks * tick
    floor = theo + tick
    return max(px, floor)
