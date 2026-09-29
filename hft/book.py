"""Top-of-book state, microprice and imbalance.

Microprice rather than mid. The mid sits halfway between bid and ask regardless
of how much size is resting on each side; the microprice weights toward the
thinner side, which is where the book is about to move. It is the single most
useful number in a short-horizon book signal, and it costs two multiplications.

Every instrument's book is a __slots__ object updated in place. Rebuilding a
dict or a namedtuple per tick would allocate thousands of times a second.
"""
from __future__ import annotations
from .clock import now_ns


class Book:
    __slots__ = ("token", "bid", "ask", "bid_qty", "ask_qty",
                 "last", "ts_ns", "seq", "_prev_micro", "_micro")

    def __init__(self, token: int) -> None:
        self.token = token
        self.bid = 0.0
        self.ask = 0.0
        self.bid_qty = 0
        self.ask_qty = 0
        self.last = 0.0
        self.ts_ns = 0
        self.seq = 0
        self._prev_micro = 0.0
        self._micro = 0.0

    def update(self, bid: float, ask: float, bid_qty: int, ask_qty: int,
               last: float, ts_ns: int) -> None:
        self.bid = bid
        self.ask = ask
        self.bid_qty = bid_qty
        self.ask_qty = ask_qty
        self.last = last
        self.ts_ns = ts_ns
        self.seq += 1
        self._prev_micro = self._micro
        tot = bid_qty + ask_qty
        if tot > 0 and bid > 0.0 and ask > 0.0:
            # weight toward the side with LESS size: that side breaks first
            self._micro = (bid * ask_qty + ask * bid_qty) / tot
        elif bid > 0.0 and ask > 0.0:
            self._micro = (bid + ask) * 0.5

    @property
    def micro(self) -> float:
        return self._micro

    @property
    def micro_delta(self) -> float:
        return self._micro - self._prev_micro

    @property
    def mid(self) -> float:
        return (self.bid + self.ask) * 0.5 if self.bid > 0.0 and self.ask > 0.0 else 0.0

    @property
    def spread(self) -> float:
        return self.ask - self.bid if self.ask > 0.0 and self.bid > 0.0 else 1e9

    @property
    def imbalance(self) -> float:
        """(bid - ask) / (bid + ask) of resting size. +1 all bid, -1 all ask."""
        tot = self.bid_qty + self.ask_qty
        return (self.bid_qty - self.ask_qty) / tot if tot > 0 else 0.0

    @property
    def fresh(self) -> bool:
        return self.bid > 0.0 and self.ask > 0.0 and self.ask > self.bid

    def age_ns(self) -> int:
        return now_ns() - self.ts_ns
