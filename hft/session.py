"""Session phases for a strategy that runs all day.

There is no trading window in the strategy sense -- the bot scalps quote lag
whenever lag exists, which is whenever the market is open. What remains is the
structure the exchange imposes.

  PRE      before the open. No orders.
  WARMUP   books filling, IV not yet solved. No orders.
  ACTIVE   armed, for as long as the market is open.
  FLATTEN  before the close. Cancel, square off, stay down.
  DONE

The flatten phase is not optional and is not a preference. An intraday option
position carried past the bell becomes an overnight gap position, and Indian
brokers auto-square intraday books around 15:15-15:25 anyway -- at their price,
not yours. Squaring off deliberately, early, is strictly better than being
squared off.

The deadline is checked on every tick rather than scheduled, because a scheduled
callback that a busy loop starves is how a position survives the bell it was
supposed to die at.
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


class TradingDay:
    """Market hours with a mandatory squaring-off phase before the close."""

    __slots__ = ("open_t", "close_t", "flat_t", "warmup_s")

    def __init__(self, open_hhmm: tuple[int, int] = (9, 15),
                 flat_hhmm: tuple[int, int] = (15, 10),
                 close_hhmm: tuple[int, int] = (15, 30),
                 warmup_s: int = 20) -> None:
        self.open_t = dtime(*open_hhmm)
        self.flat_t = dtime(*flat_hhmm)
        self.close_t = dtime(*close_hhmm)
        self.warmup_s = warmup_s

    def phase(self, now: datetime | None = None) -> Phase:
        now = now or datetime.now(IST)
        if now.weekday() >= 5:
            return Phase.DONE
        t = now.time()
        if t < self.open_t:
            return Phase.PRE
        if t >= self.close_t:
            return Phase.DONE
        if t >= self.flat_t:
            return Phase.FLATTEN
        anchor = now.replace(hour=self.open_t.hour, minute=self.open_t.minute,
                             second=0, microsecond=0)
        if (now - anchor).total_seconds() < self.warmup_s:
            return Phase.WARMUP
        return Phase.ACTIVE

    def seconds_to_flat(self, now: datetime | None = None) -> float:
        now = now or datetime.now(IST)
        f = now.replace(hour=self.flat_t.hour, minute=self.flat_t.minute,
                        second=0, microsecond=0)
        return max(0.0, (f - now).total_seconds())


# kept so existing imports do not break
SessionWindow = TradingDay
