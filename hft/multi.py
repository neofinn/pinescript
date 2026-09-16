"""Three indices, one risk pool, one clock.

NIFTY and BANKNIFTY come off NSE, SENSEX off BSE. Each gets its own books,
signals and exit policy -- their lags differ, so a single shared threshold would
be too loose for one and too tight for another -- but they share the RiskGate,
because the account is one account. Three independently-limited strategies each
respecting a 2% loss limit is a 6% loss limit nobody chose.

Firing at full speed means no artificial global throttle: a stale 25000 CE and a
stale 52000 BANKNIFTY PE are separate opportunities and neither should wait for
the other. What remains is the per-contract gap, which stops the same stale
quote being hit repeatedly before the fill comes back, and the token bucket,
which is the broker's published limit and not negotiable.
"""
from __future__ import annotations
import gc
from .book import Book as OrderBook
from .clock import now_ns, LatencyHistogram
from .exits import ExitPolicy, ExitReason
from .instruments import Spec
from .position import Book as PositionBook, Position
from .risk import RiskGate, Reject
from .session import Phase
from .signals import OptionSignal, MomentumGuard, BUY, SELL, NONE


class IndexLeg:
    """Everything that belongs to one index."""

    __slots__ = ("spec", "u_token", "books", "signals", "positions", "exits",
                 "guard", "t_years", "_deltas")

    def __init__(self, spec: Spec, u_token: int, signals: list[OptionSignal],
                 t_years: float, lots_per_strike: int, max_strikes: int) -> None:
        self.spec = spec
        self.u_token = u_token
        self.books = {u_token: OrderBook(u_token)}
        self.signals: dict[int, OptionSignal] = {}
        for s in signals:
            self.signals[s.token] = s
            self.books[s.token] = OrderBook(s.token)
        self.positions = PositionBook(lots_per_strike, max_strikes)
        self.exits = ExitPolicy(spec.expected_lag_ms)
        self.guard = MomentumGuard()
        self.t_years = t_years
        self._deltas: dict[int, float] = {}

    def net_delta(self) -> float:
        return self.positions.net_delta(self._deltas)


