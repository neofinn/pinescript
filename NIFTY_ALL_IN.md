# All in, 1R risk, ₹5 lakh — what actually happens

## First: "1R risk" and "all in" are contradictory

1R means sizing so a losing trade costs ₹5,000. All in means deploying ₹5 lakh.
You cannot do both — and the numbers show the risk limit was binding all along,
not the capital limit:

| sizing (H1, all 2026, delta_breakout RR 3.0) | n | net | final | max capital used |
|---|---|---|---|---|
| 1R, 25% premium cap | 34 | ₹8,12,382 | ₹13,12,382 | 25.0% |
| 1R, 50% cap | 34 | ₹8,11,240 | ₹13,11,240 | 43.2% |
| **1R, cap lifted to 100%** | 34 | **₹8,11,240** | ₹13,11,240 | **43.2%** |

Lifting the cap from 25% to 100% changed the result by **₹1,142** and never used
more than 43% of the account. On M5 it changed nothing at all. At ₹5,000 of
risk per trade you simply never need the rest of the money.

So "all in" only means something if the risk limit is dropped. Here is that.

## All in: full capital on every trade

| | M5 (59 sessions) | H1 (all of 2026) |
|---|---|---|
| trades taken | 9 | 16 |
| peak equity | ₹5,85,044 | **₹25,57,59,129** |
| **final equity** | **₹0** | **₹0** |
| wiped out on | trade 9, 28 Jul | trade 16, 12 May |
| worst single trade | **−111.6%** | **−111.6%** |

**Both go to zero.** The hourly path is the instructive one:

| trade | date | return | equity |
|---|---|---|---|
| 1 | 02 Jan | −44.5% | ₹2,77,399 |
| 2 | 07 Jan | −2.6% | ₹2,70,062 |
| **3** | **20 Jan** | **+6,287.9%** | **₹1,72,51,353** |
| 4 | 27 Jan | +511.4% | ₹10,54,73,869 |
| 8 | 12 Mar | +116.2% | ₹21,77,89,317 |
| … | | | peak **₹25.58 crore** |
| **16** | **12 May** | — | **₹0** |

₹5 lakh to twenty-five crore and back to nothing, in sixteen trades, by
mid-May. The remaining seven months never happen.

## Why zero is the guaranteed destination

**A single trade can lose more than the account: −111.6%.** Buying an option
risks 100% of the premium, and when the premium *is* the whole account, the
costs sit on top — the half-point spread on a cheap ATM option is around 10% of
its premium, so a worthless expiry costs the account plus about a tenth.

That is the whole mechanism. Any sizing that puts 100% of capital into a bought
option needs only one expiry-day loser to end, and the strategy loses roughly
70% of its trades. Passing through ₹25 crore first changes nothing: the
sequence has no memory, and there is no position size at which a −100% trade is
survivable.

## A number I reported earlier was wrong

A non-compounding version of this run showed **₹15.46 crore** on H1 and ₹3.07
crore on M5. Those are void. The tell was in the same table: a maximum drawdown
of **359.6% and 350.1% of capital** — a drawdown above 100% means the account
had gone negative and the simulation kept deploying ₹5 lakh it did not have.

Fixed-risk-per-trade arithmetic silently assumes the capital is always there.
For any sizing that can lose the whole account, it must compound and it must be
allowed to hit zero. Once it does, both windows end at ₹0.

## The answer for ₹5 lakh

| approach | final |
|---|---|
| 1R risk, 25% cap (H1 2026) | ₹13,12,382 |
| 1R risk, cap lifted to 100% | ₹13,11,240 |
| **all in, full capital per trade** | **₹0** |

And the ₹13.12 lakh is itself the best of 80 configurations, where random
searching the same 80 typically found more, and where three trades produce 117%
of the profit.

```
python3 scripts/nifty_maxrisk_mtf.py <data-dir>   # compounding, ruin, drawdown
```
