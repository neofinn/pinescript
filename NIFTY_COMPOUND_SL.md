# Stop at 2 / 5 / 10% of compounded capital

Your diagnosis was right: the all-in run had no effective stop, so the option
simply went to zero. Capping the loss fixes that. **No cell reaches ₹0 in any
run below** — the wipeout is gone.

Two things had to be corrected first, both found because the previous table
contradicted its own promise (it printed a worst trade of −₹33,142 under a
₹10,000 cap):

- **costs sat outside the cap** — the trigger compared the option's
  mark-to-market against the limit and subtracted spread and statutory charges
  afterwards, so every capped trade breached by the cost;
- **only one exit path was floored** — the hard stop was floored but the
  profile stop, the target and the bell were not.

And the limit now **compounds**: X% of equity as it stands when the trade opens.

## M5 — 59 sessions, best cell (delta_breakout, expiry-day, RR 3.0, 46 trades)

| SL | final (stop always fills) | final (realistic fills) | maxDD | gapped through |
|---|---|---|---|---|
| **2%** | ₹9,09,900 (1.82×) | ₹8,76,478 (1.75×) | 12.0% | 15/46 |
| **5%** | ₹16,62,614 (3.33×) | ₹15,17,440 (3.03×) | 27.8% | 14/46 |
| **10%** | ₹26,48,585 (5.30×) | ₹21,98,284 (4.40×) | 48.6% | 14/46 |

## H1 — all of 2026, best cell (delta_breakout, weekly, RR 3.0, 35 trades)

| SL | final (stop always fills) | final (realistic fills) | maxDD | gapped through |
|---|---|---|---|---|
| **2%** | ₹40,60,513 (8.12×) | **₹9,77,371 (1.95×)** | 14.7% | **18/35** |
| **5%** | ₹1,55,79,726 (31.2×) | **₹32,18,976 (6.44×)** | 33.2% | **18/35** |
| **10%** | ₹4,53,21,793 (90.6×) | ₹1,52,81,102 (30.6×) | 56.4% | 17/35 |

## The stop is enforced by assumption, not by the market

`gapped through` counts trades whose real loss exceeded the limit before the
floor overrode it — **40–51% of all trades**. On those, a real fill is worse
than the stop price, because the option moved through the level inside the bar.

The right-hand column removes that assumption, and on H1 it removes most of the
result: **8.12× becomes 1.95×** at a 2% stop. The single worst trade goes from
−₹86,166 to −₹810,729.

That is the honest reading of "no trade should be a wipeout": you can *place*
the order, but on an expiry-day ATM option roughly half the time the market
will not fill you there. The guarantee is only as good as the liquidity at your
stop price, and this model has no order book to check it against.

## The trade-off is monotonic and unsurprising

Wider stop → bigger position → more return and more drawdown, in lockstep:

| | 2% | 5% | 10% |
|---|---|---|---|
| M5 return | 1.75× | 3.03× | 4.40× |
| M5 drawdown | 12.0% | 27.8% | 48.6% |
| median capital deployed | 5.1% | 13.1% | 26.3% |

Nothing is gained by widening the stop that is not paid for in drawdown. At 10%
the M5 account is down 48.6% at its worst point, and 28 of 142 cells are
profitable against 41 at 2%.

## And it still loses to random

Best-of-grid at a 5% stop, same 160-cell search, breadth matched:

| | strategy | random (median) |
|---|---|---|
| M5 | ₹16,62,614 | **₹47,78,817** |
| H1 | ₹1,55,79,726 | **₹1,01,61,67,133** |

Random searching the same grid found ₹101 crore on hourly bars. That number is
absurd, and its absurdity is the point: **compounding plus a wide grid plus a
short sample produces arbitrarily large fictions.** The strategy's ₹1.56 crore
is not a smaller version of a real result; it is a smaller draw from the same
fiction.

## What the stop did and did not fix

**Fixed:** ruin. No configuration reaches zero. Your instinct was correct and
the all-in result is genuinely repaired by a per-trade cap.

**Not fixed:** whether there is an edge. The cap changes the size of the bet,
not whether the bet is good. Across every stop level the strategy remains below
what random achieves under the same search, and the median cell at 10% makes
₹1,05,484 on M5 while the best makes ₹26 lakh — the winner is still the tail of
the distribution, not its centre.

```
python3 scripts/nifty_compound_sl.py <data-dir>
```
