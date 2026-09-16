"""Monotonic timing and latency measurement.

Wall-clock time is unusable here: NTP steps it, and a step during the session
silently corrupts every latency figure. time.perf_counter_ns is monotonic and
nanosecond-resolution, which is what tick-to-trade has to be measured against.

The histogram is pre-allocated and fixed-width on purpose. Growing a structure
inside the hot path is an allocation, and an allocation is a GC trigger.
"""
from __future__ import annotations
import time
from typing import Final

now_ns = time.perf_counter_ns          # bind once; attribute lookup is not free
wall_ns = time.time_ns

NS_PER_US: Final = 1_000
NS_PER_MS: Final = 1_000_000


class LatencyHistogram:
    """Fixed log-spaced buckets, no allocation after construction."""

    __slots__ = ("_edges", "_counts", "_n", "_sum", "_max", "name")

    def __init__(self, name: str) -> None:
        self.name = name
        # 1us .. 1s, roughly quarter-decade spacing
        self._edges = (
            1_000, 2_000, 5_000, 10_000, 20_000, 50_000, 100_000, 200_000,
            500_000, 1_000_000, 2_000_000, 5_000_000, 10_000_000, 50_000_000,
            100_000_000, 500_000_000, 1_000_000_000,
        )
        self._counts = [0] * (len(self._edges) + 1)
        self._n = 0
        self._sum = 0
        self._max = 0

    def record(self, dt_ns: int) -> None:
        self._n += 1
        self._sum += dt_ns
        if dt_ns > self._max:
            self._max = dt_ns
        edges = self._edges
        # linear scan beats bisect for ~17 buckets and avoids the import cost
        i = 0
        while i < len(edges) and dt_ns > edges[i]:
            i += 1
        self._counts[i] += 1

    def percentile(self, p: float) -> int:
        if self._n == 0:
            return 0
        target = self._n * p / 100.0
        seen = 0
        for i, c in enumerate(self._counts):
            seen += c
            if seen >= target:
                return self._edges[i] if i < len(self._edges) else self._edges[-1]
        return self._max

    def summary(self) -> str:
        if self._n == 0:
            return f"{self.name}: no samples"
        return (f"{self.name}: n={self._n} "
                f"mean={self._sum / self._n / NS_PER_US:.1f}us "
                f"p50={self.percentile(50) / NS_PER_US:.0f}us "
                f"p99={self.percentile(99) / NS_PER_US:.0f}us "
                f"max={self._max / NS_PER_US:.0f}us")
