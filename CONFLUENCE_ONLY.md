# Confluence only

Trade a bar only where the setups agree. Four rules, fixed before the run, and
the reason there are four is an overlap measurement rather than a preference.

## The overlap had to be measured first

Pooled across SPY, QQQ and ES over the full window, same bar and same side:

| | fires | co-fires with `dva_edge_fade` |
|---|---|---|
| absorption_at_edge | 482 | **365 (76%)** |
| cvd_divergence | 1,056 | 186 |
| lvn_delta_traverse | 589 | 71 |
| naked_poc_flow | 1,005 | 13 |
| delta_breakout | 1,188 | 8 |

`absorption_at_edge` **is** `dva_edge_fade` plus an imbalance condition, so
counting them as two agreeing setups is a signal agreeing with itself. Every
other pair is genuinely independent. So one of the four variants excludes
same-family agreement, and it turns out to matter: 887 confluence bars become
595 once the redundancy is removed.

| rule | signal bars (full window, pooled) |
|---|---|
| exactly 1 setup firing | 3,667 |
| conf2 — ≥2, all firing setups agree | 887 |
| conf2_majority — ≥2 on one side, disagreement tolerated | 969 |
| conf2_distinct — ≥2 from different families | 595 |
| conf3 — ≥3, unanimous | **50** |

Confluence does not trim the edges. It discards roughly **four fifths** of the
opportunities, and it has to pay for that out of selectivity.

## August 2026, 0DTE, SPY + QQQ + ES

| plan | n | PF | net $ | final $ | maxDD | ctl95 | pct |
|---|---|---|---|---|---|---|---|
| naked_poc_flow *(single)* | 75 | 1.372 | **+13,811** | 113,811 | 10.8% | 2.54 | 59.5 |
| conf2_distinct | 113 | 0.978 | −1,499 | 98,501 | **17.2%** | 2.06 | 34.0 |
| conf2_majority | 203 | 0.973 | −2,744 | 97,256 | 18.2% | 1.51 | 52.3 |
| conf2 | 196 | 0.956 | −4,336 | 95,664 | 19.6% | 1.58 | 50.0 |
| conf3 | 11 | 0.510 | −3,403 | 96,597 | 5.4% | 6.00 | 27.0 |
| dva_edge_fade *(single)* | 298 | 0.892 | −18,612 | 81,388 | 37.4% | 1.28 | 60.0 |
| conf2 *(tight stop)* | 240 | 0.717 | −32,416 | 67,584 | 36.4% | 1.20 | 40.0 |

Confluence **rescued the bad month**: `dva_edge_fade` alone lost $18,612 with a
37.4% drawdown, and requiring a second family cut that to −$1,499 with a 17.2%
drawdown. That is a real effect and it is what people buy confluence for.

It did not find an edge. Every variant sits at or below the coin flip against
its own control — 50.0, 52.3, **34.0**. And it still does not beat the best
single setup, which made money.

`conf3` gets 11 trades in a month. Its control reaches PF 6.00. Nothing can be
concluded from it and it is listed only so the row is not quietly dropped.

## Jul–Sep, the same plans on a sample worth reading

| plan | n | PF | net $ | maxDD | return/DD | ctl95 | pct |
|---|---|---|---|---|---|---|---|
| **dva_edge_fade** *(single)* | 763 | 1.187 | **+73,610** | 28.1% | **2.62** | 1.24 | **92.5** |
| naked_poc_flow *(single)* | 251 | 1.456 | +55,743 | 23.4% | 2.38 | 2.42 | 50.5 |
| conf2_distinct | 327 | 1.226 | +42,052 | **17.3%** | 2.43 | 2.01 | 45.5 |
| conf3 | 45 | 1.875 | +20,177 | 8.6% | 2.35 | 3.19 | 79.5 |
| conf2 | 528 | 1.063 | +16,571 | 21.7% | 0.76 | 1.52 | 46.5 |
| conf2_majority | 566 | 1.050 | +13,716 | 22.3% | 0.61 | 1.47 | 53.5 |

## The clearest demonstration of sample cost this project has produced

`dva_edge_fade` and `conf2_distinct` have **almost the same risk-adjusted
return** — 2.62 against 2.43. One sits at the **92.5th** percentile of its
control and the other at the **45.5th**.

Nothing about the quality of the trades explains that. The control at 763
trades reaches PF 1.24; at 327 trades it reaches 2.01. Halving the sample
raises the bar you have to clear by more than confluence raises your profit
factor. That is the whole mechanism, in one pair of rows.

Confluence made the equity curve smoother — 17.3% drawdown against 28.1%, and
a near-flat August instead of a −$18.6k one — and simultaneously destroyed the
only cell in this study with respectable evidence behind it.

## Two things the run settled on the side

**The stop rule was not a lucky choice.** "Widest stop among agreeing setups"
was pre-registered on the reasoning that if two structures disagree about where
an idea is wrong, it is wrong at the further one. The tightest-stop variant is
worse in **both** windows (−$32,416 vs −$4,336 in August; −$15,771 vs +$16,571
over Jul–Sep), so the choice is supported rather than fitted.

**Excluding the redundant family helped.** `conf2_distinct` beats plain
`conf2` on net, on drawdown and on return/DD in both windows, on fewer trades.
Measuring the overlap before building the rule was worth doing.

## Verdict

Confluence is a risk-reduction tool here, not an edge-finding one. It halves
drawdown and it halves your evidence, and on this data the second effect is
larger. Nothing in the table beats a matched control.

If the goal is a smoother curve on a strategy you already believe in,
`conf2_distinct` does that. If the goal is to find out whether there is
anything to believe in, confluence is the wrong instrument — it moves you away
from the sample sizes that can answer the question, which is the same result
this project has now reached five times from five different directions.

```
python3 scripts/vp_conf_run.py <bars-dir> <vol-dir>
```
