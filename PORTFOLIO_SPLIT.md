# ₹10 lakh, split 50/50 — index options and stock options

Two accounts of ₹5,00,000, each compounding independently, each risking 5% of
**its own** equity per trade. Both restricted to 2026 so they cover the same
calendar. Direction from Kronos, stops from supply/demand, ATM options.

## Result

| sleeve | n | start | final | × | maxDD |
|---|---|---|---|---|---|
| INDEX — NIFTY options | 50 | ₹5,00,000 | ₹19,20,484 | 3.84 | 24.6% |
| STOCKS — top-20 F&O | 139 | ₹5,00,000 | ₹4,43,409 | **0.89** | 36.4% |
| **COMBINED** | 189 | ₹10,00,000 | **₹23,63,893** | **2.36** | **25.6%** |

## The split did real work, and it is the first thing in this project that did

| | |
|---|---|
| monthly return correlation between sleeves | **0.222** over 9 shared months |
| worst single sleeve drawdown | 36.4% |
| **combined drawdown** | **25.6%** |

A correlation of 0.22 is genuinely low, and the drawdown fell by almost eleven
points below the worse sleeve rather than landing between the two. That is what
diversification is supposed to do and it is measurable here.

It is worth being precise about what this is: **a risk result, not a return
result.** Splitting did not find an edge. It made the same expectancy less
painful to hold, which is a real and useful thing and is not the same claim.

Note also what it survived: both sleeves take direction from the *same model*,
so a systematic tilt in Kronos would have correlated them regardless of
instrument. At 0.222 there is no such tilt doing the work — the sleeves are
genuinely trading different things.

## The combined return still does not clear its control

| | |
|---|---|
| direction-shuffled portfolio, median | ₹16,02,668 |
| direction-shuffled portfolio, 95th | ₹43,16,694 |
| **the real portfolio** | ₹23,63,893 — **76th percentile** |

Shuffling only what Kronos predicted, holding every entry time, stop and gate
fixed, produces ₹16 lakh on the median draw. The real portfolio's ₹23.6 lakh is
at the 76th percentile of that. It does not clear 95.

## One inconsistency to state plainly

The index sleeve runs the **best** NIFTY configuration found earlier
(median-magnitude threshold, RR 1.5, ungated). The stock sleeve runs the same
parameter shape — but on stocks the grid showed that cell at **0.98×**, which is
one of the weaker ones, not the best (4.29× at RR 2.0 with no threshold).

So the combined figure is carried by the index sleeve, and the stock sleeve is
being run at a setting its own grid says is poor. Picking each sleeve's best
would raise the total and would also be exactly the selection this project has
spent twelve documents showing is worthless. The numbers above are the ones
where only one sleeve was optimised, and that asymmetry is the reason the
stock sleeve lost money.

## What the stock sleeve's own grid said

The threshold that was the one apparent Kronos contribution on NIFTY —
percentile 65 → 92, PF 1.60 → 2.18 — **reverses on stocks**. Every
median-threshold cell lands at 0.84–1.39× against 2.50–4.29× ungated.

That is the same failure mode as every other candidate here: the effect exists
on the instrument it was found on and not on the next one. And the best stock
cell reached the **90th percentile** where the null expectation for twelve cells
is **92.3rd** — below what pure search predicts.

## Verdict

**Keep the split.** Correlation 0.222 and a drawdown cut from 36.4% to 25.6% is
a real benefit, it cost nothing, and it is the only structural change in this
entire project that improved something measurably.

**Do not trade the signal.** The combined portfolio sits at the 76th percentile
of its own direction-shuffled control, the stock sleeve loses money, and the one
Kronos behaviour that looked useful on the index did not survive the move to
single names.

```
python3 scripts/fno_kronos_zone.py <data-dir>     # stock sleeve grid
python3 scripts/portfolio_split.py <data-dir>     # the 50/50 portfolio
```
