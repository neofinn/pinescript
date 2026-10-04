# Can you trade the S&P with the dip-buying effect?

The one real thing found while testing the SPX/DJI overlap claim: the S&P
mean-reverts after sharp declines. A 2-sigma drop in the index's own 60-day
z-score was followed by **+281 bps over 30 days against a +119 bps baseline**,
at the 100th percentile of its random-time control, over 20 years.

**No. It is not tradeable as a strategy. Holding half your money in the index
and half in cash — doing nothing at all — beats it by 2 points of CAGR a year at
exactly the same drawdown.**

---

## Why the +281 bps was never a strategy

It is a forward-return statistic. It has no entry rule, no exit, no account, and
its 30-day windows overlap heavily, so its effective sample is far smaller than
its signal count. Turning it into something with money attached requires three
things, all enforced here:

- **Causal.** The z-score is known at the close; the trade opens at the **next
  bar's open**.
- **No overlap.** One position at a time. A signal that fires while already long
  is ignored — which makes the trades independent and the statistics honest.
- **Costs.** 2 bps each way.

The S&P is a price index, so dividends are excluded from the strategy *and* from
buy-and-hold. The comparison stays fair and both sides are understated.

Data: 5,031 daily bars, 2006-10-03 → 2026-10-02.

## 1. It loses to buy-and-hold in every single configuration

22 parameter cells (lookback 60/120/240, threshold −1.5/−2.0/−2.5, hold
10/30/60 days):

| w | thr | hold | n | total % | CAGR % | maxDD % | in mkt % | vs buy-and-hold |
|---|---|---|---|---|---|---|---|---|
| 60 | −1.5 | 60 | 34 | 144.8 | **4.76** | 33.5 | 42.1 | −4.44 pts/yr |
| 60 | −2.0 | 60 | 30 | 103.1 | 3.75 | 30.6 | 37.2 | −5.50 pts/yr |
| 60 | −2.0 | 30 | 37 | 73.3 | 2.92 | 32.5 | 23.1 | −6.00 pts/yr |
| 60 | −2.0 | 10 | 58 | 26.6 | 1.24 | 24.2 | 12.1 | −7.28 pts/yr |
| 120 | −2.0 | 30 | 21 | 0.4 | 0.02 | 33.3 | 13.6 | −9.19 pts/yr |
| 240 | −1.5 | 10 | 48 | −25.8 | −1.71 | 35.6 | 11.0 | −9.48 pts/yr |

**Buy-and-hold: 373% total, 8.47% CAGR, 57.7% max drawdown.**

- cells beating buy-and-hold on CAGR: **0 / 22**
- cells with a smaller drawdown than buy-and-hold: **22 / 22**

So it does one thing: it reduces risk. It does that by sitting in cash 58–92% of
the time, which is not a skill.

## 2. The risk reduction is free elsewhere

The strategy's best-known cell returns 2.92% CAGR at a 32.5% max drawdown. A
static index/cash mix over the **identical** window, rebalanced daily:

| index weight | CAGR % | maxDD % |
|---|---|---|
| 30% | 3.04 | 20.6 |
| 40% | 3.99 | 26.7 |
| **50%** | **4.90** | **32.5** |
| 100% | 8.97 | 56.8 |

50% in the index matches the strategy's drawdown **to the decimal** — 32.5% —
and returns **4.90%** against the strategy's **2.92%**.

Two points of CAGR a year, given up in exchange for 37 trades, a signal, and
execution risk. The timing is not merely failing to add value; it is costing
about 2% a year versus the laziest possible alternative.

## 3. The entire result is five trades

w=60, z<−2, 30-day hold, 37 trades:

| drop the best | trades left | total % | CAGR % |
|---|---|---|---|
| 0 | 37 | 73.3 | 2.92 |
| 1 | 36 | 40.2 | 1.78 |
| 3 | 34 | 11.7 | 0.58 |
| **5** | **32** | **−5.7** | **−0.30** |

The top five trades account for **110.6%** of all compounded growth. The other
32 trades, over 19 years, lose money.

| date | return | share of all log-growth |
|---|---|---|
| 2008-11-21 | +23.6% | 38.6% |
| 2025-04-22 | +14.6% | 24.8% |
| 2019-06-03 | +9.5% | 16.5% |
| 2010-02-05 | +9.0% | 15.6% |
| 2016-06-28 | +8.7% | 15.1% |

This is not an edge you can plan around. It is a handful of crisis bottoms, and
whether you catch the next one is a coin flip on timing you cannot rehearse.

## 4. Both halves of the sample agree

No fitting, just a split down the middle:

| half | w | thr | hold | n | CAGR % | B&H CAGR % | edge | maxDD % | B&H DD % |
|---|---|---|---|---|---|---|---|---|---|
| first (2006–2016) | 60 | −2.0 | 30 | 21 | 1.52 | 4.92 | **−3.40** | 32.5 | 57.7 |
| first | 60 | −2.0 | 10 | 33 | 2.45 | 4.80 | −2.35 | 24.2 | 57.7 |
| second (2016–2026) | 60 | −2.0 | 30 | 15 | 4.75 | 13.17 | **−8.42** | 7.2 | 35.4 |
| second | 60 | −2.0 | 10 | 23 | −0.25 | 12.23 | −12.47 | 17.4 | 35.4 |

It loses to buy-and-hold in both halves, by 2.4–5.8 points a year in the first
and 8.4–12.5 in the second. This is not a regime that ended; it never worked.

## What the statistic actually was

The +281 bps was real arithmetic and it was still misleading, for a reason worth
keeping:

The baseline it beat was **a random day**, and a random day is the wrong
comparison. The right one is the alternative you would otherwise take, which is
holding the index. Measured against *that*, the effect inverts — because the
30-day windows after a 2-sigma drop are a small, overlapping, crisis-heavy
subset of a market that spent twenty years going up. Being out of it for 77% of
the time costs more than the bounces return.

A signal can be genuinely statistically significant against the null it was
tested against, and still be the wrong thing to do with your money. That gap is
the whole lesson here.

## Files

- `scripts/spx_dip.py` — causal entry, non-overlapping trades, buy-and-hold and
  static-mix benchmarks.
