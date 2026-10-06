"""The machine's half: working a direction call without leaking the edge.

The human has said which way and how much. Everything from here is execution,
and execution has exactly one job -- get the size done near the price that was
on the screen when the decision was made. That reference price is the ARRIVAL
PRICE, and the gap to it is implementation shortfall. It is the only honest
scorecard for this layer, because a fill is not good because it was fast or
because it was passive; it is good because it was close to the decision.

Four controls, and the third is the one that matters most:

  AGGRESSION RAMP   Start at the human's urgency and ramp toward 1.0 as the TTL
                    burns down. Patient early, decisive late. A flat aggression
                    either crosses spreads it did not need to or never finishes.

  SLICING           Never show the whole size. Child clips are capped both
                    absolutely and as a share of traded volume, because being a
                    large fraction of the tape moves the price you are trying
                    to get.

  NO-CHASE          Never pay worse than arrival ± max_slip. This is the
                    control that stops an algorithm turning a good call into a
                    bad fill: without it, a ramping aggression will follow
                    price wherever it goes and buy the top of the very move it
                    was trying to catch. When the limit binds, the algo STOPS.
                    Not filling is a legitimate outcome; chasing is not.

  RE-QUOTE          A resting order the market has walked away from is not
                    working, it is an option you wrote for free. Age it out and
                    re-post at the new touch.
"""
from __future__ import annotations
from enum import IntEnum
from .clock import now_ns
from .intent import Intent, IState, Side
from .orders import OrdType


class Act(IntEnum):
    WAIT = 0
    POST = 1          # rest passively
    CROSS = 2         # marketable limit, capped at the touch
    STOP = 3          # no-chase limit binds; do nothing further
    DONE = 4


class Plan:
    __slots__ = ("act", "side", "lots", "price", "otype", "why")

    def __init__(self, act, side=0, lots=0, price=0.0, otype=OrdType.PASSIVE,
                 why=""):
        self.act = act
        self.side = side
        self.lots = lots
        self.price = price
        self.otype = otype
        self.why = why

    def __repr__(self):
        return (f"{self.act.name} {self.side:+d} {self.lots}@{self.price:.2f} "
                f"{self.otype.name} ({self.why})")


