# Daily rebalancing — total split three ways every morning

Same three index sleeves, same 5%-of-own-equity cap, same Kronos direction and
supply/demand stop. The only change: **at the start of every trading day the
whole balance is divided equally three ways.**

## The replay is validated before it is used

Each trade is recorded with the equity it was sized against, so its return can
be applied to a different capital level. Position size is an integer number of
lots, so that proportionality is approximate — and an approximation that is not
checked is just an assumption.

| | |
|---|---|
| true independent run | ₹42,11,559 |
| replayed with rebalancing **off** | ₹42,11,559 |
| **error** | **0.00%** |

The replay reproduces the engine exactly, so the rebalanced figure below means
what it says.

## Result

| scheme | final | × | maxDD |
|---|---|---|---|
| independent sleeves | ₹42,11,559 | 2.81 | 16.0% |
| **rebalanced to 1/3 every morning** | **₹43,09,089** | **2.87** | **14.9%** |

Rebalancing improved the total by **+2.3%** and cut drawdown by **1.1 points**.

## I expected this to cost money and it did not

My prediction was that rebalancing would reduce the total, because it moves
capital out of whatever just won and into whatever just lost — and here that
means repeatedly selling NIFTY at 3.84× to buy SENSEX at 1.02×. Cutting the
winner to fund the loser should hurt.

It helped slightly instead, and the reason is the **rebalancing bonus**: when
sleeves have genuinely low correlation and their *relative* performance
oscillates, systematically selling the recent winner and buying the recent loser
harvests that oscillation. The correlations here are 0.035 (BANKNIFTY/SENSEX),
0.395 (NIFTY/BANKNIFTY) and 0.698 (NIFTY/SENSEX) — low enough for there to be
something to harvest.

That is the second prediction I have got wrong about these three sleeves. The
first was expecting them to be nearly the same bet; they are not, because
BANKNIFTY's monthly-only expiry forces its trades onto a different calendar.
Both errors point the same way: **the expiry structure is doing more to separate
these sleeves than the underlying indices do to join them.**

## The returns still do not clear the control

Pinned properly this time, after the 25-draw error in the previous run:

| shuffle draws | percentile |
|---|---|
| 25 | 76% |
| 60 | 83% |
| 100 | 84% |
| **300** | **83%** |

At 60 draws the reported value ranges **73 to 92**. The stable answer is the
**83rd percentile** — better than the independent version's 79th, and still not
95.

## Where this leaves the structure

Three changes have now been tested that are about *portfolio construction*
rather than signal, and all three helped:

| change | effect |
|---|---|
| split index vs stocks | drawdown 36.4% → 25.6% (correlation 0.222) |
| split across three indices | drawdown 29.4% → 16.5% |
| **daily rebalancing** | **drawdown 16.0% → 14.9%, return +2.3%** |

None of them required the signal to be good. They are all free, all structural,
and all reproducible — which is more than can be said for anything on the signal
side of this project.

The signal remains the problem. ₹43 lakh from ₹15 lakh is what shuffling
Kronos's predicted directions produces about one time in six.

```
python3 scripts/portfolio_rebalanced.py <data-dir>
```
