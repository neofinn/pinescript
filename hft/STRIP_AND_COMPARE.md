# Buy every option to 30 delta — and how it compares

`python -m hft.strip` · `python -m hft.compare`

## 0. Today's open: I could not read it

Checked at **09:02:45 IST, Thu 17 Sep 2026** — pre-open was live at that moment.
`api/market-data-pre-open?key=NIFTY` returned **403**, `api/allIndices` returned
403, BSE returned a redirect. No pre-open analysis exists below, and none is
invented. Everything here is arithmetic over Black-Scholes plus the measured
statutory cost stack, or simulation that is labelled as such.

## 1. Buying out to 30 delta selects the worst ratios on the board

The number that governs any held option is `theta_per_day / delta` — index
points per day needed just to stand still. Decay measured by **revaluation**,
not by BS theta, which is a derivative and overstates discrete decay so badly
near expiry that it prints a larger daily loss than the far legs are worth:

| strike | delta | premium | 1-day loss | % of premium | pts/day to stand still |
|---|---|---|---|---|---|
| **ATM 23,200** | 0.519 | 123.74 | −23.65 | **19%** | **45.5** |
| 23,400 | 0.265 | 47.15 | −17.82 | 38% | 67.2 |
| 23,500 | 0.168 | 26.12 | −12.70 | 49% | 75.8 |
| 23,600 | 0.097 | 13.38 | −7.95 | 59% | 81.8 |
| 23,800 | 0.025 | 2.75 | −2.14 | **78%** | **86.2** |

The ratio **rises monotonically as you go out**. Cheap options are cheap because
they are unlikely to matter, and they need the biggest move to stand still.
Buying the whole band to 30 delta is a deliberate selection of the worst ones.

That is not automatically wrong — it is what buying convexity costs. But it
makes this a bet on the **size** of the move, not its direction.

## 2. "Let them move" is the whole risk

9 legs, 23 lots each, ₹244,481 outlaid (49% of ₹5L), net delta 1,578:

| hold | decay | per minute | points needed in your direction |
|---|---|---|---|
| 1 min | −336 | −336 | 0.21 |
| 5 min | −1,680 | −336 | **1.06** |
| 60 min | −20,032 | −334 | 12.70 |
| full day | −118,969 | −317 | **75.40** |

At five minutes the bar is small. Overnight it is ruinous — **25% of capital per
day** in decay. The instruction "let them move" is precisely the part that
decides which of those two you get.

Against the same money in one ATM strike, the strip only wins above roughly
**+150 to +200 points**. Below that, ATM is better per rupee.

## 3. Against the other two strategies, same paths, same signal

3,000 five-minute candles, 32-point range, ₹5L at 50% deployed. All three read
the **same** open-direction signal. "Drift" is how many points the candle
travels, on average, in the direction the open pointed.

| drift | A: candle scalp | B: 2pt TP / 1pt stop | C: OTM strip |
|---|---|---|---|
| 0 pt | −17,382 | −2,133 | **−774** |
| 2 pt | −17,430 | −2,142 | **−701** |
| 5 pt | −17,170 | −2,153 | **−419** |
| 10 pt | −15,541 | −2,173 | **+502** |
| 20 pt | −10,607 | −2,122 | **+4,095** |
| entries/candle | ~21 | ~2.6 | **1** |

**C wins at every level and is the only one that ever turns positive.** The
signal is identical for all three, so this is not about forecasting. It is how
many times each pays the toll: about 21 times a candle, 2.6 times, once.

At zero drift the strip loses only ₹774 against the scalp's ₹17,382 — long
gamma harvests the 32-point range regardless of direction, which is the one
thing none of the scalping variants can do.

> Correction made while running this: `run_candle` had no stop-loss concept at
> all, so strategy B's "1-point stop" was never enforced in a first pass. A real
> `stop_points` is now implemented; the no-stop results in `CANDLE_SCALP.md` are
> unchanged (regression: 20.6 entries, −15.67 points, identical).

## 4. The finding that should change the plan: it is short volatility

Every table above holds IV fixed at 14%. The strip is long vega, and that
assumption flatters it. A 5-minute hold:

| IV after | +0p | +10p | +20p | +40p |
|---|---|---|---|---|
| 14.0% (flat) | −2,235 | +13,899 | **+30,891** | +67,568 |
| 13.5% | −27,110 | −11,940 | +4,078 | +38,785 |
| 13.0% | −50,722 | −36,525 | **−21,493** | +11,214 |
| 12.0% | −93,993 | −81,761 | −68,724 | −40,090 |

**One volatility point costs roughly what a 20-point index move earns.** At +20
points, flat IV pays +₹30,891; the same move with IV one point lower loses
₹21,493 — a ₹52,000 swing from vol alone.

IV is at its highest at the open and routinely falls once the session settles.
**9:15 is the worst moment of the day to put on a long-vega position**, which is
exactly when the plan calls for it. The strip's win in section 3 is conditional
on a vol assumption that the open specifically violates.

## 5. What the three tests together actually say

The dominant variable across everything measured in this project is **how many
times you pay the toll**, not signal quality, order rate, or delta selection:

- 21 tolls a candle: −17,382, never recoverable by any drift tested
- 2.6 tolls: −2,133, flat and never positive
- 1 toll: the only structure that turns positive, at 10 points of drift

That is the opposite of "punch in maximum orders." Trading **less** is what
moved the needle, every time it was measured.

## 6. Before any of this is real

1. **Measure IV through the first 30 minutes.** Section 4 makes this the single
   largest risk in the strip, and it is measurable the moment you have a feed.
2. **Confirm the strike band actually quotes.** The 0.025-delta leg is ₹2.75;
   its spread may be a large share of its own price, and none of these tables
   price that.
3. **Decide the hold, explicitly.** Five minutes and one day are different
   trades by a factor of 70 in decay.
