# The inside-bar breakdown short, on gold

Same pattern, gold chart: a 30-minute candle makes the high, a small candle
forms inside it, short the break of the inside candle's low.

**Gold is the best this pattern has looked. It is still not an edge.** The
30-minute chart returns +0.144 R per trade — but on 38 trades, with a 95%
confidence interval of **[−0.293, +0.597]**. Every larger gold sample is
significantly negative, and two ETFs holding the identical metal over the
identical 60 days disagree about the sign.

---

## Data

| series | bars | window |
|---|---|---|
| **GC=F 30m** — the requested chart | 2,276 | 2026-07-21 → 09-29 |
| GC=F h1 | 13,737 | 2024-05-07 → 2026-09-29 |
| GC=F 1D | 5,030 | 2006-09-29 → 2026-09-29 |
| GLD 30m / h1 / 1D | 779 / 5,079 / 5,030 | |
| IAU, GDX, GDXJ 30m | 779 each | 2026-07-07 → 09-29 |
| SI=F, PL=F 30m | 2,278 / 2,273 | 2026-07-21 → 09-29 |

Costs: 0.6 bps round turn on GC/SI futures, 3.0 bps on the ETFs.

## The grid

192 parameter cells, each against 200 draws of its own price-matched random
control:

| series | cells | positive total R | beat 95th pct of own control | expected best under the null | observed best |
|---|---|---|---|---|---|
| **GOLD 30m (GC=F)** | 42 | **17** | 1 | 97.7th | **96th** |
| GOLD h1 (GC=F) | 48 | 0 | 0 | 98.0th | 78th |
| GOLD 1D (GC=F, 20 yrs) | 48 | 0 | 0 | 98.0th | 93rd |
| GLD 30m | 6 | 3 | 0 | 85.7th | 90th |
| GLD h1 | 48 | 9 | 20 | 98.0th | 100th |

Gold 30m is genuinely the standout: 17 of 42 cells end positive, against 5 of
288 across all the markets tested previously. The best cell — lookback 20, RR
2.0, stop at the inside bar, entry on the close — returns PF 1.79 on a 54.2%
win rate.

**And it still does not clear its own bar.** The best of 42 cells reaches the
96th percentile where the expected best of 42 draws from a null distribution is
the 97.7th. Picking the winner out of 42 tries is the reason it looks good.

GLD h1's 20/48 is the same trap seen elsewhere in this project: the pattern
losing *less than random shorting does* in a metal that rose. 9 of those 48
cells are actually profitable.

## The confidence intervals

Average R per trade, 20,000-resample bootstrap, at the pattern's own settings:

| series | n | avg R | 95% CI | excludes zero |
|---|---|---|---|---|
| **GOLD 30m** | 38 | **+0.144** | **[−0.293, +0.597]** | **no** |
| GOLD h1 | 248 | −0.429 | [−0.570, −0.281] | **yes** |
| GOLD 1D | 76 | −0.246 | [−0.523, +0.052] | no |
| GLD h1 | 99 | −0.062 | [−0.343, +0.219] | no |
| SI 30m | 35 | +0.085 | [−0.380, +0.576] | no |
| **pooled, 7 gold-complex series at 30m** | 158 | **−0.016** | [−0.230, +0.198] | no |
| **pooled gold at h1, 2.4 yrs** | 347 | **−0.325** | [−0.452, −0.192] | **yes** |
| **pooled gold at 1D, 20 yrs** | 137 | **−0.398** | [−0.591, −0.186] | **yes** |

The only positive number in the table has an interval four times its own width.
Both intervals that exclude zero are negative, and they are the two largest
samples.

## Timeframe or window?

Gold h1 sits at the 4th–6th percentile of its own control over 2.4 years — worse
than shorting gold at random. Two explanations were distinguishable, so both
were tested:

| | n | avg R |
|---|---|---|
| 30m, the 60-day window | 38 | **+0.144** |
| h1, all 2.4 years | 248 | −0.429 |
| **h1, restricted to the same 60 days** | 19 | **−0.363** |

Gold rose 3.7% across that window. The same 60 days on the hourly chart loses,
so the 30-minute result is not the summer of 2026 being kind to shorts. If it
were anything, it would have to be something the 30-minute bar holds and the
hourly does not.

## The check that settles it

**GLD and IAU are both physically-backed gold ETFs.** Same metal, same exchange
hours, same 60 days, same 30-minute bars. Nothing about gold can differ between
them.

| | n | avg R | 95% CI |
|---|---|---|---|
| GLD 30m | 11 | **−0.366** | [−1.123, +0.428] |
| IAU 30m | 12 | **+0.062** | [−0.702, +0.861] |

They disagree in sign, by 0.43 R. The difference cannot be information about
gold — it can only be sampling noise, and it is larger than the effect being
measured. Across the whole complex in that window the signs scatter the same
way: GC +0.144, IAU +0.181, GDX +0.400, SI +0.085, GLD −0.282, PL −0.338.

## Where gold does differ

One thing genuinely separates gold from the earlier markets. On the broad
40-symbol universe, deleting the inside-bar rule *improved* results — the inside
candle was dead weight. On gold it does not:

| variant | short | long (mirror) |
|---|---|---|
| full pattern | **−0.122** | −0.262 |
| drop the inside-bar rule | −0.282 | −0.229 |
| drop the new-high rule | −0.246 | −0.255 |

(mean across the five gold-complex series)

On gold the full pattern is the best short variant, and the long mirror is worse
than the short — the directional asymmetry the pattern is supposed to have. That
is the right shape. It is driven by the 30m and gold-complex samples, both of
which have fewer than 50 trades, and it reverses on gold h1, where the full
pattern (−0.429) is worse than either ablation (−0.398, −0.305).

## Exit mix

| series | trades | stopped | target | timed out | of those resolved, hit target |
|---|---|---|---|---|---|
| GOLD 30m | 38 | 55% | 34% | 11% | **38.2%** |
| GOLD h1 | 248 | 77% | 18% | 6% | 18.8% |
| GOLD 1D | 76 | 74% | 24% | 3% | 24.3% |

A driftless random walk with a stop at *r* and a target at *2r* resolves in the
target's favour 33.3% of the time. Gold 30m beats that at 38.2% — on 35 resolved
trades. Gold h1 and daily fall well short, on 236 and 74.

## Verdict

Run it on a gold chart and it will look better than it looked anywhere else, and
the 30-minute chart is where it looks best. What the measurement says is that
this is 38 trades in one 60-day window: the interval spans zero, the best of 42
parameter cells does not clear the bar set by having tried 42, the same metal at
hourly and daily resolution is significantly negative over 2.4 and 20 years, and
the identical asset in two different ETF wrappers gives opposite signs over the
same period.

If you want to trade it on gold anyway, the honest framing is that you would be
taking a position on a 38-trade sample, not on a demonstrated edge — and the
20-year daily and 2.4-year hourly records on the same metal both point the other
way.
