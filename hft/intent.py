"""The human's half: a direction call, and the rules that keep it honest.

The split this file exists to enforce is the one thing measured repeatedly in
this project: every strategy tested failed at DIRECTION, and none failed at
execution. Tick-to-signal came in at 15.6us while fourteen pre-registered
signals scored at or below a random entry. So the human supplies side and size;
the machine supplies everything else -- timing, order type, price, slicing,
exits. Neither is allowed into the other's job.

Four rules, each from a way this goes wrong in practice:

  EXPIRY      A direction call made at 09:20 is not still true at 09:45, but a
              machine will happily keep working it. Every intent carries a TTL
              and stops adding when it lapses. What is already filled is held
              or flattened by policy, never silently added to.

  FLIP VIA FLAT  LONG to SHORT is not one instruction, it is two. Reduce to
              flat, then build the other side. Netting them means a moment
              where the position is neither and the risk is both.

  FLIP COOLDOWN  The most dangerous input a human gives is a reversal, and the
              most common reason is panic rather than information. A flip
              inside the cooldown is refused, not queued -- a queued reversal
              executes exactly when the person has changed their mind again.

  RE-ARM      A kill is one-way. Nothing resumes without a fresh, explicit
              instruction, because an automatic resume is the machine deciding
              the human's job.
"""
from __future__ import annotations
from enum import IntEnum
from .clock import now_ns


class Side(IntEnum):
    SHORT = -1
    FLAT = 0
    LONG = 1


class IState(IntEnum):
    WORKING = 0
    COMPLETE = 1
    EXPIRED = 2
    CANCELLED = 3
    REDUCING = 4          # flipping: draining the old side before the new one


class Reject(IntEnum):
    OK = 0
    NOT_ARMED = 1
    KILLED = 2
    FLIP_COOLDOWN = 3
    SAME_SIDE_ACTIVE = 4
    BAD_SIZE = 5
    SESSION_CLOSED = 6


class Intent:
    """One direction call. Immutable in side and target; mutable in progress."""

    __slots__ = ("side", "target", "filled", "urgency", "created_ns", "ttl_ns",
                 "state", "arrival_px", "note", "_notional", "_lots")

    def __init__(self, side: Side, target: int, urgency: float = 0.5,
                 ttl_s: float = 300.0, arrival_px: float = 0.0,
                 note: str = "") -> None:
        self.side = side
        self.target = int(target)
        self.filled = 0
        # urgency 0 = work it patiently and passively, 1 = get it done now.
        # It is the ONE execution dial the human is given, because it encodes
        # information only they have: how fast they think they are right.
        self.urgency = max(0.0, min(1.0, urgency))
        self.created_ns = now_ns()
        self.ttl_ns = int(ttl_s * 1e9)
        self.state = IState.WORKING
        self.arrival_px = arrival_px     # for implementation shortfall
        self.note = note
        self._notional = 0.0             # this intent's own fills, only
        self._lots = 0

    # ── progress ───────────────────────────────────────────────────────────
    @property
    def remaining(self) -> int:
        return max(0, self.target - self.filled)

    def age_ns(self) -> int:
        return now_ns() - self.created_ns

    def expired(self) -> bool:
        return self.age_ns() > self.ttl_ns

    def time_frac(self) -> float:
        """0 at creation, 1 at expiry. Drives the patient-to-urgent ramp."""
        if self.ttl_ns <= 0:
            return 1.0
        return min(1.0, self.age_ns() / self.ttl_ns)

    def on_fill(self, lots: int, px: float = 0.0) -> None:
        self.filled += lots
        if px > 0.0:
            self._notional += px * lots
            self._lots += lots
        if self.filled >= self.target:
            self.state = IState.COMPLETE

    def avg_fill(self) -> float:
        return self._notional / self._lots if self._lots else 0.0

    def tick(self) -> None:
        if self.state is IState.WORKING and self.expired():
            self.state = IState.EXPIRED

    def summary(self) -> str:
        return (f"{self.side.name} {self.filled}/{self.target} "
                f"u={self.urgency:.1f} {self.state.name} "
                f"t={self.age_ns()/1e9:.0f}/{self.ttl_ns/1e9:.0f}s")


