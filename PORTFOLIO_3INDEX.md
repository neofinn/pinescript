# ₹15 lakh across NIFTY, BANKNIFTY and SENSEX

Three ₹5,00,000 sleeves, each compounding independently at 5% of its own equity.
Kronos for direction, supply/demand for the stop, 2026 hourly.

## A correction, first

I initially reported this portfolio at the **96th percentile** of its control
and called it the first result in the project to clear 95. **That was wrong.**
The stable figure is **79th**, and the error was mine, not the market's.

The percentile was computed from **25 shuffled draws**. Re-running the identical
cell with a different control seed gave 70. Running it properly:

| shuffle draws | shuffled median | percentile |
|---|---|---|
| 25 | ₹29,77,052 | 72% |
| 50 | ₹28,55,115 | 78% |
| 100 | ₹28,51,667 | 79% |
| 200 | ₹27,52,858 | 79% |
| **300** | **₹27,43,395** | **79%** |

And the size of the trap, measured directly: bootstrapping 25-draw sub-samples
from the 300-draw distribution, **the percentile you would report ranges from 64
to 92** across 95% of seeds. Twenty-five draws cannot place a result near a 95th
percentile boundary. My 96 was a tail draw from that noise.

This affects every percentile in this project computed from small draw counts —
15 in the VWAP/zone run, 25–40 elsewhere. It does not change their verdicts,
because those landed at the 0th, 20th, 33rd and 60th percentiles, far from any
boundary. It does mean the two near-misses — 92nd for Kronos+zone on NIFTY, 90th
for the stock sleeve — carry roughly ±10 points and were never as close to
significance as they looked.

## The result

| sleeve | expiry | lot | n | final | × | maxDD |
|---|---|---|---|---|---|---|
| NIFTY | weekly | 75 | 50 | ₹19,20,484 | 3.84 | 24.6% |
| BANKNIFTY | **monthly** | 35 | 49 | ₹17,81,117 | 3.56 | 29.4% |
| SENSEX | weekly | 20 | 22 | ₹5,09,958 | 1.02 | 17.1% |
| **COMBINED** | | | 121 | **₹42,11,559** | **2.81** | **16.5%** |

At the 79th percentile of its direction-shuffled control. Across eleven
configurations, **0 of 11 clear the 95th**, and the best reads 70 where the null
expectation for eleven draws is 91.7. The portfolio is worse than pure search
would produce.

## What is real here: the diversification

This part is arithmetic on the equity curves, not a percentile, so the control
noise above does not touch it.

| pair | monthly return correlation |
|---|---|
| NIFTY vs BANKNIFTY | **+0.395** |
| NIFTY vs SENSEX | +0.698 |
| **BANKNIFTY vs SENSEX** | **+0.035** |

| | |
|---|---|
| worst single sleeve drawdown | 29.4% |
| **combined drawdown** | **16.5%** |

**I expected these to be nearly the same bet and they are not.** SENSEX and
NIFTY hold heavily overlapping large caps and BANKNIFTY's constituents sit
inside NIFTY at about a third of its weight, so I predicted correlations near
0.9. BANKNIFTY against SENSEX came in at **0.035**.

The reason is that correlated *underlyings* do not make correlated *strategies*
when the trades happen at different times. BANKNIFTY has no weekly series, so
its sleeve holds four-week options while NIFTY and SENSEX trade weeklies; the
signals fire on different bars and the positions are open over different
windows. The expiry structure decorrelates them even though the indices do not.

That is worth keeping: **a 13-point drawdown reduction for free**, on top of the
11-point reduction the earlier stock/index split produced. Diversification is
the only thing in this entire project that has improved anything measurably, and
it has now done so twice.

## Verdict

**The split is real and worth keeping.** Three sleeves cut drawdown from 29.4%
to 16.5%, and the mechanism — different expiry calendars forcing different trade
timing — is structural rather than fitted.

**The returns are not.** 79th percentile on the reported cell, 0 of 11 clearing
95, best of eleven at 70 against a null expectation of 91.7. The ₹42 lakh is
what shuffling Kronos's directions produces about a fifth of the time.

```
python3 scripts/portfolio_3index.py <data-dir>
```
