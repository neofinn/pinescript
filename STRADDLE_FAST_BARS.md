# The straddle bot on 1, 3 and 5 minute bars

Companion to [STRADDLE_BOT.md](STRADDLE_BOT.md), which measured the same system
from hourly to daily and found that transaction costs were the binding
constraint. This runs it faster, which is the direction that constraint says
not to go.

**It loses on all three. At 1-minute it beat buy-and-hold in 0 of 15 markets and
lost 20% of the account in 25 days. The reason is one number: a round trip at
1-minute costs 192% of the bar's own average range.**

---

## Data

15 markets with a common history: ES NQ GC SI CL · SPY QQQ GLD AAPL NVDA TSLA
JPM · BTC ETH · EURUSD.

- **m1** — 288,802 bars, ~25 days (Yahoo serves 1-minute in 7-day windows,
  chained here to reach a month)
- **m3** — 96,320 bars, aggregated from m1 (Yahoo has no 3-minute interval)
- **m5** — 151,053 bars, 60–75 days

Costs 1 bp futures and FX, 3 bps ETFs and single names, 10 bps crypto.

## The whole timeframe curve, one system, one set of markets

Medians, so no single runaway market carries a row. Total return over the data
available — **not annualised**, because annualising a 25-day window produces
nonsense.

| timeframe | days | trades/market | **cost as % of 1 ATR** | strategy | hold | beat hold |
|---|---|---|---|---|---|---|
| **m1** | 25 | 963 | **192%** | **0.795** | 1.002 | **0 / 15** |
| **m3** | 25 | 301 | **109%** | **0.918** | 1.006 | 3 / 15 |
| **m5** | 75 | 463 | **81%** | **0.863** | 1.038 | 1 / 15 |
| h1 | 953 | 464 | 15% | 0.812 | 1.758 | 2 / 15 |
| h4 | 953 | 120 | 7% | 0.977 | 1.759 | 2 / 15 |
| daily | 6,749 | 202 | **3%** | **1.165** | 7.406 | 2 / 15 |

One column explains the entire table. **At 1-minute, getting in and out costs
nearly twice the average range of the bar you are trading.** The move you are
trying to capture is smaller than the toll to capture it. By daily the same
round trip costs 3% of a bar's range, and the system turns positive.

## The signal is there. It is three orders of magnitude too small.

| timeframe | cost × | trades | mean × |
|---|---|---|---|
| m1 | **0.00** | 14,447 | **1.013** |
| m1 | 0.25 | 14,447 | 0.868 |
| m1 | 0.50 | 14,447 | 0.784 |
| m1 | **1.00** (real) | 14,447 | **0.679** |
| m3 | 0.00 | 4,519 | 0.991 |
| m5 | 0.00 | 6,940 | 1.009 |

At **zero cost** the 1-minute system makes money. Gross, it returns about
**+1.3% over 25 days across roughly 963 trades per market** — which is
**0.135 basis points per trade**.

The round trip costs 2 bps on futures, 6 on single names, 20 on crypto.

**The cost is 15 to 150 times the gross edge.** Not a margin to be optimised —
a different order of magnitude. And a quarter of the real spread is already
enough to turn it negative (0.868), so no realistic execution improvement
reaches it.

## Per market at 1-minute, the timeframe asked for

| market | trades | strategy | hold | cost as % of 1 ATR |
|---|---|---|---|---|
| **EURUSD** | 2,798 | 0.502 | 0.969 | **881%** |
| **BTC** | 1,813 | **0.031** | 1.069 | **576%** |
| **ETH** | 1,752 | **0.039** | 1.083 | **390%** |
| SPY | 336 | 0.809 | 1.000 | 229% |
| QQQ | 313 | 0.845 | 1.039 | 174% |
| GLD | 334 | 0.800 | 0.941 | 138% |
| ES | 1,214 | 0.740 | 1.007 | 126% |
| JPM | 326 | 0.841 | 0.933 | 100% |
| AAPL | 319 | 0.864 | 1.045 | 92% |
| NVDA | 317 | 0.855 | 1.002 | 87% |
| NQ | 1,115 | 0.794 | 1.045 | 75% |
| TSLA | 305 | 0.795 | 1.031 | 62% |
| GC | 1,156 | 0.789 | 0.928 | 51% |
| SI | 1,175 | 0.681 | 0.892 | 35% |
| CL | 1,174 | 0.803 | 0.980 | 24% |

**Crypto loses 96–97% of the account in 25 days.** BTC takes 1,813 trades at
20 bps a round trip; that is 36 full percent of equity paid in spread alone
before a single opinion about direction is expressed.

**EURUSD is the extreme**: its 1-minute range is so small that a 1 bp round
trip is **8.8 times** the average bar. Nothing about the strategy matters at
that ratio.

Note that the markets least damaged — CL at 24%, SI at 35%, GC at 51% — are the
ones with the widest 1-minute ranges relative to their spreads. The ranking is
the cost ratio, not anything about the pattern.

## What this confirms

STRADDLE_BOT.md found the same system at the 100th percentile against shuffled
data, meaning it genuinely harvests trend — and found that hourly costs ate all
of it. Three faster timeframes extend that curve in exactly the predicted
direction, and the cost-per-ATR column makes the mechanism explicit rather than
inferred.

There is no execution fix. A quarter of the assumed spread still loses, and no
broker offers a quarter of the spread.

## Verdict

Do not run this bot on m1, m3 or m5. The `--timeframe` default in
`bots/straddle_bot.py` is `1d` for this reason, and the chart script carries the
same warning.

If the goal is specifically intraday trading, this system is the wrong tool: its
edge is serial correlation in price, which exists at minute scale but is far
smaller than the bid-ask spread that must be crossed to reach it. The numbers
above are what that looks like.
