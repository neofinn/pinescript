# Imbalance + orderflow on the wickless level

`python -m` nothing — see `scripts/orderflow.py`. Pine gate is group 6 of
`wickless_candle.pine`.

## What this is, and what it is not

**Real orderflow is trade-by-trade with the aggressor side known** — who crossed
the spread, at what price level, against how much resting size. Diagonal
imbalance (ask volume at a price against bid volume one tick below) needs
per-level bid/ask volume. **No OHLCV feed carries any of it.** Not Yahoo, not a
standard TradingView chart.

What is available is the tick rule applied to sub-bars: split each sub-bar's
volume between buyers and sellers by where it closed in its own range, then sum.
Every Pine footprint script does this underneath, via
`request.security_lower_tf()`. It is an **inference from bars**, not a
measurement of flow — a sub-bar closing at its high might be one aggressive buy
into a thin book or steady accumulation, and this cannot tell them apart.

So the honest question isn't "is this real orderflow" (it isn't) but "does the
approximation carry information the price bars don't". That is measurable.

## It needs volume, and some things have none

`corr(volume, |return|)` — below ~0.2 the field is void:

| GC=F | 1m | 2m | 5m | 15m | 1h | **1d** |
|---|---|---|---|---|---|---|
| corr | +0.615 | +0.588 | +0.584 | +0.572 | +0.563 | **void** |

Intraday gold is usable. **Daily gold volume was already killed in this project
at −0.03.** And NIFTY / BANKNIFTY / SENSEX publish **no volume at any
timeframe** — on those this gate rejects every signal and the chart looks
identical to a broken script. The diagnostics table now prints `NO VOLUME` in
red for exactly that reason.

## The approximation is not garbage

Delta sign agrees with candle direction on **76%** of 15m candles. Near 100%
would mean it's re-reading the close and adds nothing; near 50% would mean
noise. The 24% disagreement is where any information lives.

Imbalance distribution: p5 −0.41, p50 −0.00, p95 +0.43. |imb| > 0.30 on 24% of
candles.

## Does it improve the strategy?

Window 08-12 → 09-17 (2m data caps at ~35 days), 2,345 × 15m bars, re-baselined.

**Both entry types** — PF by threshold: 1.19, 1.42, 1.30, **2.28**, 1.26, 1.42.
The 0.30 cell is an **isolated spike with 1.30 below and 1.26 above it**. Textbook
fitted corner. Rejected on the same rule that rejected the IV filter earlier in
this project.

**Retest only** — 1.31, 1.09, 0.64, 1.11, 1.38. The filter makes it *worse* at
most thresholds. Note also: retest-only here is PF **1.31**, where the 2-month
test had it at **0.85**. That finding did not replicate — the sub-samples are
not stable enough to support either claim.

**Breakout only** — 1.13, 1.09, **2.06, 2.17**, 1.72. This is the only proper
shape: two adjacent cells above 2.0, falling off either side.

## The candidate, taken apart

Breakout + |imbalance| ≥ 0.35: **33 trades, 42.4% wins, PF 2.17, +431.5 points.**

| test | result |
|---|---|
| binomial vs the 33.3% a 1:2 needs | **p = 0.177** — not significant |
| top 1 trade | +152.0 = **35%** of all profit |
| top 3 trades | +375.3 = **87%** of all profit |
| top 5 trades | **118%** — everything else nets negative |
| **median trade** | **−9.63** |
| split halves | 2.08 (22 trades) / 2.40 (11 trades) |
| random control, 600 runs of 33 | median 0.81, 95th **1.55**, 99th **2.07** |

**The median trade loses money.** The whole result is three trades out of
thirty-three. And random runs of 33 trades reach PF 2.07 one time in a hundred —
the candidate is 2.17. Having tested ~19 cells in this pass alone (37 across the
whole wickless investigation), finding one at the 99th percentile of noise is
precisely what chance produces.

## Verdict

**Not demonstrated.** Not refuted either — and the reason is worth stating
plainly, because it is the binding constraint on everything here:

**A filter's real cost is sample size.** The unfiltered strategy had 77 trades on
this window. Requiring |imbalance| ≥ 0.35 cut it to 33. At n=33 a PF above 2 is
one-in-a-hundred noise, so the filter destroys the very sample needed to judge
it. More thresholds cannot fix that; only more data can.

What would settle it: 2m or finer bars over a year rather than 35 days, and a
second instrument. Yahoo caps 2m at ~35 days and 1m at ~7, so this needs the
broker feed.

## Using it

`wickless_candle.pine` group 6:

- **Require flow confirmation** — off by default, deliberately
- **Sub-bar timeframe** — `1` on a 15m chart gives 15 sub-bars; the coarser the
  sub-bar, the worse the tick-rule approximation
- **Min |imbalance|** — 0.25 default. Nothing above justifies a specific value
- **Reject bars where flow and price disagree** — tested separately and it did
  nothing on its own (PF 1.19 → 1.17); the imbalance term was doing the work

Watch the `sub-bars / volume` row before anything else. If it says `NO VOLUME`,
the gate is rejecting everything and no parameter will change that.