class IntentBook:
    """Accepts or refuses direction calls, and owns the flip rules."""

    __slots__ = ("armed", "killed", "current", "last_flip_ns", "flip_cooldown_ns",
                 "on_expiry_flatten", "history", "reject_counts", "last")

    def __init__(self, flip_cooldown_s: float = 10.0,
                 on_expiry_flatten: bool = False) -> None:
        self.armed = False
        self.killed = False
        self.current: Intent | None = None
        self.last_flip_ns = 0
        self.flip_cooldown_ns = int(flip_cooldown_s * 1e9)
        # On expiry: HOLD what is filled by default. Auto-flattening an expired
        # intent turns a stale opinion into a market order at the worst
        # possible moment -- whenever the human stopped paying attention.
        self.on_expiry_flatten = on_expiry_flatten
        self.history: list[Intent] = []
        self.last: Intent | None = None      # kept for the scorecard
        self.reject_counts = [0] * len(Reject)

    def arm(self) -> None:
        if not self.killed:
            self.armed = True

    def kill(self) -> None:
        """One way. Cancels the working intent; does not touch the position --
        flattening is a separate, deliberate instruction."""
        self.killed = True
        self.armed = False
        if self.current is not None:
            self.current.state = IState.CANCELLED

    def re_arm(self) -> bool:
        """Only a human clears a kill, and only explicitly."""
        self.killed = False
        self.armed = True
        return True

    def _rej(self, r: Reject) -> Reject:
        self.reject_counts[r] += 1
        return r

    def submit(self, side: Side, target: int, urgency: float = 0.5,
               ttl_s: float = 300.0, arrival_px: float = 0.0,
               net_position: int = 0, note: str = "") -> Reject:
        if self.killed:
            return self._rej(Reject.KILLED)
        if not self.armed:
            return self._rej(Reject.NOT_ARMED)
        if target <= 0 and side is not Side.FLAT:
            return self._rej(Reject.BAD_SIZE)

        cur = self.current
        if cur is not None and cur.state is IState.WORKING:
            if cur.side is side:
                return self._rej(Reject.SAME_SIDE_ACTIVE)

        # a reversal while holding the other side
        flipping = (side is not Side.FLAT and net_position != 0 and
                    (net_position > 0) != (side is Side.LONG))
        if flipping:
            t = now_ns()
            if t - self.last_flip_ns < self.flip_cooldown_ns:
                return self._rej(Reject.FLIP_COOLDOWN)
            self.last_flip_ns = t

        if cur is not None:
            cur.state = IState.CANCELLED
            self.history.append(cur)
        self.current = Intent(side, target, urgency, ttl_s, arrival_px, note)
        # A flip reduces first. The execution layer reads REDUCING and closes
        # the existing side before it builds anything new.
        if flipping:
            self.current.state = IState.REDUCING
        return Reject.OK

    def tick(self) -> None:
        c = self.current
        if c is None:
            return
        was = c.state
        c.tick()
        # Archive on the TRANSITION only. Appending while the state persists
        # grows the history once per tick, which is how a 15-second intent
        # came back reporting 1,891 completed calls.
        if was is IState.WORKING and c.state is IState.EXPIRED:
            self.history.append(c)
            self.last = c
        elif c.state in (IState.COMPLETE, IState.CANCELLED):
            self.history.append(c)
            self.last = c
            self.current = None

    def working(self) -> Intent | None:
        c = self.current
        if c is not None and c.state in (IState.WORKING, IState.REDUCING):
            return c
        return None

    def summary(self) -> str:
        c = self.current.summary() if self.current else "none"
        r = " ".join(f"{Reject(i).name}={v}"
                     for i, v in enumerate(self.reject_counts) if v and i)
        return (f"armed={self.armed} killed={self.killed} intent[{c}] "
                f"done={len(self.history)} rejects[{r or 'none'}]")
