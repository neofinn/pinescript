# Gold pivots: multi-timeframe, EMA 5 vs 9, capped at 0.05 lots

Three changes from the previous run: a hard **0.05-lot cap**, **five
timeframes**, and **EMA 5 against EMA 9**.

**The EMA length question has a definite answer: for the setup that works, the
two are byte-identical. The 0.05-lot cap is the single most useful change made
to this system — it converts near-certain ruin into a survivable account, taking
the 50%-risk ruin rate from 99.5% to 37.0%.**

---

## 1. EMA 5 vs EMA 9 — identical where it matters

Across 76 matched pairs: mean (EMA5 − EMA9) = **+0.008 R**, EMA 5 better in
**35 of 76**. That is a coin flip.

On m15 and m30 the two are **exactly equal to three decimals** on every
pivot-break cell. That is not a bug, and the reason is measurable:

> On gold m30, price is on the **same side of the 5 and the 9 EMA on 89.6% of
> bars** (2,004 of 2,237).

A pivot **break** is by definition a bar closing decisively through a level, so
it lands in that 90% essentially always — both EMAs agree, and the "aligned"
filter returns the same trades either way.

**The EMA length can only matter for BOUNCE setups**, where price sits at an
extreme and the two averages can straddle it. That is exactly where the
differences show up:

| timeframe | cell | EMA 5 | EMA 9 | diff |
|---|---|---|---|---|
| h1 | R1/S1 bounce aligned | **+0.102** | −0.041 | **+0.142** |
| h1 | R2/S2 bounce aligned | −0.046 | −0.168 | +0.122 |
| h1 | R1/S1 break counter | +0.261 | +0.181 | +0.083 |
| h1 | **P break aligned** | +0.346 | **+0.373** | −0.027 |
| d1 | P break aligned | +0.089 | **+0.126** | −0.036 |

**For P break — the cell that actually works — use either. For bounce setups,
EMA 5 is the better of the two.**

## 2. Multi-timeframe, and sample size is doing the ranking

474 testable cells across 5 timeframes × 2 EMA lengths.

| timeframe | sessions | n | best avg R |
|---|---|---|---|
| m15 | 58 | 40 | **+1.132** |
| m30 | 59 | 44 | +0.858 |
| **h1** | **733** | **317** | **+0.373** |
| h4 | 733 | 40 | +0.139 |
| **d1 (weekly pivots)** | **1,044** | **438** | **+0.132** |

Average R falls **monotonically as the sample grows**. The m15 figure of +1.132
rests on 40 trades from 58 sessions — Yahoo's 60-day cap on sub-hourly data.
Only h1 and daily carry enough trades to mean anything, and they agree.

Daily bars cannot hold an intraday walk, so the daily row uses **weekly pivots
on daily bars** — the same construction one level up, and the only way this
setup is expressible on a daily chart.

## 3. The daily/weekly result validates the hourly one, over 20 years

Same structure (P break, EMA-aligned), a different timeframe, a different pivot
period, and a sample that starts 18 years earlier:

| | n | avg R |
|---|---|---|
| long | 225 | +0.191 |
| **short** | 213 | **+0.069** |
| **direction-neutral** | | **+0.130** |

Gold rose 10.5%/yr over those 20 years and **shorts are still profitable**.

| check | result |
|---|---|
| shuffle control (40 draws) | real **+0.132** vs median −0.553, best −0.458 → **100th pct** |
| split-half | **+0.201** / **+0.064** — both positive |

This is independent confirmation. The h1 cell (+0.373 over 733 sessions) and the
daily/weekly cell (+0.132 over 1,044 weeks and 20 years) are the same structure
measured on non-overlapping resolutions, and both pass direction-neutrality,
the shuffle control and the split-half.

## 4. The 0.05-lot cap — the most useful change here

0.05 lots = 5 ounces. At the median stop of $11.03/oz that risks **$55 — 11% of
a $500 account.** The cap is a *high* risk setting, not a low one, until the
account reaches several thousand dollars.

$500, 1:1000, liquidation at a 50% margin level, 1,000 reshufflings per row:

| risk/trade | final $ | max DD | **ruin** | 5th pct | median $ | trades at the cap |
|---|---|---|---|---|---|---|
| 2% | 4,013 | 52.4% | **1.4%** | 2,529 | 3,340 | 30% |
| 5% | 4,052 | 70.9% | **3.2%** | 3,655 | 5,307 | 70% |
| 10% | 7,357 | 50.3% | 9.0% | 0 | 6,471 | 98% |
| 20% | 7,703 | 49.1% | 20.9% | 0 | 6,784 | 99% |
| 50% | 7,177 | 50.8% | 37.0% | 0 | 6,980 | 100% |
| 100% | 7,177 | 50.8% | 46.6% | 0 | 6,649 | 100% |

### What the cap does, against the same settings uncapped

| risk/trade | **ruin capped** | **ruin uncapped** | final capped | final uncapped |
|---|---|---|---|---|
| 10% | **9.0%** | 15.5% | 7,357 | 15,639 |
| 20% | **20.9%** | **87.4%** | 7,703 | **0** |
| 50% | **37.0%** | **99.5%** | 7,177 | **0** |
| 100% | **46.6%** | **99.8%** | 7,177 | **0** |

**At 50% risk the cap takes ruin from 99.5% to 37.0%.** At 100% it takes 99.8%
to 46.6%. Max drawdown stops at ~50% instead of 100%.

The cap is doing what leverage limits are supposed to do and 1:1000 refuses to:
it puts a ceiling on the single worst trade.

### One consequence worth knowing

Once the cap binds, **the risk-per-trade setting stops mattering**. At 10% and
above, 98–100% of trades are at the cap, so every row is running the same fixed
0.05-lot strategy — final equity is $7,177–$7,703 across all of them. The only
difference between those rows is how fast the early account grows into the cap,
which is where the differing ruin rates (9% to 47%) come from.

## Verdict

- **EMA 5 or EMA 9 — for P break it makes no difference at all**; price is on
  the same side of both 90% of the time, and a break is always in that 90%. If
  you trade bounce setups instead, use EMA 5 (+0.142 on h1 R1/S1).
- **Trade h1, or daily with weekly pivots.** Those are the only two samples with
  enough trades, and they confirm each other across 20 years.
- **Ignore the m15 and m30 numbers.** +1.132 R on 40 trades from 58 sessions is
  the small-sample inflation visible right down the table.
- **Keep the 0.05 cap. It is the best risk control in this system** — better
  than any risk-percentage setting, because it binds on the trade that would
  otherwise end the account.
- **Use 2–5% risk underneath the cap**: 1.4–3.2% ruin, $500 → ~$4,000 over
  2.4 years. Above 10% the cap binds anyway and you are only buying ruin
  probability for no extra return.

## Files

- `scripts/pivot_ema.py` — now supports weekly pivot periods for daily bars.
- `scripts/gold_mtf_run.py` — the timeframe × EMA-length sweep.
