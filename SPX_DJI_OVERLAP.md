# "SPX and DJI overlap on a 1-second chart and that marks the S&P bottom"

The claim, as given: put the S&P 500 and the Dow on one chart at 1-second
resolution; the two lines always interact and overlap; where they overlap is the
bottom in the S&P.

**Four measurements, and the last one is decisive: looking at the S&P alone finds
S&P bottoms better than comparing it to the Dow, in 8 of 8 configurations tested.
Adding the Dow destroys information rather than adding it.**

Data: ^GSPC and ^DJI from Yahoo, time-aligned bar by bar — 2,731 1-minute bars
(7 days), 4,680 5-minute (60 days), 5,081 hourly (2.9 years), 5,031 daily (20
years). 1 minute is the finest resolution available from any free feed; what
1-second would change is addressed in §3.

---

## 0. On a shared axis the lines cannot touch

SPX is near 7,723 and DJI near 51,177. Across every bar in the sample the
smallest gap between them is **5,871 points**.

Return correlation: 0.841 at 1m, 0.768 at 5m, 0.879 at 1h, **0.965 daily**.

So the two lines never meet on a shared price scale, and an "overlap" only
exists because the charting package gives each symbol its **own auto-scaled
axis**. That is not a market event. It is a rendering decision.

## 1. Where they cross is set by the zoom

An auto-scaled axis maps the **visible window's** [min, max] onto the pane
height. Change how much history is on screen and every crossing moves. On the
same 2,731 1-minute bars:

| visible window | sessions on screen | crossings | one every |
|---|---|---|---|
| 30 bars | 0.1 | 305 | 9.0 min |
| 60 bars | 0.2 | 250 | 10.9 min |
| 120 bars | 0.3 | 181 | 15.1 min |
| 240 bars | 0.6 | 152 | 18.0 min |
| 390 bars | 1.0 | 135 | 20.2 min |

How much do those crossing sets agree? Jaccard overlap:

| | 30 | 60 | 120 | 240 | 390 |
|---|---|---|---|---|---|
| **30** | 1.00 | 0.26 | 0.15 | 0.13 | **0.09** |
| **60** | 0.26 | 1.00 | 0.25 | 0.17 | 0.10 |
| **120** | 0.15 | 0.25 | 1.00 | 0.35 | 0.22 |
| **240** | 0.13 | 0.17 | 0.35 | 1.00 | 0.38 |
| **390** | 0.09 | 0.10 | 0.22 | 0.38 | 1.00 |

A tightly-zoomed chart and a one-session chart share **9%** of their crossings.
Same data, same two symbols, same seconds — only the zoom changed. A signal you
can relocate by scrolling is a property of the chart, not of the market.

## 2. The crossings do not mark bottoms

"Bottom" is scored with the future: SPX is the lowest close within ±k bars. No
real-time rule can see that, so this is the most generous possible scoring.
Baseline: the same number of randomly chosen bars, 400 draws.

| timeframe | window | k | crossings | bottom % | random % | pct |
|---|---|---|---|---|---|---|
| 1-minute | 60 | 10 | 250 | 1.6% | 3.6% | **2** |
| 1-minute | 60 | 30 | 247 | 0.4% | 1.2% | **3** |
| 1-minute | 240 | 30 | 146 | 0.0% | 1.4% | **0** |
| 5-minute | 60 | 10 | 418 | 2.6% | 3.1% | 21 |
| 5-minute | 240 | 10 | 241 | 3.7% | 2.9% | 67 |
| 1-hour | 60 | 10 | 420 | 2.6% | 2.9% | 28 |
| 1-hour | 240 | 30 | 263 | 0.4% | 1.1% | **6** |
| daily | 60 | 10 | 416 | 1.2% | 2.9% | **0** |
| daily | 240 | 10 | 386 | 4.1% | 2.8% | 90 |

Across 16 cells the crossings land on bottoms **less often than random moments
do**. Forward returns after a crossing are likewise at or below the random
baseline in most cells. Two cells reach the 80th–90th percentile, which is what
16 tries buys you.

## 3. What 1-second would actually change

Crossings per hour of market time, at a fixed 240-bar window:

| bar size | crossings/hour | one every |
|---|---|---|
| 1-minute | 3.34 | 1,078 sec |
| 5-minute | 0.62 | 1.6 hours |
| 1-hour | 0.05 | 18.8 hours |
| daily | 0.01 | 84.7 hours |