class Executor:
    __slots__ = ("tick", "max_clip", "pov", "cross_at", "improve_ticks",
                 "max_slip_ticks", "requote_ms", "min_book_lots",
                 "sent", "stopped", "crossed", "posted")

    def __init__(self, tick: float, max_clip: int = 5, pov: float = 0.10,
                 cross_at: float = 0.65, improve_ticks: float = 1.0,
                 max_slip_ticks: float = 8.0, requote_ms: float = 400.0,
                 min_book_lots: int = 1) -> None:
        self.tick = tick
        self.max_clip = max_clip
        self.pov = pov                    # share of traded volume we may be
        self.cross_at = cross_at          # aggression above this -> take
        self.improve_ticks = improve_ticks
        self.max_slip_ticks = max_slip_ticks
        self.requote_ms = requote_ms
        self.min_book_lots = min_book_lots
        self.sent = 0
        self.stopped = 0
        self.crossed = 0
        self.posted = 0

    # ── the ramp ───────────────────────────────────────────────────────────
    def aggression(self, it: Intent) -> float:
        """Urgency at the start, 1.0 by expiry. Squared so the push comes
        late rather than bleeding spread across the whole window."""
        f = it.time_frac()
        return min(1.0, it.urgency + (1.0 - it.urgency) * f * f)

    # ── the no-chase band ──────────────────────────────────────────────────
    def limit_band(self, it: Intent) -> tuple[float, float]:
        """Worst price we will accept, on each side of arrival."""
        s = self.max_slip_ticks * self.tick
        return it.arrival_px - s, it.arrival_px + s

    def plan(self, it: Intent, bid: float, ask: float, bid_lots: int,
             ask_lots: int, recent_lots: int, resting_age_ms: float | None,
             position: int) -> Plan:
        """One decision. Called per tick; must be cheap and must not allocate
        anything it does not need."""
        if it.state is IState.COMPLETE:
            return Plan(Act.DONE, why="target met")
        if it.state is IState.EXPIRED:
            # not a no-chase bind, so it is not counted as one: the counter
            # exists to tell you the band is too tight, and an expired intent
            # would otherwise swamp it
            return Plan(Act.STOP, why="intent expired")
        if bid <= 0.0 or ask <= bid:
            return Plan(Act.WAIT, why="no book")

        # A flip drains the old side first. Size is whatever is still on, and
        # the direction is the opposite of the position, not of the intent.
        if it.state is IState.REDUCING and position != 0:
            side = -1 if position > 0 else 1
            lots = min(abs(position), self.max_clip)
            px = bid if side < 0 else ask
            self.crossed += 1
            self.sent += 1
            return Plan(Act.CROSS, side, lots, px, OrdType.MARKETABLE,
                        "reducing before flip")

        rem = it.remaining
        if rem <= 0:
            return Plan(Act.DONE, why="target met")

        side = 1 if it.side is Side.LONG else -1
        lo, hi = self.limit_band(it)

        # No-chase. Checked BEFORE any sizing, because a clip that cannot be
        # priced inside the band is not a smaller clip, it is no order.
        if side > 0 and ask > hi and self.aggression(it) >= self.cross_at:
            self.stopped += 1
            return Plan(Act.STOP, why=f"ask {ask:.2f} beyond arrival+slip {hi:.2f}")
        if side < 0 and bid < lo and self.aggression(it) >= self.cross_at:
            self.stopped += 1
            return Plan(Act.STOP, why=f"bid {bid:.2f} beyond arrival-slip {lo:.2f}")

        # participation: never more of the tape than pov
        cap = max(1, int(recent_lots * self.pov)) if recent_lots > 0 else 1
        lots = max(1, min(rem, self.max_clip, cap))

        agg = self.aggression(it)
        if agg >= self.cross_at:
            px = ask if side > 0 else bid
            # cap at the band even when crossing: fill at our price or better
            px = min(px, hi) if side > 0 else max(px, lo)
            avail = ask_lots if side > 0 else bid_lots
            if avail < self.min_book_lots:
                return Plan(Act.WAIT, why="touch too thin to take")
            lots = max(1, min(lots, avail))
            self.crossed += 1
            self.sent += 1
            return Plan(Act.CROSS, side, lots, px, OrdType.MARKETABLE,
                        f"agg {agg:.2f}")

        # patient: post inside the touch, never through the band
        if side > 0:
            px = min(bid + self.improve_ticks * self.tick, hi)
            if px >= ask:
                px = ask - self.tick        # stay passive, never cross by post
        else:
            px = max(ask - self.improve_ticks * self.tick, lo)
            if px <= bid:
                px = bid + self.tick
        if resting_age_ms is not None and resting_age_ms < self.requote_ms:
            return Plan(Act.WAIT, why="resting order still fresh")
        self.posted += 1
        self.sent += 1
        return Plan(Act.POST, side, lots, px, OrdType.PASSIVE, f"agg {agg:.2f}")

    def summary(self) -> str:
        return (f"sent={self.sent} posted={self.posted} crossed={self.crossed} "
                f"no-chase stops={self.stopped}")


def shortfall_bps(it: Intent, avg_fill: float = 0.0) -> float:
    """Implementation shortfall against the decision price, in basis points.

    Positive means the fill was worse than the price on screen when the call
    was made. This is the number that tells a human whether their execution is
    giving back the edge they think they have.
    """
    # Prefer the intent's OWN average fill. Passing a session-wide average
    # measures slippage across unrelated orders.
    avg_fill = it.avg_fill() or avg_fill
    if it.arrival_px <= 0 or avg_fill <= 0 or it.filled <= 0:
        return 0.0
    sign = 1.0 if it.side is Side.LONG else -1.0
    return sign * (avg_fill - it.arrival_px) / it.arrival_px * 10_000.0
