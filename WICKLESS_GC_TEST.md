# Wickless candle on GC=F — 2 months, 1:2 RR

Data: Yahoo `GC=F`, **2026-07-17 → 2026-09-17**, gold 4018.3 → 4406.7 (**+9.7%**).
11,503 × 5m bars, 3,843 × 15m, 986 × 1h, 44 × 1d.

This is a **replication** of `wickless_candle.pine` in Python
(`scripts/wickless_backtest.py`), block-for-block in the same execution order,
because there is no Pine compiler in this environment. Entry at next bar open;
when a bar contains both stop and target the **stop** is taken; cost 0.45 price
points per round trip (~$5 commission + 2 ticks slippage each side).

## Daily is unusable

Exact wickless bars: **8.4%** of 5m bars, 4.7% of 15m, 2.3% of 1h, **0 of 44
daily bars**. Over two months a daily chart produces no signals at all. This
has to be an intraday strategy or it is nothing.

## The sweep

| tf | tolerance | levels | trades | win% | PF | net pts |
|---|---|---|---|---|---|---|
| 5m | exact | 848 | 315 | 31.7 | 1.04 | +85.7 |
| 5m | 5% | 1,563 | 267 | 35.2 | 0.99 | −21.2 |
| 5m | 10% | 2,383 | 314 | 37.6 | 1.09 | +185.3 |
| 5m | 35% | 4,759 | 641 | 32.3 | 0.89 | −364.7 |
| **15m** | exact | 154 | 70 | 30.0 | 0.91 | −64.5 |
| **15m** | 2% | 253 | 100 | 36.0 | 1.09 | +97.2 |
| **15m** | **5%** | 446 | **131** | **40.5** | **1.34** | **+455.2** |
| **15m** | 10% | 741 | 169 | 38.5 | 1.32 | +504.9 |
| **15m** | 35% | 1,551 | 214 | 35.0 | 0.98 | −30.6 |
| 1h | 20% | 286 | 46 | 43.5 | 1.75 | +570.7 |

5m oscillates around PF 1.0 with no pattern — noise. 1h is wildly
non-monotonic on 9–68 trades — noise. Only **15m** shows the rise-plateau-fall
shape of a real effect: 0.91 → 1.09 → **1.34 → 1.32** → 1.07 → 0.98.

## Does it survive?

**Multiple comparisons: marginal.** 18 cells were tested. Best cell (15m, 5%)
gives a one-tailed binomial p of **0.052** against the 33.3% break-even win rate
a 1:2 needs. Across 18 cells you expect **0.9** cells that good from noise.

**Out-of-sample halves: consistent.** First half PF 1.33 (76 trades), second
1.46 (53). Both positive. Note this is a stability check, not validation — the
cell was chosen using both halves.

**Bootstrap: spans zero.** 10,000 resamples of the 131 trades: 95% CI
**−238 to +1,192 points**, with **10.3%** of resamples at or below zero.

**Random control, matched per side.** Gold rose 9.7%, so a random long and a
random short are different experiments and the signal must beat its own side:

| side | wickless n | win% | PF | net | random PF median | random 95th | **percentile** |
|---|---|---|---|---|---|---|---|
| **LONG** | 103 | 41.7 | **1.44** | **+409** | 0.83 | 1.15 | **99th** |
| SHORT | 113 | 32.7 | 0.99 | −11 | 0.95 | 1.35 | 58th |

This is the most informative result here. A **random long lost money** in this
window (PF median 0.83, net −74) despite gold rising 9.7% — a 1:2 with a tight
stop gets chopped out regardless of trend. So the long result is not the market
doing the work: it beats its own matched control at the **99th percentile**.

The short side is **indistinguishable from random** (58th percentile, PF 0.99).

## What is actually carrying it

| variant | trades | win% | PF | net |
|---|---|---|---|---|
| as reported | 131 | 40.5 | 1.34 | +455.2 |
| **retest entries only** | 200 | 35.0 | **0.85** | **−128.0** |
| breakout entries only | 89 | 36.0 | 1.12 | +152.1 |
| breakeven stop at 1R **on** | 181 | 30.9 | 1.21 | +296.1 |
| optimistic fill (target first) | 131 | 42.0 | 1.37 | +495.7 |
| double cost | 131 | 40.5 | 1.29 | +396.2 |

**The retest — the mechanism the whole idea rests on — loses money standalone.**
Breakout-only is weak. The combined figure is better than either component,
which happens because they compete for one position slot and the combination
incidentally skips bad retests. That is a fragile interaction, not a mechanism.

Costs are not the fragile part: doubling them still leaves PF 1.29.

## Verdict

**Not validated. Worth one more test, not worth trading.**

For it: the long side beats its own matched random control at the 99th
percentile, the two halves agree, and it is robust to cost and fill assumptions.

Against it: the parameter cell was chosen in-sample out of 18 (p = 0.052, ~0.9
expected by chance), the bootstrap CI spans zero, the short side is noise, the
core retest mechanism loses standalone, and this is one instrument in one
two-month rising regime with 103 long trades.

I cannot separate "longs work" from "trend-aligned trades work" in a single
rising window. That is the first thing a second test should resolve.

## Settings that reproduce the headline

`wickless_candle.pine`, **15-minute** chart:

- Wick tolerance: **Percent of range, 5.0** (matches the default)
- Marubozu: **off**, Min body **50%**, Min range **0.5 × ATR**, ATR **14**
- Trigger: **Both**, Order: **Market next open**
- Level life **20** bars, retest zone **0.10 × ATR**
- Stop **0.25 × ATR** beyond level, Target **2.0 R**
- **Move stop to breakeven at 1R: OFF** ← the .pine ships with this **ON**,
  and leaving it on gives PF 1.21 instead of 1.34
- Trail: off

## Next test, if you want one

1. **More history.** 2 months and 131 trades cannot separate p = 0.05 from
   nothing. Yahoo caps 15m at ~60 days, so this needs a different source.
2. **More instruments.** If the effect is real it should appear elsewhere; if
   it only ever appears on gold it is a fitted cell.
3. **A falling window**, to settle whether the long-side result is the signal
   or trend alignment.
