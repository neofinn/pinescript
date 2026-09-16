"""Limit-order simulator with a queue model and adverse selection.

The passive fill model is where simulators lie. Two assumptions flatter a market
maker into profitability that does not exist:

  * that you are first in the queue. You are not. You join behind whatever is
    already resting at your price, and on a liquid index strike that is most of
    the size that will ever trade there.
  * that fills are independent of what happens next. They are not. You are
    filled BECAUSE someone wanted to trade against you, and the times they most
    want to are the times the price is about to move through you. That is
    adverse selection, and modelling fills as a coin flip removes the single
    largest cost a passive strategy carries.

Both are modelled here. `adverse_bias` is how much more likely a fill is when
the underlying is moving against the resting side; set it to 0 and the results
turn optimistic in exactly the way real passive books are not.
"""
from __future__ import annotations
import random
from ..clock import now_ns
from ..orders import Order, OrdType, OrdState, OrderStore


class LimitGateway:
    def __init__(self, tick: float, store: OrderStore,
                 marketable_fill_prob: float = 0.72,
                 queue_ahead_lots: tuple[int, int] = (2, 40),
                 adverse_bias: float = 0.65,
                 fee_per_lot: float = 25.0,
                 rebate_per_lot: float = 0.0,
                 seed: int = 3) -> None:
        self.tick = tick
        self.store = store
        self.mk_prob = marketable_fill_prob
        self.q_lo, self.q_hi = queue_ahead_lots
        self.adverse_bias = adverse_bias
        self.fee = fee_per_lot
        self.rebate = rebate_per_lot
        self.rng = random.Random(seed)
        self.fills: list[dict] = []
        self.expired = 0
        self.cancelled = 0
        self.passive_fills = 0
        self.marketable_fills = 0
        self.fees_paid = 0.0

    # ── submission ─────────────────────────────────────────────────────────
    def submit(self, o: Order, bid: float, ask: float) -> None:
        if o.otype is OrdType.MARKETABLE:
            crossed = (o.side > 0 and o.limit_px >= ask) or (o.side < 0 and o.limit_px <= bid)
            if crossed and self.rng.random() <= self.mk_prob:
                px = ask if o.side > 0 else bid
                # you never fill worse than your limit; that is the whole point
                px = min(px, o.limit_px) if o.side > 0 else max(px, o.limit_px)
                self._fill(o, o.remaining, px, passive=False)
            else:
                o.state = OrdState.EXPIRED
                self.expired += 1
            return
        o.state = OrdState.RESTING
        o.queue_ahead = self.rng.randint(self.q_lo, self.q_hi)

    # ── the passive queue ──────────────────────────────────────────────────
    def on_book(self, o: Order, bid: float, ask: float, traded_lots: int,
                micro_delta: float) -> None:
        """Advance one resting order against this tick."""
        if o.state not in (OrdState.RESTING, OrdState.PARTIAL):
            return
        if o.side > 0:
            if bid < o.limit_px:            # market left you behind
                return
            at_touch = abs(bid - o.limit_px) < self.tick * 0.5
            against = micro_delta < 0.0     # falling into your bid
        else:
            if ask > o.limit_px:
                return
            at_touch = abs(ask - o.limit_px) < self.tick * 0.5
            against = micro_delta > 0.0

        if not at_touch or traded_lots <= 0:
            return

        # the queue drains before you do
        if o.queue_ahead > 0:
            eat = min(o.queue_ahead, traded_lots)
            o.queue_ahead -= eat
            traded_lots -= eat
            if traded_lots <= 0:
                return

        p = 0.5 + (self.adverse_bias * 0.5 if against else -self.adverse_bias * 0.35)
        if self.rng.random() > max(0.02, min(0.98, p)):
            return
        got = min(o.remaining, max(1, traded_lots))
        self._fill(o, got, o.limit_px, passive=True)

    def _fill(self, o: Order, lots: int, px: float, passive: bool) -> None:
        o.on_fill(lots, px)
        fee = (self.fee - self.rebate) * lots if passive else self.fee * lots
        self.fees_paid += fee
        self.fills.append(dict(oid=o.oid, token=o.token, symbol=o.symbol,
                               side=o.side, lots=lots, px=px, passive=passive,
                               fee=fee, ts=now_ns()))
        if passive:
            self.passive_fills += lots
        else:
            self.marketable_fills += lots

    def cancel(self, o: Order) -> None:
        if o.live:
            o.state = OrdState.CANCELLED
            self.cancelled += 1

    def summary(self) -> str:
        n = self.passive_fills + self.marketable_fills
        return (f"fills={n} (passive {self.passive_fills}, "
                f"marketable {self.marketable_fills})  expired={self.expired}  "
                f"cancelled={self.cancelled}  fees={self.fees_paid:,.0f}")
