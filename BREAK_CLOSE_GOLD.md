# The H1 break-close pattern, on gold

Same pattern — hourly candle closes red, next closes below its low → short with
the main candle's high as the stop; green and a close above the high → long with
its low as the stop — run on gold and the whole metals complex.

**As stated it is a disaster on gold: 0.244× against buy-and-hold's 1.76× over
the same 2.4 years. The body filter rescues it to roughly breakeven. It still
lost to simply holding in 7 of 7 complex members.**

---

## Data

| series | bars | window | cost |
|---|---|---|---|
| **GC=F h1** — the asked timeframe | 13,722 | 2024-05-12 → 2026-10-02 | 1 bp |
| GC=F 15m / 30m | 4,488 / 2,246 | 60 days | 1 bp |
| GC=F h4 (aggregated from h1) | 3,711 | 2.4 yrs | 1 bp |
| GC=F daily | 5,030 | **20 years** | 1 bp |
| GLD, IAU, GDX, GDXJ h1 | 5,080 each | 2.9 yrs | 3–4 bps |
| SI=F, PL=F h1 | 13,721 / 13,710 | 2.4 yrs | 1.5 / 3 bps |

## 1. The pattern as stated, gold hourly

| RR | hold | SHORT avg R | LONG avg R | combined R |
|---|---|---|---|---|
| 1.0 | 24 | −0.151 | −0.034 | −203.5 |
| 2.0 | 24 | −0.112 | −0.003 | −98.4 |
| 3.0 | 24 | −0.105 | +0.022 | −64.8 |
| 5.0 | 48 | −0.147 | +0.071 | **−45.0** |
| 8.0 | 48 | −0.219 | +0.116 | −54.4 |

**Cells with a positive combined total: 0 / 18.** The "maximum" is −45R, the
least negative. Short is negative in all 18; long only goes positive at wide
targets, which is the drift-capture pattern seen across all 30 markets.

## 2. Every gold timeframe agrees

| series | bars | SHORT avg R | LONG avg R | combined R |
|---|---|---|---|---|
| GC 15m | 4,488 | −0.175 | −0.107 | −83.2 |
| GC 30m | 2,246 | −0.140 | −0.092 | −32.4 |
| GC h1 | 13,722 | −0.112 | −0.003 | −98.4 |
| GC h4 | 3,711 | −0.160 | +0.075 | −13.5 |
| **GC daily, 20 years** | 5,030 | −0.143 | +0.123 | **−1.0** |

Short loses at every resolution from 15 minutes to daily, across 20 years.
The daily combined total of −1.0R over two decades is as close to exactly
nothing as a measurement gets.

## 3. The body filter

The one knob that measurably helped across the 30-market study — requiring the
main candle's body to be a real fraction of its range, not a red close by a
tick. It was chosen **before** gold was looked at, so applying it here is a
genuine out-of-sample use.

| body ≥ | RR | SHORT avg R | LONG avg R | combined R |
|---|---|---|---|---|
| 0.0 | 3.0 | −0.105 | +0.022 | −64.8 |
| **0.3** | **3.0** | **+0.012** | **+0.069** | **+54.8** |
| 0.5 | 3.0 | −0.022 | +0.086 | +37.7 |
| 0.7 | 3.0 | −0.040 | **+0.184** | +54.4 |

It flips gold from −64.8R to +54.8R. That is the strongest single improvement
any filter has produced in this repo.

## 4. The control, and the confidence intervals

300 price-matched draws per cell on GC h1:

| body | RR | side | n | total R | control median | pct | avg R | 95% CI |
|---|---|---|---|---|---|---|---|---|
| 0.0 | 2.0 | short | 855 | −95.8 | −157.2 | 98 | −0.112 | [−0.199, −0.025] |
| 0.0 | 2.0 | long | 892 | −2.6 | −214.0 | 100 | −0.003 | [−0.088, +0.085] |
| 0.3 | 3.0 | short | 621 | +7.2 | −102.9 | 100 | +0.012 | [−0.109, +0.136] |
| 0.3 | 3.0 | long | 693 | +47.6 | −106.4 | 100 | +0.069 | [−0.047, +0.186] |
| 0.7 | 3.0 | **long** | 363 | +66.9 | −7.2 | 100 | **+0.184** | **[+0.022, +0.351]** |

