# Both strategies on SPY and QQQ options

There is **no historical intraday option data** available here, so this is a
model — but it is calibrated to the real chain, pulled from CBOE today, not
invented:

| | SPY | QQQ |
|---|---|---|
| spot | 761.69 | 722.05 |
| strike spacing | $1 | $1 |
| ATM bid/ask | 2.36 / 2.38 | 2.39 / 2.42 |
| **ATM spread, % of premium** | **1.1%** | **2.4%** |
| ATM volume (nearest expiry) | 25k–75k / strike | 14k–60k / strike |

Yahoo's options endpoint now returns 401; CBOE's delayed chain is public and was
used instead.

**A note on the implied vol.** The chain's own `iv` field (6.9% / 8.9%) does not
reconcile with its own mid prices. Solving IV from the quotes shows why: on a
near-dated contract only **σ√T** is pinned — 15.4% at one day and 8.4% at three
days reprice the same $2.37 quote identically. So the expected move is what
carried forward (0.81% of spot), paired with a one-day clock to stay
self-consistent.

Each trade from the underlying backtests was re-priced as the option trade it
would have been: buy at the ask, sell at the bid, $0.65/contract each way, time
decayed over the actual hold.

---

## The headline number, and why it is not a result

**Strategy A, SPY, 0DTE ATM: PF 2.15, +73% return on outlay.**

The underlying version of that same strategy **loses** (PF 0.94). Here is what
produced the difference:

| | SPY | QQQ |
|---|---|---|
| trades | 48 | 53 |
| **median trade** | **−98.3%** | **−97.7%** |
| expire worthless | **46%** | — |
| **top 1 trade** | **78% of all net** | **122% of all net** |
| top 2 trades | 104% of net | — |
| net without the single best trade | +15.9% (from +73%) | — |
| worst losing streak | **9 in a row** | 7 in a row |
| max drawdown | **9.1× the average bet** | 11.1× |

That is a lottery-ticket payoff, not an edge. Long premium caps the loss at 100%
and leaves the upside open, so **convexity alone flips the sign of the mean
while the typical trade is a near-total loss**. It is the defining property of
buying options, and it is exactly what the premium charges for. With one trade
worth 78% of the result, there is no statistical claim available at all.

Going further out of the money makes the illusion stronger and the reality
worse: SPY 0DTE +2 OTM shows **PF 4.44, +252%** — on a **−100% median trade**.

## A modelling problem worth naming

Strategy A's mean hold is **316 minutes on SPY**, against a mean of 48 bars
(240 min) left in the session at entry. **58% of its SPY trades and 45% of its
QQQ trades would be held past 0DTE expiry** — which cannot be done. Capping the
hold at the closing bell changes the answer by nothing (PF 2.15 either way),
because by then the option is already near-worthless or deep in the money. The
binary outcome is baked in.

Put plainly: **A is not a 0DTE strategy.** Its holding period is longer than the
instrument's remaining life.

## Strategy B

Short holds (42–53 min) and it loses on options almost everywhere:

| contract | SPY PF | QQQ PF |
|---|---|---|
| 0DTE ATM | 0.77 | 1.49 |
| 0DTE +2 OTM | 0.50 | 2.35 |
| 1DTE ATM | 0.59 | 0.93 |
| weekly ATM | 0.52 | 0.67 |

QQQ's 0DTE numbers are the same lottery shape — median trade −24% and −42%.
Everything dated beyond 0DTE loses on both names, which is what a short hold
does against a spread charged as a percentage of premium.

## What actually carries across

Longer-dated contracts strip the convexity out and show the signal underneath:

| | SPY A | QQQ A | SPY B | QQQ B |
|---|---|---|---|---|
| underlying PF | 0.94 | 0.38 | 0.82 | 0.95 |
| weekly ATM PF | 1.14 | 0.41 | 0.52 | 0.67 |

Once you stop buying the tail, the option result tracks the underlying result —
and the underlying result is the one already established: median PF 0.587/0.699
for A, 1.050/0.884 for B, with an in-sample to out-of-sample rank correlation of
**+0.006 and +0.067**.

## Verdict

**Options do not rescue either strategy.** The one figure that looks like a win
is 48 trades in which 46% expire worthless, the median loses 98%, one trade is
78% of the profit, and the path includes nine consecutive total losses and a
drawdown of nine times the average bet.

If that trade had landed outside the two-month window, the same table would read
**−40%** instead of +73%. Nothing about the strategy would have changed.

## Caveats

- Modelled, not real option prices. Spread, strike spacing and expected move are
  from today's chain; IV is held constant, so no vol crush, no skew, no smile.
- A constant IV **flatters** long premium: a real 0DTE bought in the morning and
  held into the afternoon usually sees IV fall.
- Two months, 48–53 trades per cell. Far too few for a tail-driven payoff, where
  the answer lives entirely in how many tails the window happened to contain.
