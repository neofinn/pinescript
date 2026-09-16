"""Pre-trade risk. Every order passes through here, and it fails closed.

This layer exists because of Knight Capital: 440 million dollars in 45 minutes
from a strategy that was allowed to keep sending. The rule that prevents that is
not "check the position afterwards" but "no order leaves without passing every
limit first", and every limit here rejects rather than clamps -- a clamped order
is still an order you did not intend to send.

Checks are ordered cheapest-first so the common rejection costs the least.
"""
from __future__ import annotations
from enum import IntEnum
from .clock import now_ns


class Reject(IntEnum):
    OK = 0
    KILLED = 1
    NOT_ARMED = 2
    RATE_LIMIT = 3
    MAX_ORDERS = 4
    POSITION_LIMIT = 5
    NET_DELTA_LIMIT = 6
    ORDER_VALUE = 7
    DAILY_LOSS = 8
    PRICE_SANITY = 9
    DUPLICATE = 10


class RiskGate:
    __slots__ = ("killed", "armed", "max_pos_lots", "max_net_delta",
                 "max_order_value", "max_orders", "max_daily_loss",
                 "orders_sent", "realised", "unrealised", "_tokens",
                 "_token_rate", "_token_cap", "_last_refill_ns",
                 "_pos", "_last_by_token", "_min_gap_ns", "reject_counts")

    def __init__(self, max_pos_lots: int = 10, max_net_delta: float = 200.0,
                 max_order_value: float = 500_000.0, max_orders: int = 400,
                 max_daily_loss: float = 25_000.0, orders_per_sec: float = 8.0,
                 min_gap_us: int = 20_000) -> None:
        self.killed = False
        self.armed = False
        self.max_pos_lots = max_pos_lots
        self.max_net_delta = max_net_delta
        self.max_order_value = max_order_value
        self.max_orders = max_orders
        self.max_daily_loss = max_daily_loss
        self.orders_sent = 0
        self.realised = 0.0
        self.unrealised = 0.0
        # token bucket: brokers rate-limit, and tripping it can get the API key
        # throttled for the rest of the session
        self._token_rate = orders_per_sec
        self._token_cap = orders_per_sec
        self._tokens = orders_per_sec
        self._last_refill_ns = now_ns()
        self._pos: dict[int, int] = {}
        # Per-instrument, not global. The broker's cap is global and the token
        # bucket enforces that; this gap exists to stop one contract being
        # hammered, and making it global would block a genuine opportunity on
        # the 25050 PE because the 25000 CE fired a millisecond earlier.
        self._last_by_token: dict[int, int] = {}
        self._min_gap_ns = min_gap_us * 1_000
        self.reject_counts = [0] * (len(Reject))

    # ── state ──────────────────────────────────────────────────────────────
    def arm(self) -> None:
        self.armed = True

    def disarm(self) -> None:
        self.armed = False

    def kill(self, reason: str = "") -> None:
        """One way. A killed session does not un-kill itself."""
        self.killed = True
        self.armed = False

    def position(self, token: int) -> int:
        return self._pos.get(token, 0)

    def on_fill(self, token: int, side: int, lots: int, price: float,
                lot_size: int) -> None:
        self._pos[token] = self._pos.get(token, 0) + side * lots

    def pnl(self) -> float:
        return self.realised + self.unrealised

    # ── the gate ───────────────────────────────────────────────────────────
    def check(self, token: int, side: int, lots: int, price: float,
              lot_size: int, net_delta: float) -> Reject:
        if self.killed:
            return self._rej(Reject.KILLED)
        if not self.armed:
            return self._rej(Reject.NOT_ARMED)

        t = now_ns()
        if t - self._last_by_token.get(token, 0) < self._min_gap_ns:
            return self._rej(Reject.RATE_LIMIT)

        # refill before spending, so a quiet period actually earns tokens
        elapsed = (t - self._last_refill_ns) / 1e9
        if elapsed > 0.0:
            self._tokens = min(self._token_cap, self._tokens + elapsed * self._token_rate)
            self._last_refill_ns = t
        if self._tokens < 1.0:
            return self._rej(Reject.RATE_LIMIT)

        if self.orders_sent >= self.max_orders:
            return self._rej(Reject.MAX_ORDERS)

        if price <= 0.0 or lots <= 0:
            return self._rej(Reject.PRICE_SANITY)

        value = price * lots * lot_size
        if value > self.max_order_value:
            return self._rej(Reject.ORDER_VALUE)

        new_pos = abs(self._pos.get(token, 0) + side * lots)
        if new_pos > self.max_pos_lots:
            return self._rej(Reject.POSITION_LIMIT)

        if abs(net_delta) > self.max_net_delta:
            return self._rej(Reject.NET_DELTA_LIMIT)

        if self.pnl() < -self.max_daily_loss:
            self.kill("daily loss")
            return self._rej(Reject.DAILY_LOSS)

        # only spend the token once the order is actually going out
        self._tokens -= 1.0
        self._last_by_token[token] = t
        self.orders_sent += 1
        return Reject.OK

    def _rej(self, r: Reject) -> Reject:
        self.reject_counts[r] += 1
        return r

    def summary(self) -> str:
        parts = [f"{Reject(i).name}={c}" for i, c in enumerate(self.reject_counts)
                 if c and i != 0]
        return (f"orders={self.orders_sent} pnl={self.pnl():+.0f} "
                f"killed={self.killed} rejects[{' '.join(parts) or 'none'}]")
