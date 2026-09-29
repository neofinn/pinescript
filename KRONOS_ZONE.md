# Kronos direction + supply/demand stop

The narrow hypothesis. One signal, one structural stop, **twelve cells instead
of a hundred and sixty**.

- **Direction** — the sign of Kronos's predicted return over its 12-bar horizon
- **Stop** — the nearest live opposing supply/demand zone, so the stop is where
  the idea is structurally wrong rather than a number chosen to fit
- **Gate** — optional: skip if the nearest opposing zone sits closer than the
  target, so the trade has nowhere to go

**Contamination:** the hourly forecasts run 2025-09-10 to 2026-09-24, all after
the weights froze on 2025-09-09. The model never saw these outcomes.

## The control is the design

Instead of random entries, this shuffles **only the predicted directions**
between forecasts — same entry times, same stops, same zones, same gate, same
option maths. If the result survives, Kronos's direction carried something. If
not, the zones and the calendar made the money.

## H1 — 149 forecasts, Sep 2025 to Sep 2026

| threshold | RR | gate | n | final | × | PF | maxDD | shuffled median | **pct** |
|---|---|---|---|---|---|---|---|---|---|
| none | 1.5 | no | 131 | ₹23,55,800 | 4.71 | 1.60 | 32.5% | ₹17,35,833 | 65 |
| none | 2.0 | no | 131 | ₹19,68,289 | 3.94 | 1.53 | 38.1% | ₹16,54,774 | 60 |
| **median** | **1.5** | **no** | **67** | **₹21,70,120** | **4.34** | **2.18** | **24.8%** | ₹9,60,927 | **92** |
| median | 2.0 | no | 67 | ₹18,57,543 | 3.72 | 2.07 | 26.1% | ₹9,54,628 | 82 |
| median | 3.0 | no | 67 | ₹14,95,740 | 2.99 | 1.84 | 25.3% | ₹9,10,923 | 78 |
| none | 1.5 | **yes** | 47 | ₹6,04,666 | 1.21 | 1.18 | 22.6% | ₹5,66,217 | 55 |
| none | 2.0 | **yes** | 42 | ₹4,29,471 | **0.86** | 0.85 | 31.9% | ₹5,99,154 | 22 |

**0 of 11 cells cleared the 95th percentile.**

## M15 — 78 forecasts

Everything between the 25th and 28th percentile, every cell between 0.81× and
1.14×. The magnitude threshold left fewer than 15 trades in every cell. Nothing
here at all.

## The number that settles it

The best cell sits at the **92nd percentile** of its own control. Eleven cells
were tested.

The expected maximum of *n* independent draws from a uniform distribution is
*n*/(*n*+1). For eleven cells that is **91.7%**.

Observed: 92. The best result is exactly what searching eleven cells produces
when there is nothing to find.

That is not a near miss — it is the null landing precisely on its expectation.
And it is why the number of cells has to be stated next to the maximum: at 160
cells the same argument would have predicted a 99.4th-percentile winner, which
is roughly what the earlier grids kept producing.

## Two things worth keeping

**The magnitude threshold is the one place Kronos's output did work.** Taking
only forecasts above the median predicted move raised the percentile from 65 to
92, cut the drawdown from 32.5% to 24.8%, and lifted the profit factor from 1.60
to 2.18 — on half the trades. Kronos cannot pick direction, but a larger
predicted move was associated with a better outcome. That is a thinner claim
than "it forecasts", and it is the only part of the model that survived contact
with a control at all.

**The supply/demand gate hurts, consistently.** Every gated cell is worse than
its ungated twin — 4.71× to 1.21×, 3.94× to 0.86×, 3.49× to 0.92× — because it
cuts the sample from 131 trades to 31–47. This is the sixth measurement in this
project of the same effect, now on the narrowest design available: the filter
removes sample faster than it removes bad trades.

The zones are still doing the real work — the shuffled control keeps ₹9.6–17.4
lakh of the return with the directions randomised — but they are doing it
through the **stop placement**, not the entry filter.

```
python3 scripts/kronos_zone_strategy.py <data-dir>
```
