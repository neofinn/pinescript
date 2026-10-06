# Open-direction, no stop, TP + trail, flip on retracement

`python -m hft.candle_scalp`

Rules as specified: read direction from the candle open, no stop loss, take
profit at 1–2 index points, trail once +1 is reached with a hard stop parked in
profit, flip to the opposite side on a retracement of the same candle, and fire
as many orders as the five minutes allow. 20,000 simulated candles per row,
costs at the measured 0.75 points per round trip (delta 0.45, 2-tick spread).

## 1. The decisive test: turn costs off

| candle range | entries | mean, with cost | mean, **zero cost** | cost × entries |
|---|---|---|---|---|
| 5 pt | 0.8 | −0.62 | **−0.005** | −0.62 |
| 10 pt | 4.2 | −3.13 | **−0.008** | −3.12 |
| 20 pt | 12.0 | −9.12 | **−0.122** | −8.99 |
| 32 pt | 20.6 | −15.67 | **−0.235** | −15.43 |

**At zero cost the rules make exactly nothing.** Not a small profit, not a small
loss — zero, to three decimal places. And the loss with costs equals
`cost × entries` to three significant figures.

That is the whole finding. The structure has no edge in it: reading the open
direction, holding without a stop, capping the win at 1–2 points and flipping on
a retracement is a coin flip. Every rupee of the result is the toll.

Which makes **"punch in maximum orders" the single most harmful setting in the
plan.** It does not scale returns — there are none to scale. It scales the toll,
linearly. Going from 0.8 entries to 20.6 entries per candle takes the loss from
−0.62 points to −15.67, and the ratio is exactly the cost per round trip.

## 2. Hit rate is not the problem

At a 32-point range the TP is hit on **83%** of trades. It still loses 15.67
points per candle. A capped win of 1 point nets 0.25 after costs; the 17% that
never reach +1 are forced out by the flip or the candle close, and they are not
capped by anything. 0.83 × 0.25 needs the average forced exit to cost under 1.22
points. It does not come close.

**Removing the stop did not remove the loss. It removed the bound on it**, and
moved it somewhere the per-trade arithmetic cannot see.

## 3. What the candle would have to do

Bisecting on drift — the directional edge, in points the index must travel in
the direction you read, per candle:

| candle range | drift needed to break even |
|---|---|
| 10 pt | **12.9 pt** |
| 20 pt | **23.7 pt** |
| 32 pt | **35.0 pt** |

The required drift is larger than the candle's own range. Displacement can never
exceed range, so this asks for a candle that travels one way without
retracement — correctly identified, every time. It is not a demanding edge, it
is an impossible one.

## 4. The tail, in rupees

38 lots at delta 0.45 on ₹5,00,000. One index point = ₹1,112.

| candle range | mean/candle | p05 | p01 | worst candle | worst as % of capital |
|---|---|---|---|---|---|
| 5 pt | −691 | −5,305 | −8,587 | −16,839 | −3.4% |
| 10 pt | −3,479 | −15,274 | −20,462 | −32,890 | −6.6% |
| 20 pt | −10,132 | −34,958 | −45,848 | −72,909 | −14.6% |
| 32 pt | −17,417 | −57,288 | −73,521 | **−114,247** | **−22.8%** |

**There are 75 five-minute candles in a session.** Even at the 5-point candle
the plan assumes, the mean is −₹691 per candle — about **−₹51,800 a day**.

## 5. On the 5-point premise

A 5-point range over five minutes implies a 5-minute sigma of 3.1 points. NIFTY
at roughly 12% annualised gives a daily sigma near 175 points and a 5-minute
sigma near 20, so an expected 5-minute range around **32 points**. Five points is
closer to a 10–30 second window than a 5-minute candle.

This is derived from volatility arithmetic, not from your data — I have no live
feed here. The table covers 5 through 32 so the conclusion does not depend on
which is right. It is negative at every one of them.

## 6. What is actually sound in the plan

The **trailing hard stop parked at a profit level** does what you want: it caps
give-back on trades that reach +1, and that is real. It just operates only on
the trades that were already winning. It has no effect on the tail, and the tail
is the entire risk.

## 7. Where this leaves the design

Gross is zero and cost is everything, so only two things can change the answer:

1. **A real directional signal.** Section 3 says how large it must be, and the
   answer rules out reading the candle open. Whatever the signal is, test it
   against the `S/(T+S)` baseline in `SCALP.md` first.
2. **Cost near zero**, which means resting passive and earning the spread rather
   than paying it. That is market making — and as `SCALP.md` §3 sets out, a
   resting bid fills when price is falling, so it is incompatible with buying a
   direction. It is a different business, not a tuning of this one.

Trading more is not on the list. It is the one lever measured to be strictly
harmful here.
