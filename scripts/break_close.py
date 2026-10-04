"""Close beyond the prior candle's range, in the direction that candle closed.

The pattern as given, on hourly bars:

  SHORT   the main candle closes RED (close < open).
          the NEXT candle closes BELOW the main candle's LOW  -> short at that
          close. Stop = the main candle's HIGH.
  LONG    the main candle closes GREEN.
          the NEXT candle closes ABOVE the main candle's HIGH -> long at that
          close. Stop = the main candle's LOW.

Two things about the geometry are worth stating before any number appears,
because they are what separate this from the inside-bar pattern tested earlier
in this repo:

  * the stop is WIDE. Entry is beyond one end of the main candle and the stop
    is at the other end, so the risk is the main candle's whole range plus the
    distance the confirming candle travelled past it. The inside-bar pattern
    failed because its stop sat inside ordinary noise; this one cannot fail
    that way.
  * the entry is a CLOSE, not a touch. The confirming candle must close
    beyond the level, so there is no "wick through and reverse" fill, and no
    gap-fill assumption is needed. Entry is at a price that printed.

Both of those are in the pattern's favour, and both are why it deserves a run
rather than an argument.

`arm()` produces the armed-trigger lists that `inside_bar_short.execute` already
knows how to run, so the exit model, the cost handling and the pessimistic
tie-break (a bar touching both stop and target is scored a loss) are the same
code that every other study in this repo used.
"""
from __future__ import annotations
import os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from inside_bar_short import execute, stats                    # noqa: F401


def arm(bars, side="short", require_colour=True, body_min=0.0):
    """Armed-trigger list for `execute`.

    The armed dict's field names come from the inside-bar module, where
    `ref_high` means "the price the stop sits at". For a long that is the main
    candle's LOW, which is why the name reads oddly here and is correct.

    require_colour=False drops the red/green condition and keeps only the
    break, which is the ablation that says whether the candle's colour does
    any work at all.

    body_min requires |close-open| to be at least this fraction of the main
    candle's range -- "closes red" with conviction rather than by a tick.
    """
    n = len(bars)
    out = [None] * n
    for i in range(n):
        m = bars[i]
        rng = m["h"] - m["l"]
        if rng <= 0:
            continue
        if body_min > 0.0 and abs(m["c"] - m["o"]) < body_min * rng:
            continue
        if require_colour:
            if side == "short" and not (m["c"] < m["o"]):
                continue
            if side == "long" and not (m["c"] > m["o"]):
                continue
        if side == "short":
            trigger, stop = m["l"], m["h"]
        else:
            trigger, stop = m["h"], m["l"]
        out[i] = dict(i=i, trigger=trigger, inside_high=stop,
                      ref_high=stop, ref_low=trigger)
    return out


def run(bars, side="short", rr=2.0, cost_bps=1.0, max_hold=24,
        require_colour=True, body_min=0.0, stop_mult=None):
    """One position at a time; the trigger is live for exactly one candle."""
    a = arm(bars, side, require_colour, body_min)
    kw = dict(rr=rr, valid_bars=1, on_close=True, cost_bps=cost_bps,
              max_hold=max_hold, side=side)
    if stop_mult is None:
        kw["stop_at"] = "ref"
    else:
        kw["stop_at"] = "mult"
        kw["stop_mult"] = stop_mult
    return execute(bars, a, **kw)
