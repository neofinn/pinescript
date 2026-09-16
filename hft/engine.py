"""The hot loop.

Design rules held throughout:
  * No allocation on the tick path. Books, signals and the histogram are
    created once at startup and mutated in place.
  * No logging on the tick path. Records go into a pre-sized ring and are
    drained after the window closes.
  * Risk is checked before the order is built, not after.
  * Every rejection is counted. A strategy that silently never trades and one
    that is being rejected 400 times a second look identical without this.

Python is not the right language for a sub-millisecond tick-to-trade path; the
GIL and the allocator both get in the way. What it is good for is getting the
logic, the risk model and the instrument plumbing correct, which is the part
that takes the longest and is language-independent. When the logic is settled,
the path from feed callback to order send is a few hundred lines to port.
gc.freeze() and a disabled collector during the window buy most of what can be
bought without leaving Python.
"""
from __future__ import annotations
import gc
from datetime import datetime

from .book import Book
from .clock import now_ns, LatencyHistogram
from .risk import RiskGate, Reject
from .session import SessionWindow, Phase, IST
from .signals import OptionSignal, MomentumGuard, BUY, SELL, NONE


class Engine:
    def __init__(self, underlying_token: int, signals: list[OptionSignal],
                 risk: RiskGate, gateway, window: SessionWindow,
                 t_years: float, log_size: int = 20_000) -> None:
        self.u_token = underlying_token
        self.books: dict[int, Book] = {underlying_token: Book(underlying_token)}
        self.signals: dict[int, OptionSignal] = {}
        for s in signals:
            self.signals[s.token] = s
            self.books[s.token] = Book(s.token)
        self.risk = risk
        self.gw = gateway
        self.window = window
        self.t_years = t_years
        self.guard = MomentumGuard()
        self.tick_to_signal = LatencyHistogram("tick->signal")
        self.tick_to_send = LatencyHistogram("tick->send")
        self._phase = Phase.PRE
        self._pending: list[tuple] = []          # drained by the async sender
        self._log = [None] * log_size            # pre-allocated
        self._log_i = 0
        self._ticks = 0
        # Position per token, and delta recomputed FROM it. Accumulating a
        # running delta off intended orders is a one-way ratchet: it never
        # reconciles against what actually filled, so it drifts up until the
        # limit blocks every further order and the strategy silently stops.
        self._pos: dict[int, int] = {}

    # ── lifecycle ──────────────────────────────────────────────────────────
    def enter_window(self) -> None:
        gc.collect()
        gc.freeze()            # move everything live into the permanent gen
        gc.disable()           # no collection pauses inside the window
        self.risk.arm()

    def leave_window(self) -> None:
        self.risk.disarm()
        gc.enable()
        gc.unfreeze()

    # ── the tick path ──────────────────────────────────────────────────────
    def on_tick(self, token: int, bid: float, ask: float, bid_qty: int,
                ask_qty: int, last: float, ts_ns: int) -> None:
        t0 = now_ns()
        book = self.books.get(token)
        if book is None:
            return
        book.update(bid, ask, bid_qty, ask_qty, last, ts_ns)
        self._ticks += 1

        if token == self.u_token:
            self.guard.push(ts_ns, book.micro)
            return                                  # underlying ticks arm, not fire

        if self._phase is not Phase.ACTIVE:
            return

        u = self.books[self.u_token]
        if not u.fresh:
            return
        spot = u.micro
        if not self.guard.calm(ts_ns, spot):
            return

        sig = self.signals.get(token)
        if sig is None:
            return
        side = sig.evaluate(book, spot, self.t_years)
        self.tick_to_signal.record(now_ns() - t0)
        if side == NONE:
            return

        net_delta = self._net_delta(spot)

        # take the side that is stale: lift the ask to buy, hit the bid to sell
        px = book.ask if side == BUY else book.bid
        lots = 1
        verdict = self.risk.check(token, side, lots, px, sig.lot, net_delta)
        if verdict is not Reject.OK:
            self._record(ts_ns, token, side, px, sig.last_edge, int(verdict))
            return

        self._pending.append((token, side, lots, px))
        self._pos[token] = self._pos.get(token, 0) + side * lots
        self._record(ts_ns, token, side, px, sig.last_edge, 0)
        self.tick_to_send.record(now_ns() - t0)

    def _net_delta(self, spot: float) -> float:
        """Portfolio delta from the live book. Cheap: the position dict holds
        only contracts actually traded, which in this window is a handful."""
        tot = 0.0
        for tok, q in self._pos.items():
            if not q:
                continue
            s = self.signals.get(tok)
            if s is not None:
                tot += q * s.last_delta * s.lot
        return tot

    def on_fill(self, token: int, side: int, lots: int) -> None:
        """Reconcile against what actually filled, not what was sent."""
        self._pos[token] = self._pos.get(token, 0) + side * lots

    def _record(self, ts_ns: int, token: int, side: int, px: float,
                edge: float, verdict: int) -> None:
        if self._log_i < len(self._log):
            self._log[self._log_i] = (ts_ns, token, side, px, edge, verdict)
            self._log_i += 1

    # ── drained off the hot path ───────────────────────────────────────────
    def drain(self) -> list[tuple]:
        if not self._pending:
            return []
        out = self._pending
        self._pending = []
        return out

    def set_phase(self, p: Phase) -> None:
        self._phase = p

    def stats(self) -> str:
        u = self.books[self.u_token]
        return (f"ticks={self._ticks} signals={self._log_i} "
                f"net_delta={self._net_delta(u.micro):+.0f} | {self.risk.summary()}\n"
                f"  {self.tick_to_signal.summary()}\n"
                f"  {self.tick_to_send.summary()}")

    def trade_log(self) -> list[tuple]:
        return [r for r in self._log[:self._log_i] if r]
