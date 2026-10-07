# Gold 3-minute, on tick-built data with real spreads — interim

Re-run of the 3-minute question using Dukascopy ticks instead of Yahoo bars:
**44 sessions instead of 22**, bars built from ticks, and the **real measured
spread charged per bar** instead of a flat assumption. The fetch for a full year
is still running (1,200 of 8,760 hours at the time of writing); this is the
interim read on what has landed.

**Two answers. The validated strategy still fails at 3 minutes, now confirmed on
better data. And the cell that looks spectacular there is 15 trades.**

---

## 1. The validated cell still fails

P break, EMA-aligned, RR 20 — the cell that passes every control on h1 (733
sessions) and daily with weekly pivots (1,044 weeks):

| source | sessions | n | avg R | PF | win % |
|---|---|---|---|---|---|
| h1 (Yahoo, real spread) | 733 | 317 | **+0.330** | 1.47 | 31.2 |
| m3 Dukascopy, one per day | 44 | 27 | **−1.436** | 0.00 | **0.0** |
| m3 Dukascopy, many per day | 44 | 239 | **−0.276** | 0.79 | 11.3 |

Same conclusion as the Yahoo run, now on twice the sample with measured costs.
Twenty-seven one-per-day trades, every one a loss.

**Why**: round-trip cost is **25% of the risk** on 3-minute against **6%** on
h1 — four times the drag, on a setup whose h1 edge is +0.330 R.

| | median risk | median cost | cost as % of risk |
|---|---|---|---|
| 3-minute cell | $3.06/oz | $0.78 | **25%** |
| h1 validated cell | $11.03/oz | $0.65 | **6%** |

## 2. The best 3-minute cell — and what it actually is

132 cells, 19 positive. Top: **R2/S2 bounce, counter-EMA, RR 20 → +1.365 R,
n=114, PF 2.11**, win rate 17.5%.

It passes every control, which the Yahoo version did not:

| check | result |
|---|---|
| shuffle (40 draws) | real **+1.365** vs median −0.405, best +0.422 → **100th pct** |
| direction | long **+1.520** (n=52), short **+1.235** (n=62) → neutral **+1.377** |
| split-half | **+1.751** (n=56) / **+1.183** (n=54) |

That looked like a genuine find. It is not — or at least, not what the headline
says.

### The risk denominator is sound, so I checked where the money comes from

Median risk is $3.06/oz and **no trade has a risk smaller than the spread**, so
R is not being inflated by a small denominator. The problem is elsewhere:

| | value |
|---|---|
| **median R per trade** | **−1.44** |
| median P&L per trade | **−$3.92/oz** |
| trades returning more than +10R | **15 of 114** |
| their share of all R | **174%** |
| their median actual price move | **$57.77/oz** |

**The typical trade loses.** The entire result is 15 trades out of 114 — and
their median move is **$57.77 an ounce**, which is a full day's range in gold.
These are not three-minute trades. They are multi-hour holds that happen to be
entered on a three-minute bar, and the 3-minute chart contributes the entry
timing and nothing else.

Remove those 15 and the strategy is deeply negative.

### Why it passes the controls anyway

Capturing a handful of large daily trends **is** a real path property — shuffling
a session destroys it, so the shuffle control approves. Both directions and both
halves contain some of those 15 trades, so those checks approve too.

The controls are working correctly. They are answering "is this a real feature
of the price path?" — yes. They cannot answer "is 15 trades enough?" — and 15
trades across 44 sessions is not.

## 3. In dollars, which cannot be inflated

| | trades | total | mean | median |
|---|---|---|---|---|
| 3-minute cell | 114 | $588/oz | $5.16 | **−$3.92** |
| h1 validated cell | 317 | $1,207/oz | $3.81 | **−$5.92** |

Both have the same shape — a minority of large winners paying for a majority of
losers. The difference is that the h1 version rests on 317 trades across 733
sessions and has held up across a 20-year daily confirmation, while the
3-minute version rests on 15 decisive trades across 44 sessions.

## Verdict, for now

- **The validated strategy does not work at 3 minutes.** Confirmed twice, on two
  data sources, with measured costs. Cost is 25% of risk there against 6% on h1.
- **The 3-minute cell that ranks first is 15 trades.** It passes every control
  because capturing big daily trends is genuinely a path property — but the
  median trade loses $3.92/oz and the result would reverse without those 15.
- **Still use h1 or daily-with-weekly-pivots.** Nothing here changes that.

The year-long fetch continues. What it will settle is whether those 15 trades
are a recurring feature or a property of these particular 44 sessions — which is
exactly the question 22 sessions could not answer either, and the reason the
deeper source was worth building.

## Files

- `scripts/dukascopy.py` — the tick fetcher and spread-carrying aggregator.
