# Volume-surge confluence on both clip strategies

Ten highest dollar-volume names, 5m bars, two months. Trades **pooled** across
instruments and normalised by price, so a $762 SPY and a $108 INTC contribute
comparably — pooling is where the power is (10 × ~25 trades, not 25).

## First: a volume surge is partly a clock

Median SPY volume by position in the session:

| bar | time | × midday |
|---|---|---|
| 0 | open | **8.5×** |
| 6 | +30m | 1.9× |
| 48 | +240m | 0.8× |
| 77 | close | **12.5×** |

So "volume vs the last 20 bars" partly measures *what time it is*. Both
definitions were therefore tested:

- **naive** — volume ÷ trailing 20-bar average
- **session-adjusted** — volume ÷ the median for *that position in the session*,
  computed from **prior sessions only** (using the current session's own bars
  would leak data the bar did not have)

Adjusting halves the clustering at the open (SPY 9% → 6%, QQQ 16% → 5%).

## The result

| | trades | PF | median trade |
|---|---|---|---|
| **A, in-sample baseline** | 254 | 0.56 | −0.515 |
| A, in-sample, adj ≥ 2.0 | 29 | **1.34** | −0.739 |
| **A, out-of-sample, adj ≥ 2.0** | 41 | **0.64** | −0.336 |
| **B, in-sample baseline** | 163 | 0.87 | −0.096 |
| B, out-of-sample baseline | 195 | 1.15 | −0.077 |
| B, out-of-sample, naive ≥ 2.0 | 26 | **1.90** | −0.059 |

A's filter looks like it works in-sample (0.56 → 1.34) and **reverses out of
sample** (0.77 → 0.64). Same pattern this project has now seen four times.

B's numbers survive both halves and look good — PF 1.90 out of sample. That is
the one worth taking apart properly.

## The number that settles it

A profit factor means nothing without the trade count behind it. Here is each
out-of-sample cell against **the 95th percentile of random run at that same
trade count** — the bar it must clear to be significant at 5%:

| strat | filter | trades | PF | bar to clear | **PF ÷ bar** |
|---|---|---|---|---|---|
| A | **none** | 228 | 0.77 | 1.37 | **0.56** |
| A | adj ≥ 1.5 | 89 | 0.86 | 1.70 | 0.51 |
| A | adj ≥ 2.0 | 41 | 0.64 | 2.95 | 0.22 |
| A | naive ≥ 3.0 | 70 | 0.79 | 1.71 | 0.46 |
| B | **none** | 195 | 1.15 | 1.24 | **0.93** |
| B | naive ≥ 1.25 | 79 | 1.20 | 1.97 | 0.61 |
| B | naive ≥ 1.5 | 51 | 1.50 | 1.73 | 0.87 |
| B | naive ≥ 2.0 | 26 | **1.90** | **2.68** | **0.71** |

**Nothing reaches 1.00.** B's headline PF 1.90 is on 26 trades, where random
reaches 2.68 one time in twenty — so 1.90 is *unremarkable*, not impressive.

And the line that matters most: **for both strategies the UNFILTERED baseline
scores highest.** B's baseline is 0.93; every filtered cell is worse. Tightening
the filter raises the bar faster than it raises the profit factor — **the sample
it destroys costs more power than the selectivity buys.**

That is not an argument against volume. It is arithmetic about this data: at
26–90 trades there is no threshold that can be shown to work, because the
significance bar at those counts is above anything the strategies produce.

## Also

The **median trade is negative in all 28 cells** tested, filtered and
unfiltered, both strategies, both halves. Both are many-small-losses profiles
hoping for a tail — which is exactly what made the options overlay look like a
winner while 46% of contracts expired worthless.

## Verdict

Volume confluence does not rescue either strategy. It moves both **away** from
significance rather than toward it, and the one cell that looks best (B, naive
≥ 2.0, PF 1.90) is 26 trades sitting below its own noise threshold.

If you want volume to earn its place, it needs a dataset where filtering to a
third still leaves several hundred trades. Two months of 5m bars on ten names
is not that dataset — which is the same conclusion the pre-registered
fourteen-signal search reached independently.