The information content is real and large — 98th to 100th percentile against the
control, the same as across all 30 markets.

**Exactly one cell has a confidence interval excluding zero**: body ≥ 0.7, RR
3.0, long. That is one out of roughly 26 cells examined on this instrument. At
95% confidence, 26 tries produces about 0.65 false positives per tail by
construction. One is what you expect from nothing.

## 5. The complex disagrees with itself

RR 3.0, body ≥ 0.3 — the configuration that looked best on gold:

| series | SHORT avg R | LONG avg R | combined R | 95% CI on combined |
|---|---|---|---|---|
| GC gold futures | +0.012 | +0.069 | +54.8 | [−0.043, +0.127] |
| GLD gold ETF | −0.060 | **+0.432** | +108.7 | **[+0.063, +0.350]** |
| IAU gold ETF | −0.131 | +0.335 | +63.8 | [−0.019, +0.265] |
| GDX miners | −0.114 | +0.258 | +42.1 | [−0.057, +0.211] |
| GDXJ junior miners | −0.175 | +0.209 | +17.0 | [−0.103, +0.165] |
| SI silver | −0.173 | −0.062 | −150.2 | **[−0.193, −0.035]** |
| PL platinum | −0.159 | −0.114 | −179.0 | **[−0.214, −0.056]** |
| **POOLED** | | | | **−0.007, [−0.046, +0.032]** |

Pooled across the complex the answer is **−0.007 R, dead zero**. Three intervals
exclude zero: one positive (GLD) and two negative (silver, platinum).

And the same-metal check, over the **identical** window:

| | SHORT avg R | LONG avg R |
|---|---|---|
| GC=F (gold futures, ~24h) | +0.012 | **+0.069** |
| GLD (gold ETF, US hours only) | −0.058 | **+0.426** |

Gold futures and a gold ETF holding bullion, same metal, same dates, differ by
**0.36 R** on the long side. Either the result depends entirely on which trading
session you are in, or it is noise. Both readings argue against trading it.

## 6. In money — the only test that settles it

Both sides, one position at a time, 1% of live equity risked per trade,
compounding. GC=F hourly, 2.4 years:

| variant | n | final | CAGR | max DD | **holding gold** |
|---|---|---|---|---|---|
| **as stated** (RR 2, no body filter) | 936 | **0.244×** | −44.6% | 77.1% | **1.76×, +26.6%** |
| RR 3, no body filter | 847 | 0.608× | −18.8% | 49.9% | same |
| RR 3, body ≥ 0.3 | 761 | 0.991× | −0.4% | 32.8% | same |
| RR 3, body ≥ 0.7 | 493 | **1.235×** | +9.3% | 27.9% | same |
| RR 3, body ≥ 0.3, **5% risk** | 761 | **0.176×** | −51.7% | **94.3%** | same |

The pattern as literally stated turns 1.00 into **0.244** while gold itself went
to 1.76. The best variant found anywhere reaches 9.3% CAGR against gold's 26.6%.
Raising risk to 5% destroys the account — a 94.3% drawdown.

Across the complex at the best configuration:

**Beat buy-and-hold: 0 / 7.** GLD 1.434× against 2.06×. GDX 0.821× against
3.03×. Silver 0.315× against 2.13×.

## Verdict

Gold does not rescue this pattern, and it is worth being precise about why,
because the shape of the failure is informative.

The information is real — 98th–100th percentile against the matched control on
every cell, exactly as in the 30-market study, and the body filter transfers
cleanly from that study to this one and produces the largest improvement any
filter has produced here. None of that is noise.

But everything positive lives on the **long** side, during 2.4 years in which
gold rose 26.6% a year and the miners 46–50%. The short side is negative in 7 of
7 complex members, at every timeframe from 15 minutes to 20 years of daily bars.
What the long side is capturing is the trend, and it captures it worse than
owning the metal: 9.3% against 26.6% at best, 0 of 7 beating buy-and-hold.

If the intent is to be long gold, own gold. This takes 493 to 936 trades a year
to underperform that.

## Files

- `scripts/break_close.py` — setup generation (shared with the 30-market study).
- `break_close_h1.pine` — the pattern on a chart, both sides, body filter exposed.