The crossing rate is a property of the **sampling**, not the market — each step
finer multiplies it. Extrapolating that slope, a 1-second chart crosses roughly
**every 10–20 seconds of market time**.

This is where the word "always" in the claim does the damage. Something that
happens every fifteen seconds is within a few bars of every bottom in the
session — and of every top, and of every other point. A signal that fires
continuously cannot discriminate. The claim is not falsified by 1-second data;
it is rendered unfalsifiable by it.

## 4. The steelman, and the test that ends it

The one version of this idea a chart cannot distort is the **SPX/DJI ratio**. It
is scale-free, and it is a real quantity.

Tested at z < −2, it genuinely does land on SPX bottoms — 7 of 8 cells at the
97th percentile or above. That looked like something. It is not, because of how
`is_bottom` works: any signal that fires after a sharp **drop** scores well,
since a sharp drop mechanically puts you near the low of the surrounding window.

So the ratio has to be compared against the simplest signal that uses **no Dow
data at all** — the S&P's own z-score:

| timeframe | w | signal | n | bottom % | pct | fwd bps | pct |
|---|---|---|---|---|---|---|---|
| 1-minute | 60 | SPX/DJI ratio z<−2 | 213 | 4.7% | 100 | +1.93 | 86 |
| 1-minute | 60 | **SPX alone z<−2** | 239 | **7.5%** | 100 | +2.03 | 92 |
| 5-minute | 60 | SPX/DJI ratio z<−2 | 309 | 2.6% | 98 | +7.86 | 100 |
| 5-minute | 60 | **SPX alone z<−2** | 420 | **5.5%** | 100 | +2.47 | 74 |
| 1-hour | 60 | SPX/DJI ratio z<−2 | 353 | 3.7% | 100 | +19.14 | **6** |
| 1-hour | 60 | **SPX alone z<−2** | 344 | **7.6%** | 100 | **+71.19** | 100 |
| 1-hour | 240 | SPX/DJI ratio z<−2 | 242 | 3.7% | 100 | −6.56 | **0** |
| 1-hour | 240 | **SPX alone z<−2** | 233 | **4.7%** | 100 | **+84.84** | 100 |
| daily | 60 | SPX/DJI ratio z<−2 | 307 | 2.6% | 98 | +31.48 | **0** |
| daily | 60 | **SPX alone z<−2** | 294 | **9.5%** | 100 | **+281.10** | 100 |
| daily | 240 | SPX/DJI ratio z<−2 | 273 | 2.6% | 98 | +173.31 | 94 |
| daily | 240 | **SPX alone z<−2** | 220 | **5.5%** | 100 | **+280.32** | 100 |

**The S&P alone beats the SPX/DJI ratio in 8 of 8 cells on bottom detection, and
in 6 of 8 on forward return — several of them by an order of magnitude.** On the
daily chart the ratio returns +31 bps where looking at the S&P by itself returns
+281 bps against a +119 bps baseline.

Bringing the Dow in does not add information. It subtracts it: the ratio is
contaminated by Dow-specific moves that say nothing about the S&P, and the
0.965 daily return correlation means there was very little independent signal
there to begin with.

## What is actually true nearby

One real effect sits next to this claim, and it is worth separating from it.
**The S&P mean-reverts after sharp declines.** A 2-sigma drop in the index's own
z-score is followed by +281 bps over the next 30 days against a +119 bps
baseline, at the 100th percentile of its random control, over 20 years of daily
data. That is a long-documented effect.

It needs no Dow, no overlay, no dual axis, and no 1-second chart. It is visible
on a daily chart with one indicator on it.

## Verdict

The mechanism described cannot work as stated. The lines never touch on a shared
axis; the crossings exist only because of dual auto-scaling and move when you
zoom; they mark bottoms less often than random moments do; at 1-second
resolution they would fire every ~15 seconds, which is what "always interact and
overlap" already concedes; and the scale-free version of the idea is beaten by
simply looking at the S&P on its own, in every configuration tested.

## Files

- `scripts/index_overlap.py` — window-normalisation, crossing detection, the
  random-time baseline.
- `spx_dji_overlap.pine` — plots both z-scores on one pane so the §4 result is
  visible on a live chart: the ratio signal and the S&P-alone signal fire at
  nearly the same places, and the S&P-alone one is the better of the two.