class MultiEngine:
    def __init__(self, legs: list[IndexLeg], risk: RiskGate,
                 log_size: int = 50_000) -> None:
        self.legs = {l.spec.symbol: l for l in legs}
        self._by_token: dict[int, IndexLeg] = {}
        for l in legs:
            for tok in l.books:
                self._by_token[tok] = l
        self.risk = risk
        self.lat_signal = LatencyHistogram("tick->signal")
        self.lat_send = LatencyHistogram("tick->send")
        self._phase = Phase.PRE
        self._pending: list[tuple] = []
        self._log = [None] * log_size
        self._log_i = 0
        self._log_n = 0
        self._ticks = 0
        self._last_gc_ns = 0
        self._gc_every_ns = 5_000_000_000
        self.exit_counts = [0] * len(ExitReason)
        self.pnl_by_symbol: dict[str, float] = {}
        self.trades_by_symbol: dict[str, int] = {}

    # ── lifecycle ──────────────────────────────────────────────────────────
    def enter(self) -> None:
        gc.collect(); gc.freeze(); gc.disable()
        self._last_gc_ns = now_ns()
        self.risk.arm()

    def leave(self) -> None:
        self.risk.disarm(); gc.enable(); gc.unfreeze()

    def set_phase(self, p: Phase) -> None:
        self._phase = p

    def flat(self) -> bool:
        return all(l.positions.flat() for l in self.legs.values())

    def maintenance(self) -> bool:
        if not self.flat():
            return False
        t = now_ns()
        if t - self._last_gc_ns < self._gc_every_ns:
            return False
        gc.collect(0)
        self._last_gc_ns = now_ns()
        return True

    def net_delta(self) -> float:
        return sum(l.net_delta() for l in self.legs.values())

    # ── the tick path ──────────────────────────────────────────────────────
    def on_tick(self, token: int, bid: float, ask: float, bid_qty: int,
                ask_qty: int, last: float, ts_ns: int) -> None:
        t0 = now_ns()
        leg = self._by_token.get(token)
        if leg is None:
            return
        book = leg.books[token]
        book.update(bid, ask, bid_qty, ask_qty, last, ts_ns)
        self._ticks += 1

        if token == leg.u_token:
            leg.guard.push(ts_ns, book.micro)
            return

        u = leg.books[leg.u_token]
        if not u.fresh:
            return
        spot = u.micro
        sig = leg.signals.get(token)
        if sig is None:
            return

        # exits are checked in every phase, including FLATTEN. A position that
        # can only be opened while ACTIVE must still be closable after.
        pos = leg.positions.get(token)
        if pos is not None:
            theo = sig.last_theo
            if theo <= 0.0:
                sig.evaluate(book, spot, leg.t_years)
                theo = sig.last_theo
            reason, px = leg.exits.evaluate(
                pos.side, pos.entry_px, pos.entry_edge, theo, book.bid,
                book.ask, leg.spec.tick, pos.age_ns())
            if self._phase is Phase.FLATTEN and reason is ExitReason.HOLD:
                reason, px = ExitReason.SESSION, (book.bid if pos.side > 0 else book.ask)
            if reason is not ExitReason.HOLD and px > 0.0:
                self._close(leg, pos, px, reason, ts_ns)
            return

        if self._phase is not Phase.ACTIVE:
            return
        if not leg.guard.calm(ts_ns, spot):
            return
        if not leg.positions.can_open(token):
            return

        side = sig.evaluate(book, spot, leg.t_years)
        self.lat_signal.record(now_ns() - t0)
        if side == NONE:
            return

        px = book.ask if side == BUY else book.bid
        lots = leg.positions.lots_per_strike
        verdict = self.risk.check(token, side, lots, px, leg.spec.lot,
                                  self.net_delta())
        if verdict is not Reject.OK:
            self._rec(ts_ns, leg.spec.symbol, token, side, px, sig.last_edge,
                      int(verdict), 0)
            return

        leg._deltas[token] = sig.last_delta
        leg.positions.open(Position(token, leg.spec.symbol, sig.strike,
                                    sig.is_call, side, lots, px, sig.last_theo,
                                    sig.last_edge, leg.spec.lot))
        self._pending.append((leg.spec.symbol, token, side, lots, px, "OPEN"))
        self._rec(ts_ns, leg.spec.symbol, token, side, px, sig.last_edge, 0, 0)
        self.lat_send.record(now_ns() - t0)

    def _close(self, leg: IndexLeg, pos: Position, px: float,
               reason: ExitReason, ts_ns: int) -> None:
        leg.positions.close(pos.token)
        leg._deltas.pop(pos.token, None)
        self.exit_counts[reason] += 1
        pnl = pos.mtm(px)
        self.risk.realised += pnl
        s = pos.symbol
        self.pnl_by_symbol[s] = self.pnl_by_symbol.get(s, 0.0) + pnl
        self.trades_by_symbol[s] = self.trades_by_symbol.get(s, 0) + 1
        self._pending.append((leg.spec.symbol, pos.token, -pos.side, pos.lots,
                              px, reason.name))
        self._rec(ts_ns, leg.spec.symbol, pos.token, -pos.side, px, pnl, 0,
                  int(reason))

    def _rec(self, ts_ns: int, sym: str, token: int, side: int, px: float,
             val: float, verdict: int, reason: int) -> None:
        self._log[self._log_i] = (ts_ns, sym, token, side, px, val, verdict, reason)
        self._log_i = (self._log_i + 1) % len(self._log)
        self._log_n += 1

    def drain(self) -> list[tuple]:
        if not self._pending:
            return []
        out, self._pending = self._pending, []
        return out

    # ── reporting ──────────────────────────────────────────────────────────
    def stats(self) -> str:
        legs = "  ".join(
            f"{s}:{l.positions.count()}/{l.positions.max_strikes}"
            for s, l in self.legs.items())
        ex = " ".join(f"{ExitReason(i).name}={c}"
                      for i, c in enumerate(self.exit_counts) if c)
        per = "\n".join(
            f"    {k:<11}{self.trades_by_symbol.get(k,0):>5} trades  "
            f"{self.pnl_by_symbol.get(k,0.0):>+12,.0f}"
            for k in self.legs)
        return (f"ticks={self._ticks} events={self._log_n} open[{legs}] "
                f"net_delta={self.net_delta():+.0f}\n"
                f"  {self.risk.summary()}\n"
                f"  exits[{ex or 'none'}]\n"
                f"  {self.lat_signal.summary()}\n"
                f"  {self.lat_send.summary()}\n"
                f"  per index:\n{per}")
