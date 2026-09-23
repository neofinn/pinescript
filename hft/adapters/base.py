"""The broker/feed boundary.

Everything above this line is venue-agnostic. Implement this for whatever you
are actually connected to -- a colocated binary feed, a broker WebSocket, the
simulator in sim.py -- and the strategy does not change.

on_tick is called from the feed thread or loop and must return fast. Anything
slow belongs on a separate cadence; blocking here adds latency to every
subsequent tick, not just this one.
"""
from __future__ import annotations
from typing import Callable, Protocol


class Feed(Protocol):
    def subscribe(self, tokens: list[int]) -> None: ...
    def set_handler(self, fn: Callable[[int, float, float, int, int, float, int], None]) -> None: ...
    async def run(self) -> None: ...
    async def stop(self) -> None: ...


class Gateway(Protocol):
    async def send(self, token: int, side: int, lots: int, price: float,
                   ioc: bool = True) -> str | None: ...
    async def cancel(self, order_id: str) -> bool: ...
    async def cancel_all(self) -> int: ...
    async def flatten(self) -> int: ...
