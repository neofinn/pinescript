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
from .costs import CostModel, BY_VENUE
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
                 "guard", "t_years", "_deltas", "pending", "cost")

    def __init__(self, spec: Spec, u_token: int, signals: list[OptionSignal],
                 t_years: float, lots_per_strike: int, max_strikes: int,
                 cost: CostModel | None = None) -> None:
        self.spec = spec
        # NSE and BSE publish different transaction charges, and SENSEX is on
        # BSE, so the cost model follows the venue rather than the strategy.
        self.cost = cost if cost is not None else BY_VENUE[spec.venue]
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
        # Tokens with an order out but no fill yet. Without this the same stale
        # quote fires again on the next tick and you end up with N orders
        # chasing one opportunity.
        self.pending: dict[int, tuple] = {}

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
        self.costs = 0.0
        self.gross = 0.0
        # premium actually traded, so break-even (a % of premium) can be
        # compared against what the trades were worth rather than assumed
        self.premium_sum = 0.0
        self.premium_n = 0
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
        if not leg.positions.can_open(token) or token in leg.pending:
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

        # An order is INTENT. The position opens when the venue says it filled,
        # not when we send. Opening on submission books trades that never
        # happened -- with passive quotes, where the great majority are
        # cancelled unfilled, that is the difference between a result and a
        # work of fiction.
        leg._deltas[token] = sig.last_delta
        leg.pending[token] = (side, lots, sig.last_theo, sig.last_edge,
                              sig.strike, sig.is_call)
        self._pending.append((leg.spec.symbol, token, side, lots, px, "OPEN"))
        self._rec(ts_ns, leg.spec.symbol, token, side, px, sig.last_edge, 0, 0)
        self.lat_send.record(now_ns() - t0)

    def on_fill(self, symbol: str, token: int, side: int, lots: int,
                px: float) -> None:
        """The venue filled. Only now does a position exist."""
        leg = self.legs.get(symbol)
        if leg is None:
            return
        meta = leg.pending.pop(token, None)
        pos = leg.positions.get(token)
        if pos is not None:                       # closing fill
            return
        if meta is None:
            return
        _side, _lots, theo, edge, strike, is_call = meta
        leg.positions.open(Position(token, symbol, strike, is_call, side, lots,
                                    px, theo, edge, leg.spec.lot))

    def on_no_fill(self, symbol: str, token: int) -> None:
        """Expired, cancelled or rejected. Clear the intent so the contract can
        be quoted again rather than being locked out for the session."""
        leg = self.legs.get(symbol)
        if leg is not None:
            leg.pending.pop(token, None)
            leg._deltas.pop(token, None)

    def _close(self, leg: IndexLeg, pos: Position, px: float,
               reason: ExitReason, ts_ns: int) -> None:
        leg.positions.close(pos.token)
        leg._deltas.pop(pos.token, None)
        self.exit_counts[reason] += 1
        gross = pos.mtm(px)

        # Both legs are charged here, off the prices they actually traded at,
        # because the cost is a fraction of premium rather than a flat per-lot
        # fee -- an entry at 150 and an exit at 151 do not cost the same. STT
        # lands on whichever leg is the sell, which is what leg_cost's sign
        # argument decides.
        c = leg.cost
        lot = leg.spec.lot
        cost = (c.leg_cost(pos.entry_px, lot, pos.lots, pos.side)
                + c.leg_cost(px, lot, pos.lots, -pos.side))
        self.costs += cost
        self.gross += gross
        self.premium_sum += pos.entry_px
        self.premium_n += 1
        pnl = gross - cost
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
                f"  gross {self.gross:+,.0f}  costs {self.costs:,.0f}  "
                f"net {self.gross - self.costs:+,.0f}\n"
                f"  {self.risk.summary()}\n"
                f"  exits[{ex or 'none'}]\n"
                f"  {self.lat_signal.summary()}\n"
                f"  {self.lat_send.summary()}\n"
                f"  per index:\n{per}")
