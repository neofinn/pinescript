# 9 EMA + Fibonacci pivots on NIFTY: every combination

Fibonacci pivots from the previous session — P = (H+L+C)/3, then 0.382 / 0.618 /
1.000 of the prior range — combined with a 9 EMA, swept across every
combination: **4 level groups × bounce/break × 3 EMA roles × 2 targets = 44
testable cells** on NIFTY hourly (722 sessions, 3 years), checked against NIFTY
15-minute and BANKNIFTY.

**The best-ranked combination is the one the control most firmly rejects.
R2/S2 bounce against the EMA returns +0.057 R — and scores at the 0th
percentile of its own shuffle control, because shuffled data returns +0.245.
Nothing survives all three checks.**

---

## 1. The sweep

44 cells on NIFTY h1, **5 with positive average R**:

| levels | mode | EMA 9 | target | n | avg R | PF |
|---|---|---|---|---|---|---|
| **R2/S2** | bounce | **counter** | RR 2.0 | 153 | **+0.057** | 1.14 |
| **P** | bounce | **aligned** | RR 2.0 | 148 | **+0.040** | 1.11 |
| R1/S1 | bounce | counter | RR 2.0 | 209 | +0.037 | 1.09 |
| P | bounce | none | RR 2.0 | 213 | +0.010 | 1.02 |
| R1/S1 | break | counter | RR 2.0 | 144 | +0.002 | 1.01 |

Everything else is negative, the worst at −0.204.

## 2. Real structure in the grid

Averaged over both targets, NIFTY h1:

| levels | mode | EMA none | EMA aligned | EMA counter |
|---|---|---|---|---|
| **P** | bounce | −0.046 | **−0.002** | −0.157 |
| P | break | −0.051 | −0.057 | — |
| **R1/S1** | bounce | −0.094 | −0.152 | **+0.012** |
| R1/S1 | break | −0.098 | −0.095 | −0.016 |
| **R2/S2** | bounce | −0.062 | −0.118 | **−0.007** |
| R2/S2 | break | −0.076 | −0.111 | −0.046 |
| R3/S3 | bounce | −0.162 | −0.138 | −0.166 |
| R3/S3 | break | −0.099 | −0.125 | −0.122 |

Three things are consistent and worth keeping regardless of the verdict:

- **Bounce and break want opposite EMA conditions.** At R1/S1 a bounce is
  +0.012 counter-EMA and −0.152 aligned — a 0.164 R gap in the opposite
  direction to the usual "trade with the EMA" advice. Mean reversion wants
  price *extended against* the short-term average, which is mechanically
  sensible.
- **P is not like the outer levels.** At P the ordering reverses: aligned
  (−0.002) beats counter (−0.157). P behaves as a trend-continuation level,
  R1/R2 as reversion levels.
- **R3/S3 is useless.** All eight cells negative, none better than −0.099.
- **RR 2.0 beats the "next pivot" target in almost every row** — the next
  Fibonacci level is simply too close to pay for the stop.

## 3. The shuffle control inverts the ranking

Bars reordered **within each session**. The pivots come from the *previous*
session so they are untouched; only the intraday path is destroyed. 40 shuffles:

| cell | n | real | shuffled median | shuffled best | pct |
|---|---|---|---|---|---|
| **R2/S2 bounce counter RR2** (the best cell) | 153 | **+0.057** | **+0.245** | +0.352 | **0** |
| R1/S1 bounce counter RR2 | 209 | +0.037 | +0.206 | +0.346 | **0** |
| **P bounce aligned RR2** | 148 | **+0.040** | −0.222 | −0.143 | **100** |

The two best-ranked cells sit at the **0th percentile**: the strategy makes four
times as much on shuffled sessions as on real ones.

That is not a quirk, it is the mechanism. **Shuffling destroys trends, and a
bounce strategy is a bet against trend.** A scrambled session oscillates, so
"touch the level and close back" is followed by more oscillation. A real session
trends, so a touch of R2 is more often followed by continuation through it. The
+0.057 is the geometry of a 2R bet with a tight stop, not information in the
pivot level — and the real market takes ~0.19 R away from it.

**P bounce aligned is the only cell that beats its control**, at the 100th
percentile, and by a wide margin (+0.040 against a best shuffle of −0.143).

## 4. Out of sample

| cell | 1st half | 2nd half | BANKNIFTY |
|---|---|---|---|
| R2/S2 bounce counter RR2 | +0.172 (n=85) | **−0.087** (n=68) | +0.007 (n=169) |
| R1/S1 bounce counter RR2 | +0.056 (n=103) | +0.018 (n=106) | **−0.062** (n=213) |
| **P bounce aligned RR2** | **+0.020** (n=86) | **+0.069** (n=62) | **−0.186** (n=165) |

- The headline cell **fails the second half** (−0.087). Its +0.057 is a
  first-half number.
- The one cell that passes the shuffle control and is positive in **both**
  halves — P bounce aligned — is **−0.186 on BANKNIFTY**, the nearest available
  out-of-sample index.

And 44 cells were searched. The expected best of 44 draws from a null
distribution already sits at the **97.8th percentile**, so one cell clearing 95%
on its own is what nothing looks like.

## Verdict

**No combination survives.** Each candidate fails a different check, and the
checks disagree with the raw ranking in a way worth remembering:

| | best avg R | beats shuffle | both halves | other index |
|---|---|---|---|---|
| R2/S2 bounce counter | ✅ | ❌ (0th) | ❌ | ~0 |
| R1/S1 bounce counter | — | ❌ (0th) | ✅ | ❌ |
| P bounce aligned | — | ✅ (100th) | ✅ | ❌ |

**Ranking by return picked the cell the control rejects hardest.** If this grid
had been run and the top row traded — which is what "best executing
combination" normally means — the chosen strategy would have been the one most
clearly explained by the geometry rather than the market.

What is worth keeping is §2: bounce and break want opposite EMA conditions, P is
a trend level while R1/R2 are reversion levels, R3/S3 does nothing, and the next
pivot is too close to use as a target. Those hold across the whole grid rather
than resting on one cell.

## Files

- `scripts/pivot_ema.py` — Fibonacci pivots, the 9 EMA roles, and the
  bounce/break runner.
- `pivot_ema9_nifty.pine` — the levels and the EMA on a chart, with the mode
  and EMA role as inputs and the measured caveats in the header.
