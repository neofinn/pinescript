# Gold on 3-minute bars

Yahoo has no 3-minute interval, so these are built by aggregating 1-minute bars
— which caps the sample at what Yahoo serves for 1m: **22 sessions**,
2026-09-08 → 2026-10-02. 8,609 bars, ~391 per session.

**The strategy that validated on hourly and daily is negative on 3-minute:
+0.373 R becomes −0.341 R. The best 3-minute cell shares nothing with it, and
does not survive its own controls.**

---

## 1. The validated cell, read on 3-minute

P break, EMA-aligned, RR 20 — the cell that passed direction-neutrality, the
shuffle control and the split-half on both h1 (733 sessions) and daily with
weekly pivots (1,044 weeks, 20 years):

| timeframe | sessions | n | avg R | PF | win % |
|---|---|---|---|---|---|
| **h1** | 733 | 317 | **+0.373** | 1.56 | 31.5 |
| m3, one trade per day | 22 | 16 | **−1.149** | 0.00 | **0.0** |
| m3, many per day | 22 | 153 | **−0.341** | 0.66 | 11.8 |

It inverts. Sixteen one-per-day trades lost every single time.

## 2. Why — the cost ratio

| timeframe | median ATR | round trip ($0.33/oz) as % of one ATR |
|---|---|---|
| h1 | $12.92 | **2.6%** |
| m30 | $11.89 | 2.8% |
| **m3** | **$3.39** | **10%** |

Four times the drag per trade, against a setup whose edge on h1 was +0.373 R.
This is nowhere near the 192%-of-ATR wall that killed the 1-minute straddle, so
cost alone does not explain the sign flip — but it removes any margin the setup
had.

## 3. The best 3-minute cell is a different strategy

105 testable cells, 19 positive. The best:

| per-day | EMA | levels | mode | EMA role | RR | n | avg R | PF | win % |
|---|---|---|---|---|---|---|---|---|---|
| many | 5 | **R3/S3** | bounce | **none** | 20 | 51 | **+0.868** | 1.91 | **13.7** |

Two things disqualify it on sight:

- **R3/S3 was the worst level group everywhere else** — all eight cells negative
  on gold h1, all eight negative on NIFTY.
- **The EMA role is "none".** The 9 EMA and the 5 EMA are both doing nothing.
  This is not the system being tested; it is a different one that happened to
  rank first in a 105-cell search.

### And it fails its own controls

| check | result |
|---|---|
| shuffle control (40 draws) | real **+0.868**, shuffled median −0.102, **shuffled best +0.986** → 98th pct, **does not clear the best shuffle** |
| split-half | +1.644 (n=27) / **+7.566 (n=3)** — three trades |
| direction | long **−1.095** (n=28), short **+3.257** (n=23) |

A 13.7% win rate producing +0.868 R means a handful of very large winners. The
direction split confirms it: every dollar comes from **23 short trades averaging
+3.257 R**, while the 28 longs lose −1.095 each. That is not an edge, it is one
direction of one month.

## 4. The prediction held

Before this ran, the established pattern across timeframes was that average R
falls as the sample grows. Adding 3-minute:

| timeframe | sessions | n | best avg R |
|---|---|---|---|
| **m3** | **22** | 51 | **+0.868** |
| m15 | 58 | 40 | +1.132 |
| m30 | 59 | 44 | +0.858 |
| **h1** | **733** | 317 | **+0.373** |
| **d1 (weekly)** | **1,044** | 438 | **+0.132** |

The three thin samples (22–59 sessions) all land between +0.86 and +1.13. The
two deep samples (733 and 1,044) land between +0.13 and +0.37. **The split is
by sample size, not by timeframe** — and only the deep two agree with each
other, pass their controls, and survive out of sample.

## Verdict

**Do not run this on 3-minute gold.**

- The validated setup is **negative** there (−0.341 R, and −1.149 one-per-day).
- The cell that ranks first is a different strategy (R3/S3, no EMA), fails the
  shuffle control, and rests on 23 short trades in a single month.
- 22 sessions is not a sample. It is the most Yahoo will serve at 1-minute
  resolution, and the whole timeframe table shows what numbers from samples
  that size look like.

Stay on **h1**, or **daily with weekly pivots**. Those two are the only
resolutions where this system has been shown to work, they were measured over
733 sessions and 20 years respectively, and they confirm each other.

## Files

- `scripts/gold_3min_run.py` — the aggregation, the sweep and the controls.
