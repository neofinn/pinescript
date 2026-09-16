# Opening-window options HFT

Runs the whole session. There is no trading window: the strategy scalps quote
lag, and lag exists whenever the market is open. What bounds the day is a profit
goal, a loss limit, and the bell.

## The strategy

An index option's fair value is a deterministic function of the underlying. The
underlying's book updates continuously; each option's quote updates when its
market maker gets round to it. In the first minutes of a session — underlying
moving fastest, quote traffic heaviest — that gap is at its widest. The trade is
to compute fair value faster than the option quote reprices and take the stale
side.

Two guards matter more than the signal:

- **Stale and wide look identical** to a naive edge calculation. The edge must
  clear a fraction of the spread, not just an absolute number of ticks, or you
  spend the window "finding" contracts nobody is quoting tightly.
- **Book age.** A quote nobody has touched for 200ms is not an opportunity; it
  is a quote that gets pulled the moment you take it. That is adverse selection
  and it is the main way this loses money.

## Layout

| file | what it does |
|---|---|
| `clock.py` | monotonic ns timing, pre-allocated latency histogram |
| `book.py` | top of book, microprice, imbalance |
| `pricing.py` | Black-Scholes via `erf`, bisection IV off the hot path |
| `signals.py` | fair-value deviation, momentum guard |
| `risk.py` | pre-trade gate, fails closed, every rejection counted |
| `session.py` | market-hours phases, mandatory squaring-off before the close |
| `engine.py` | the tick path |
| `adapters/base.py` | Feed and Gateway protocols — implement for your venue |
| `adapters/sim.py` | simulator that reproduces quote lag and pessimistic fills |

## Run it

```bash
python -m hft.main --sim --seconds 8          # one run
python -m hft.main --sweep --seconds 6        # lag x fill-probability grid
```

Read the latency histogram first. If `tick->signal` is not comfortably inside
your quote-lag assumption, the strategy cannot take the lag it is aiming at and
no amount of tuning the edge threshold fixes that.

## How the day ends

Three ways, and they are not the same:

- **Profit goal → disarm.** Stops opening new risk; the open book can still be
  closed. Set with `--goal-pct`.
- **Loss limit → kill.** One way. Set with `--loss-pct`.
- **The bell → flatten.** Not optional. An intraday option carried past the
  close becomes an overnight gap position, and Indian brokers auto-square
  intraday books around 15:15-15:25 at their price. Squaring off deliberately
  at 15:10 is strictly better than being squared off.

State checks sit above the throttles in the risk gate on purpose. A goal
reported as a rate-limit rejection is a goal you never learn you hit.

## Hot path rules

- No allocation. Books, signals and the histogram are built once and mutated.
- No logging. Records go to a pre-sized ring, drained after the window.
- No awaits. Orders queue in the tick path; a separate loop ships them, so the
  broker round trip does not land on the latency of every following tick.
- `gc.freeze()` then `gc.disable()`, with a gen-0 pass on a slow cadence and
  only while flat. Disabling the collector for five minutes is free; leaving it
  off for six hours is not, because the drain list, the order layer and the feed
  all allocate even though the tick path does not.
- The signal log is a **ring**. Sized for a short window it would simply fill;
  over a full session a non-wrapping buffer stops recording minutes in and every
  later signal vanishes without a trace.

## What the simulator is and is not

It models the inefficiency being traded: each option quote follows its own fair
value with a lag and jitter. Set lag to zero and the strategy should go nearly
silent — that is the control, and a large result there means the edge
calculation is wrong.

**Its P&L numbers are not a backtest.** Risk limits bind within a handful of
orders, so a run produces single-digit trades and the rupee figures are noise.
The simulator is for exercising the path and measuring latency, not for deciding
whether the strategy makes money. `fill_prob` is the most optimistic assumption
in it: real adverse selection is not random, and the takes that fail are
disproportionately the ones you wanted.

## Before this touches real money

1. Implement `Feed` and `Gateway` for your venue.
2. Replay a recorded session through the engine and reconcile every fill.
3. Run it armed with `max_pos_lots=1` for a week and read the reject counts.
4. Only then raise limits.

Python is not the right language for a sub-millisecond tick-to-trade path —
the GIL and the allocator both get in the way. What it is good for is settling
the logic, the risk model and the instrument plumbing, which is the slow part
and is language-independent. The feed-callback-to-order-send path is a few
hundred lines to port once the logic is fixed.
