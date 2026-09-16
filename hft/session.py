"""Time-boxing. The bot is armed for a defined window and dead outside it.

Three phases rather than two, because the first seconds after 9:15:00 are not
tradeable: NSE runs a pre-open call auction to 9:08 and the continuous session
opens at 9:15, but the book in the first moments is thin and quotes are being
established rather than quoted. Trading that is not an edge, it is paying to
discover the price for everyone else.

  WARMUP   collect ticks, build books, solve IV. No orders.
  ACTIVE   armed. Orders permitted.
  FLATTEN  hard stop. Cancel everything, close everything, disarm, stay down.

The flatten deadline is absolute and checked on every tick, not scheduled. A
scheduled callback that a busy loop starves is how a position survives past the
window it was supposed to die in.
"""
from __future__ import annotations
from datetime import datetime, time as dtime, timedelta, timezone
from enum import IntEnum

IST = timezone(timedelta(hours=5, minutes=30))


class Phase(IntEnum):
    PRE = 0
    WARMUP = 1
    ACTIVE = 2
    FLATTEN = 3
    DONE = 4


class SessionWindow:
    __slots__ = ("open_t", "warmup_s", "active_s", "flatten_s", "_phase", "_date")

    def __init__(self, open_hhmm: tuple[int, int] = (9, 15), warmup_s: int = 20,
                 active_s: int = 300, flatten_s: int = 60) -> None:
        self.open_t = dtime(open_hhmm[0], open_hhmm[1], 0)
        self.warmup_s = warmup_s
        self.active_s = active_s
        self.flatten_s = flatten_s
        self._phase = Phase.PRE
        self._date = None

    def _anchor(self, now: datetime) -> datetime:
        return now.replace(hour=self.open_t.hour, minute=self.open_t.minute,
                           second=0, microsecond=0)

    def phase(self, now: datetime | None = None) -> Phase:
        now = now or datetime.now(IST)
        if now.weekday() >= 5:
            return Phase.DONE
        a = self._anchor(now)
        if now < a:
            return Phase.PRE
        elapsed = (now - a).total_seconds()
        if elapsed < self.warmup_s:
            return Phase.WARMUP
        if elapsed < self.warmup_s + self.active_s:
            return Phase.ACTIVE
        if elapsed < self.warmup_s + self.active_s + self.flatten_s:
            return Phase.FLATTEN
        return Phase.DONE

    def seconds_left(self, now: datetime | None = None) -> float:
        now = now or datetime.now(IST)
        a = self._anchor(now)
        end = a + timedelta(seconds=self.warmup_s + self.active_s)
        return max(0.0, (end - now).total_seconds())
