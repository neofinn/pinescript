"""Semi-automatic engine: human direction, machine execution.

The boundary is enforced, not merely documented. The human's inputs are side,
size, urgency and a TTL. Nothing else reaches this engine from outside, and the
engine never invents a direction of its own -- with no working intent it sits
flat and does nothing, however tempting the book looks.

Positions open on FILL, never on submission. That distinction cost this project
a whole set of results once already: booking a position when an order is sent
reports trades that never happened, and with passive orders, where most are
cancelled unfilled, it is the difference between a measurement and a fiction.
"""
from __future__ import annotations
from .book import Book as OrderBook
from .clock import now_ns, LatencyHistogram
from .execution import Executor, Act, shortfall_bps
from .intent import IntentBook, Intent, IState, Side, Reject
from .orders import OrdType, OrdState, OrderStore
from .risk import RiskGate, Reject as RRej
from .session import Phase


class SemiAuto:
    def __init__(self, token: int, tick: float, lot: int, risk: RiskGate,
                 execu: Executor, intents: IntentBook,
                 flatten_on_session_end: bool = True) -> None:
        self.token = token
        self.tick = tick
        self.lot = lot
        self.risk = risk
        self.ex = execu
        self.intents = intents
        self.book = OrderBook(token)
        self.store = OrderStore()
        self.flatten_on_session_end = flatten_on_session_end

        self.position = 0                # in lots, signed
        self.avg_px = 0.0
        self.realised = 0.0
        self._fill_notional = 0.0
        self._fill_lots = 0
        self._phase = Phase.PRE
        self._recent_lots = 0
        self._last_vol_ns = 0
        self.pending: list = []
        self.lat = LatencyHistogram("tick->plan")
        self.blocked = [0] * len(RRej)

    # ── lifecycle ──────────────────────────────────────────────────────────
    def set_phase(self, p: Phase) -> None:
        self._phase = p

    def arm(self) -> None:
        self.intents.arm(); self.risk.arm()

    def kill(self, why: str = "manual") -> None:
        """Stops new risk. Does NOT flatten -- squaring off is its own
        instruction, because an automatic flatten on a kill turns a safety
        control into a market order at the worst moment."""
        self.intents.kill(); self.risk.kill(why)
        for o in self.store.all_live():
            o.state = OrdState.CANCELLED

    # ── market data ────────────────────────────────────────────────────────
    def on_tick(self, token: int, bid: float, ask: float, bid_qty: int,
                ask_qty: int, last: float, ts_ns: int) -> None:
        if token != self.token:
            return
        t0 = now_ns()
        self.book.update(bid, ask, bid_qty, ask_qty, last, ts_ns)
        # rolling proxy for traded size, used only for the participation cap
        self._recent_lots = max(1, (bid_qty + ask_qty) // 4)

        self.intents.tick()
        it = self.intents.working()

        if self._phase is Phase.FLATTEN and self.position != 0:
            self._emit(-1 if self.position > 0 else 1, abs(self.position),
                       bid if self.position > 0 else ask, OrdType.MARKETABLE,
                       "session flatten")
            return
        if it is None:
            return
        if self._phase is not Phase.ACTIVE:
            return

        age = None
        live = [o for o in self.store.all_live() if o.token == self.token]
        if live:
            age = min(o.age_ns() for o in live) / 1e6

        p = self.ex.plan(it, self.book.bid, self.book.ask, bid_qty, ask_qty,
                         self._recent_lots, age, self.position)
        self.lat.record(now_ns() - t0)

        if p.act in (Act.WAIT, Act.DONE, Act.STOP):
            return
        # a fresh decision supersedes a stale resting quote
        for o in live:
            o.state = OrdState.CANCELLED
        self._emit(p.side, p.lots, p.price, p.otype, p.why)

    def _emit(self, side: int, lots: int, price: float, otype: OrdType,
              why: str) -> None:
        v = self.risk.check(self.token, side, lots, price, self.lot,
                            self.position * self.lot)
        if v is not RRej.OK:
            self.blocked[v] += 1
            return
        o = self.store.new(self.token, "SEMI", side, lots, price, otype)
        self.pending.append((o, why))

    def drain(self):
        out, self.pending = self.pending, []
        return out

    # ── venue callbacks ────────────────────────────────────────────────────
    def on_fill(self, side: int, lots: int, px: float) -> None:
        """The only place a position changes."""
        prev = self.position
        self.position += side * lots
        self._fill_notional += px * lots
        self._fill_lots += lots

        if prev != 0 and (prev > 0) != (self.position > 0) or \
           (prev != 0 and self.position == 0):
            closed = min(abs(prev), lots)
            self.realised += (px - self.avg_px) * (1 if prev > 0 else -1) \
                * closed * self.lot
        if self.position == 0:
            self.avg_px = 0.0
        elif prev == 0 or (prev > 0) == (self.position > 0):
            tot = abs(prev) + lots
            self.avg_px = (self.avg_px * abs(prev) + px * lots) / tot if tot else px
        else:
            self.avg_px = px

        it = self.intents.working()
        if it is not None:
            if it.state is IState.REDUCING:
                if self.position == 0:
                    it.state = IState.WORKING     # cleared; now build the side
            else:
                it.on_fill(lots, px)
        self.risk.on_fill(self.token, side, lots, px, self.lot)

    def on_no_fill(self, o) -> None:
        pass

    # ── reporting ──────────────────────────────────────────────────────────
    def avg_fill(self) -> float:
        return self._fill_notional / self._fill_lots if self._fill_lots else 0.0

    def status(self) -> str:
        it = self.intents.current or self.intents.last
        sf = shortfall_bps(it, self.avg_fill()) if it else 0.0
        blk = " ".join(f"{RRej(i).name}={v}"
                       for i, v in enumerate(self.blocked) if v and i)
        return (f"pos {self.position:+d} @ {self.avg_px:.2f}  "
                f"realised {self.realised:+,.0f}\n"
                f"  {self.intents.summary()}\n"
                f"  {self.ex.summary()}   shortfall {sf:+.1f} bps\n"
                f"  risk blocks[{blk or 'none'}]\n"
                f"  {self.lat.summary()}")
