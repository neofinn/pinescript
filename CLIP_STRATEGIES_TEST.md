# Two clipped strategies, built and tested

Decoded both videos frame by frame, built each as a separate Pine strategy, and
ran both on the **ten highest dollar-volume instruments** — ranked from the data,
not assumed.

| rank | symbol | $ volume / 5m bar |
|---|---|---|
| 1 | SPY | 244,215,354 |
| 2 | QQQ | 208,924,405 |
| 3 | NVDA | 196,750,711 |
| 4 | TSLA | 107,289,797 |
| 5 | AAPL | 97,257,228 |
| 6–10 | AMD, MSFT, INTC, META, AMZN | 66–83 M |

5m bars, two months. IS = first half (selection), OOS = second half, spent once.
Cost = one spread each way, per instrument.

---

## A — PPS Super HMA (`pps_super_hma.pine`)

**What the clip gave exactly:** Pivot Point SuperTrend with **Pivot Point Period
2, ATR Factor 3, ATR Period 10**, Buy/Sell labels on. Those are read straight
from the Inputs tab. "PPS" in the indicator name *is* Pivot Point SuperTrend —
that is where the Buy and Sell tags come from.

**What it never gave:** the two Hull MA lengths. Only the Style tab was opened,
so the colours are known and the lengths are not.

| | median PF across 10 names |
|---|---|
| in-sample | **0.587** |
| out-of-sample | **0.699** |

**The median trade is negative on all twenty instrument-windows.** And the
winners don't persist — META scored PF 4.73 in-sample (97th percentile of its
control) and **0.46 out-of-sample (7th percentile)**.

Sweeping the unknown HMA lengths does not rescue it — this matters, because
failing a strategy on my own assumption would be my error, not its:

| HMA 1 / 2 | filter | OOS median PF |
|---|---|---|
| 9 / 21 | on | 0.79 |
| 21 / 55 | on | 0.70 |
| 34 / 89 | on | 0.66 |
| 50 / 200 | on | 0.44 |
| any | off | 0.76 |

**Every setting below 1.0.** Four of ten instruments above 1.0 in each — which
is what chance gives.

---

## B — MA pullback continuation (`ma_pullback_gold.pine`)

**What the clip gave:** GOLD, 1-minute, one slow blue MA, and one drawn trade —
a long off a pullback to the MA with a thin red stop band underneath and a long
run to the target.

**What it never gave:** anything else. No MA type, no length, no entry trigger,
no stop distance, no target. The caption ends "Comment :- Strategy" — the rules
sit behind a comment-for-access gate.

| | median PF across 10 names |
|---|---|
| in-sample | **1.050** |
| out-of-sample | **0.884** |

Sweeping the unknowns out of sample: 0.65 to 1.19 across nine MA/R combinations,
best at MA 100 / 5R — one cell out of nine, which is what nine cells produce.

### On gold, where it was actually filmed

Ten times the sample (11,139 bars). This is the only place either strategy
looked alive:

| MA | R | IS PF | **OOS PF** | OOS median trade | percentile of control |
|---|---|---|---|---|---|
| 50 | 2 | 0.78 | 1.05 | −1.51 | 80th |
| **100** | **2** | **0.88** | **1.55** | −1.08 | **99th** |
| 100 | 3 | 0.75 | 1.39 | −1.51 | 97th |
| 200 | 2 | 1.14 | 1.30 | −1.28 | 96th |
| **200** | **3** | **1.43** | **1.21** | −2.01 | 85th |

Read the two bold rows together, because that is the whole finding:

- The cell you **would have selected** on in-sample (MA 200 / 3R, IS PF 1.43)
  lands at the **85th percentile** out of sample — and its win rate is **27.8%
  against the 25% a 3R needs, binomial p = 0.308**. Not significant. Its top
  single trade is **66% of the net**; the top three are **169%**. Median trade
  **−2.01**.
- The cell that **actually scored best** out of sample (MA 100 / 2R, 99th
  percentile) had an in-sample PF of **0.88**. You would have thrown it away.

Four of six cells score *better* out of sample than in. That is not an edge
surviving — it is the second half of the window simply being kinder to gold, and
it is why in-sample ranking picked the wrong cell.

---

## The one number that settles both

Rank correlation between each instrument's in-sample and out-of-sample PF:

| strategy | Spearman ρ |
|---|---|
| A — PPS Super HMA | **+0.006** |
| B — MA pullback | **+0.067** |

An instrument's first half tells you **nothing** about its second half. That is
what no edge looks like, measured directly rather than argued.

## Caveats

- Two months, 5-minute bars. B was filmed on **1-minute**; Yahoo caps 1m at
  ~7 days, far too little to test, so the equity runs are 5m and the gold run
  is 5m. A timeframe change is a strategy change.
- A's Pivot Point SuperTrend inputs are exact; its HMA lengths are swept.
  B has no stated parameters at all, so all of it is a reconstruction of the
  single trade drawn on screen.
- Neither Pine file has been compiled — there is no Pine compiler here.
