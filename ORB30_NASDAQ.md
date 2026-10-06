# Nasdaq: first 30-minute candle break, 1:2 reward-to-risk

The first M30 candle of the regular session sets a range. A break of its high
goes long, a break of its low goes short, the stop is the other side of that
range, and the target is twice the risk.

**On the Nasdaq it returns −0.143 R per trade. Only 6.4% of trades ever reach
the 2R target; 58.9% never resolve at all and exit at the bell. Of the trades
that do resolve, 15.7% hit the target where a driftless random walk pays 33.3%.
The 1:2 target is the problem — at 1:1 the same setup is nearly break-even.**

---

## Sample, stated up front

Yahoo caps 30-minute data at 60 days and **refuses** `period1`/`period2`
requests beyond it — I verified this rather than assuming, and every window
older than 60 days returns an HTTP error. So this is ~60 sessions per
instrument: **227 Nasdaq trades**, and **1,101 across 20 markets**. The
20-market pooled figure is the more reliable one, and it agrees with the
Nasdaq-only result.

Sessions are resolved in each market's own local time with a real timezone
database, so "the first 30-minute candle" is the 09:30 ET bar and not the first
bar of the UTC day. That matters: NQ trades nearly 24 hours, and its first UTC
bar is an overnight bar with no relation to the open.

Fills: the break level, or the bar's open when the bar gapped through it. A bar
touching both stop and target is scored a loss.

## 1. The Nasdaq, as asked

| market | sessions | n | avg R | PF | win % | hit target | stopped | open at close |
|---|---|---|---|---|---|---|---|---|
| NQ | 49 | 48 | −0.115 | 0.73 | 43.8 | 6% | 35% | 58% |
| QQQ | 60 | 59 | **−0.218** | 0.53 | 40.7 | 2% | 39% | 59% |
| NDX | 60 | 60 | −0.175 | 0.62 | 48.3 | 5% | 40% | 55% |
| IXIC | 60 | 60 | −0.061 | 0.86 | 43.3 | 8% | 35% | 57% |
| **POOLED** | | **227** | **−0.143** | **0.68** | 44.1 | **5%** | 37% | **57%** |

The `win %` column reads 44% and is misleading on its own: it counts any
positive R, including the many trades that merely drift a little before the
close. **The share that actually reached 2R is 5%.**

## 2. The geometry, which explains the whole result

The stop is the opposite side of the opening range, so **risk = one range**.
Entry is at the range edge, so the 2R target sits **three range widths from the
far side**. The day must extend two full opening ranges beyond the breakout,
inside the remaining six hours, without first giving back one.

Pooled over 20 markets, 1,101 trades:

| outcome | count | share |
|---|---|---|
| reached the 2R target | 71 | **6.4%** |
| stopped at the range | 382 | 34.7% |
| **still open at the close** | **648** | **58.9%** |

**Of the 453 that resolved, 15.7% hit the target. A random walk pays 33.3%.**

The setup resolves at less than half the rate chance would give it. That is the
measurement, and it is not close.

## 3. The target is the problem, not the entry

| stop | RR | n | avg R | PF | target hit % of resolved |
|---|---|---|---|---|---|
| full range | **1.0** | 227 | **−0.025** | **0.94** | **50.7%** |
| full range | 1.5 | 227 | −0.114 | 0.74 | 27.6% |
| full range | **2.0** | 227 | **−0.143** | 0.68 | **12.4%** |
| full range | 3.0 | 227 | −0.145 | 0.68 | 2.3% |
| half range | 1.0 | 227 | −0.399 | 0.43 | 27.1% |
| half range | 2.0 | 227 | −0.359 | 0.54 | 17.5% |
| half range | 3.0 | 227 | −0.530 | 0.36 | 6.6% |

At **1:1** the target is hit 50.7% of resolved trades — exactly the random-walk
value for a symmetric bet — and the strategy is within costs of break-even at
−0.025 R.

At **1:2** the hit rate collapses to 12.4% against the 33.3% chance would give.
The market is simply not handing out two-opening-range extensions from a
breakout point.

**Halving the stop is much worse**, in every column. Same finding as everywhere
else in this repo: a tight stop sits inside ordinary noise.

## 4. Opening-range width is the entire ranking

| market | median OR width | avg R |
|---|---|---|
| TSLA | 204 bp | −0.076 |
| **NVDA** | 142 bp | **+0.070** |
| MSFT | 134 bp | −0.050 |
| AMZN | 122 bp | −0.059 |
| **AAPL** | 115 bp | **+0.100** |
| CL | 83 bp | −0.049 |
| QQQ | 57 bp | −0.218 |
| NQ | 55 bp | −0.115 |
| NDX | 52 bp | −0.175 |
| … | | |
| SPX | 31 bp | −0.177 |
| **SPY** | 31 bp | **−0.292** |
| ES | 29 bp | −0.194 |

**Correlation between opening-range width and average R: +0.617.**

- wide openers (≥80 bp, 6 markets): mean **−0.011**
- narrow openers (<50 bp, 10 markets): mean **−0.165**

Only 2 of 20 markets are positive, and both are wide-opening single names
(AAPL, NVDA).

**This is why the Nasdaq result is poor.** QQQ, NQ, NDX and IXIC all open with
46–57 bp ranges, putting them in the narrow half. A narrow opening range means
a tight stop relative to the day's noise, and the stop gets taken before the
extension arrives.

## 5. The opening range does carry information

Bars reordered **within each session after the opening-range bar**. The opening
range itself is unchanged; only the order in which price visits the rest of the
day is destroyed. 40 shuffles:

| | real | shuffled median | shuffled best of 40 | pct |
|---|---|---|---|---|
| Nasdaq | **−0.143** | −0.416 | −0.380 | **100** |
| all 20 markets | **−0.122** | −0.400 | −0.357 | **100** |

The real sequence beats **every one of 40 shuffles**, by about +0.24 R over the
best of them. The opening range is a genuine structural level — breaking it
really does mean something about the rest of the session.

It is just not worth 2R.

## Verdict

- **Do not take this at 1:2 on the Nasdaq.** −0.143 R per trade, and only 5% of
  trades ever see the target.
- **1:1 is a different proposition**: −0.025 R, PF 0.94, and the target hit at
  exactly the random-walk rate. That is a fair bet losing to costs, not a bad
  one.
- **If you trade opening ranges, trade wide ones.** The width correlation is
  +0.617 and the only two positive markets of twenty are AAPL and NVDA, which
  open three times wider than QQQ. The Nasdaq index products are among the
  narrowest in the sample.
- Never halve the stop. Every column gets worse.

Caveat kept in view: 60 sessions per instrument is what the data allows, so the
Nasdaq-specific numbers rest on about two and a half months. The 20-market,
1,101-trade pooled result points the same way, which is the main reason to
believe the Nasdaq reading.

## Files

- `scripts/orb30.py` — session resolution by timezone, the opening range, and
  the breakout trade.
- `orb30_nasdaq.pine` — the setup on a chart, with the measured RR warning.
