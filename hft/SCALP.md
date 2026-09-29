# Directional micro-scalp: 0.4–0.5 delta, 1–2 index points, limit only

`python -m hft.scalp --capital 500000 --deploy 0.5`

This is a different trade from the lag capture the rest of this package was
built for, and the difference is not a parameter. Lag capture needs no
forecast — the quote is wrong against a value you can compute. This needs one:
you are buying direction.

**A 5-point oscillation inside a candle is volatility, not edge.** If you buy
direction at random on a symmetric oscillation you win half the time, and half
a symmetric payoff minus costs is a loss. The amplitude is real and it is
comfortably above the cost floor; the entire question is whether you can call
the direction.

## 1. Your 0.4–0.5 delta band is the optimum — and the reason is not obvious

Break-even in index points, NIFTY 23,200, 3d, IV 14%, 2-tick spread:

| delta | strike | premium | statutory pts | spread pts | **cross** | passive | ticks/pt |
|---|---|---|---|---|---|---|---|
| 0.712 | 23,050 | 215.68 | 0.72 | 0.14 | 0.86 | 0.72 | 14.2 |
| 0.519 | 23,200 | 123.74 | 0.57 | 0.19 | 0.76 | 0.57 | 10.4 |
| **0.452** | **23,250** | **99.73** | 0.53 | 0.22 | **0.75** | 0.53 | 9.0 |
| 0.386 | 23,300 | 79.06 | 0.49 | 0.26 | **0.75** | 0.49 | 7.7 |
| 0.213 | 23,450 | 35.43 | 0.40 | 0.47 | 0.87 | 0.40 | 4.3 |
| 0.097 | 23,600 | 13.38 | 0.33 | 1.03 | 1.36 | 0.33 | 1.9 |
| 0.051 | 23,700 | 6.32 | 0.29 | 1.95 | 2.24 | 0.29 | 1.0 |

`breakeven_points = (0.2383% x premium + spread) / delta`

Two forces oppose each other. Statutory cost in points **falls** as delta falls
(0.72 → 0.29), because premium falls faster than delta. Spread cost in points
**rises** (0.14 → 1.95), because a fixed tick spread is a bigger index move
when each point is worth fewer ticks. The sum bottoms at **delta 0.45, 0.75
points**, and is flat across 0.30–0.60.

Below delta ~0.10 the target is finer than the price grid: one index point is
1.9 ticks at delta 0.097, so a 1-point move may not register as a price change
at all.

## 2. The 1-point target does not work

Delta 0.45, marketable limit. "By chance" is a driftless walk hitting the
target before the stop — `S/(T+S)` — which is what you get with no view at all:

| target | stop | required | by chance | **edge needed** |
|---|---|---|---|---|
| 1.0p | 1.0p | 87.4% | 50.0% | **+37.4pp** |
| 2.0p | 1.0p | 58.2% | 33.3% | **+24.9pp** |
| 2.0p | 2.0p | 68.7% | 50.0% | +18.7pp |
| 3.0p | 1.5p | 49.9% | 33.3% | +16.6pp |
| 5.0p | 2.5p | 43.3% | 33.3% | +10.0pp |

Break-even is 0.75 points. A 1-point target leaves 0.25 points of margin while
a 1-point loss costs 1.75 — hence 87.4%. **Two points is the floor, and three
with a 1.5-point stop is the first combination asking for a plausible edge.**

## 3. "Limit only" means two different things, and one of them fights you

Resting passive saves the spread (break-even 0.53 instead of 0.75):

| target | stop | required | by chance | edge needed |
|---|---|---|---|---|
| 1.0p | 1.0p | 76.3% | 50.0% | +26.3pp |
| 2.0p | 1.0p | 50.9% | 33.3% | +17.5pp |
| 3.0p | 1.5p | 45.0% | 33.3% | +11.7pp |

But **a resting bid fills when sellers hit it — which is when price is going
down.** You cannot simultaneously buy the direction and wait to be hit; passive
fills select for the trades that go against you. The version compatible with a
directional entry is a **marketable limit**: crosses now, price capped so you
never fill worse than your limit. `orders.py::price_for` already does this.

## 4. Spread is the biggest lever you control

Delta 0.45:

| spread | break-even pts | required @ 2p/1p |
|---|---|---|
| 0 ticks | 0.53 | 50.9% |
| 1 tick | 0.64 | 54.6% |
| 2 ticks | 0.75 | 58.2% |
| 4 ticks | 0.97 | 65.6% |
| 8 ticks | 1.41 | 80.4% |

Everything above assumes 2 ticks. **Measure it on your own feed before trusting
any of this** — at 4 ticks the required hit rate jumps 7 points, and at 9:15,
when you wanted to trade, spreads are at their widest.

## 5. The ratio you set is not the ratio you get

At ₹5,00,000, 50% deployed = 38 lots at ₹6,483 premium each:

| target | stop | nominal R:R | win | loss | **real R:R** |
|---|---|---|---|---|---|
| 1.0p | 1.0p | 1.00:1 | +282 | −1,950 | **0.14:1** |
| 2.0p | 1.0p | 2.00:1 | +1,398 | −1,950 | **0.72:1** |
| 2.0p | 2.0p | 1.00:1 | +1,398 | −3,066 | 0.46:1 |
| 3.0p | 1.5p | 2.00:1 | +2,514 | −2,508 | 1.00:1 |
| 5.0p | 2.5p | 2.00:1 | +4,745 | −3,624 | 1.31:1 |

Costs are charged on both outcomes — subtracted from the win **and** added to
the loss. A nominal 2:1 becomes 0.72:1. The gap widens as the target shrinks,
and at a 1-point target you are risking ₹1,950 to make ₹282.

## 6. Two traps in the sizing

**Capital-bound, not risk-bound.** A 1-point stop at delta 0.45 is ₹29 per lot.
A 2% risk budget on ₹5L would permit 342 lots; capital permits 38. Whenever the
stop is this tight, position size stops being governed by risk and starts being
governed by how much you can afford to outlay — which quietly removes the
control that was supposed to cap the damage.

**The stop is inside the noise.** The premise is an index moving 5 points
within a candle. A 1-point stop will be taken by that oscillation constantly,
independent of whether your direction was right.

## 7. If the premise is oscillation, the trade may be backwards

"Keeps doing 5 points up and down" describes mean reversion. Buying the
direction on a mean-reverting series is systematically buying the top of each
swing. The same cost arithmetic applies to fading the extremes instead, and the
hit-rate table is the test either way — but the two need opposite signals, and
which one is right is an empirical question this repo cannot answer without a
real feed.

## What to measure before building it

1. **Actual spread** on 0.40–0.50 delta contracts through the session, not just
   mid-morning. Section 4 is the sensitivity.
2. **Whether direction is predictable at 1-minute scale** at better than 33%
   for a 2:1 barrier. Everything else is arithmetic; this is the edge.
3. **Realistic fill rate on marketable limits** — a capped limit that does not
   cross is a missed trade, and missed winners do not show up in a hit rate
   computed on fills.
