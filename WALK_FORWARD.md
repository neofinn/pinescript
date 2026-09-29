# 70/30 walk-forward validation

Every earlier test fixed a plan and asked whether it beat chance. That is not
what anyone actually does. A practitioner looks at recent history, picks
whatever did best, and trades it forward — and **that selection step is itself a
strategy that can be tested**. This tests it.

```
window   30 sessions
train    first 70% (21 sessions)  — pick the best plan here
test     last  30% (9 sessions)   — trade that pick, blind
step     9 sessions, so test windows tile without overlap
```

Ten candidates (six setups, four confluence rules), three markets, four folds
each. Underlying, 1:2 on the instrument, one spread each way.

## The selection rule broke before the markets did

Run with the obvious rule — *pick the highest training profit factor* — the
harness chose `conf3` in **every fold of two markets**. Not because triple
agreement works. Because it trades least, and profit factor on twenty trades
has far more spread than on four hundred, so the maximum over ten candidates
lands on whichever candidate is noisiest.

India's headline under that rule was **PF 1.873**. It was 18 trades across four
folds — 5, 2, 7 and 4. Requiring a minimum training sample:

| India, selection rule | test n | PF |
|---|---|---|
| max PF, no guard | 18 | **1.873** |
| max PF, ≥30 training trades | 393 | **0.687** |

Same data, same folds, same test windows. The entire result was the rule
sampling its own tail. **A minimum sample requirement is not a refinement of
walk-forward selection; it is the difference between selecting and sampling
noise.** Everything below uses the ≥30 guard.

## Results

| market | folds | SELECTED | RANDOM pick | best fixed plan |
|---|---|---|---|---|
| **US set A** (10 mega-caps) | 4 | **1.353** | 1.195 | 1.344 (conf3, n=74) |
| **US set B** (ranks 11–20) | 4 | **1.593** | 0.773 | 1.593 (conf3) |
| **India** (NIFTY/BANKNIFTY/SENSEX) | 4 | **0.687** | 0.906 | 0.898 |

*"RANDOM pick" draws uniformly from the same eligible candidates each fold —
the right null for "does choosing add anything".*

Per fold, what got picked and what happened next:

| | fold 1 | fold 2 | fold 3 | fold 4 |
|---|---|---|---|---|
| **set A** pick | conf2 | conf2_distinct | naked_poc_flow | conf3 |
| test PF | **1.825** | 0.783 | **1.717** | 0.318 |
| **set B** pick | conf3 | conf3 | conf3 | conf3 |
| test PF | **1.188** | **2.023** | **1.508** | **2.160** |
| **India** pick | naked_poc_flow | absorption | dva_edge_fade | lvn_traverse |
| test PF | 0.661 | 0.708 | 0.752 | 0.593 |

India selected a *different* plan every fold and **every one lost**.

## Against a matched control

| market | selected n | PF | control 95th | percentile |
|---|---|---|---|---|
| **US set A** | 521 | 1.353 | 1.232 | **99.0** |
| US set B | 93 | 1.593 | **2.158** | 85.0 |
| India | 393 | 0.687 | 1.120 | 11.5 |

Set A clears at the 99th percentile — the strongest single result in this
study. Set B's 1.593 looks better and is not: at 93 trades the control reaches
2.158, so it lands at 85.

## The number that decides it

Selection can only work if a plan's training rank predicts its test rank.
Across all twelve folds:

| | |
|---|---|
| mean Spearman ρ (train → test) | **+0.107** |
| standard deviation | 0.453 |
| 95% confidence interval | **[−0.149, +0.364]** |
| folds with ρ > 0 | 7 of 12 |

Per fold: `+0.16, −0.48, +0.85, +0.16 | +0.30, +0.21, −0.01, +0.83 | +0.39,
−0.03, −0.66, −0.43`.

**The interval spans zero comfortably.** The mechanism a walk-forward requires
is not detectably present. One fold reaches +0.85 and another −0.66, which is
what a coin looks like when you plot it.

## Reading these together

Set A passes at the 99th percentile while the thing that would explain a pass
is absent. Both can be true, and the resolution is the one this study keeps
arriving at: **set A is the favourable basket.** Random selection among the
same candidates scores 1.195 there — above breakeven before any choosing
happens. On set B random scores 0.773 and on India 0.906. Selection is being
credited for a basket that was already paying.

So the walk-forward does not overturn anything. It adds two things:

1. **A methodological result that generalises past this project.** Naive
   walk-forward selection on profit factor is biased toward the smallest
   candidate, and the bias is large enough to invert a conclusion — 1.873 to
   0.687 on identical data. Any walk-forward without a minimum-sample guard is
   reporting that bias.

2. **A negative result on selection itself.** Choosing what to trade from
   recent performance beat a random choice on one market of three, failed on
   the other two, and the rank correlation that would justify it is
   indistinguishable from zero across twelve folds.

One caveat on the tables: "ORACLE" in the script output picks the best plan per
fold *with hindsight*, but pooling its trades is not a strict ceiling on pooled
profit factor — set B's selected stream exceeds it because the two pool
different trade counts. It is a reference point, not an upper bound, and the
script says so.

```
python3 scripts/walkforward.py <setA-dir> <setB-dir> <india-dir>
```
