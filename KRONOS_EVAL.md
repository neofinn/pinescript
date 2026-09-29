# Kronos, evaluated

[Kronos](https://github.com/shiyu-coder/Kronos) is the first open-source
foundation model for financial candlesticks — a decoder-only transformer over
tokenised OHLCV, pre-trained on 12 billion K-lines from 45 exchanges
(AAAI 2026, [arXiv 2508.02739](https://arxiv.org/abs/2508.02739)).

## Why this test is worth more than the others in this repo

Every signal in this project was written by someone who had already seen the
data. Random controls, IS/OOS splits and universe swaps exist to fight that
bias and never fully win.

**Kronos's weights were published 2025-06-30 and last modified 2025-09-09. The
bars here are July–September 2026.** The parameters were frozen a year before
this data existed. No amount of looking could have fitted them to it.

That makes this the only genuinely out-of-sample test in the repo — and it
means a positive result would have been worth far more than any of the
in-house signals.

## Protocol, fixed before running

Forecast skill **first**, trading only if skill survives. A backtest on a
forecast conflates two questions — is the forecast informative, and is the
trading rule good — and a negative result cannot tell you which failed.

```
model        Kronos-small (24.7M params) + Kronos-Tokenizer-base (4.0M)
context      512 bars of 5m data, strictly bars[i-512 : i]
horizon      12 bars (1 hour), scored at every intermediate step too
sampling     5 probabilistic paths, averaged
points       every 36 bars → 114 forecasts per instrument
universe     SPY, QQQ (set A) + GOOGL, IWM (set B) = 456 forecasts
```

Causality: the forecast at bar `i` sees only bars before `i`; a trade on it
enters at bar `i`'s open.

## Step 1 — forecast skill

| instrument | n | hit% | majority baseline | IC | IC 95% CI |
|---|---|---|---|---|---|
| SPY | 114 | 56.1 | 51.8 | +0.064 | [−0.126, +0.248] |
| QQQ | 114 | 52.6 | 52.6 | −0.019 | [−0.225, +0.178] |
| GOOGL | 114 | 53.5 | 52.6 | −0.040 | [−0.219, +0.148] |
| IWM | 114 | 52.6 | 50.9 | −0.013 | [−0.211, +0.177] |
| **POOLED** | **456** | **53.7** | **50.7** | **−0.013** | **[−0.108, +0.089]** |

Directional hit 53.7%, 95% CI **[49.1%, 58.3%]** — the interval **includes**
the 50.7% majority-class baseline. Three of the four per-instrument ICs are
negative.

The baseline matters: scoring against 50% rather than the majority class would
have credited a model that merely learned "up" on a drifting sample.

### Every horizon, same forecasts

| horizon | hit% | majority | IC | IC 95% CI |
|---|---|---|---|---|
| 5m | 50.7 | 52.2 | +0.037 | [−0.057, +0.132] |
| 10m | 47.8 | 51.8 | −0.055 | [−0.156, +0.041] |
| 15m | 45.6 | 53.9 | −0.096 | [−0.192, +0.004] |
| 30m | 54.8 | 52.2 | −0.004 | [−0.106, +0.099] |
| 45m | 54.2 | 50.2 | +0.019 | [−0.078, +0.122] |
| 60m | 53.7 | 50.7 | −0.013 | [−0.109, +0.089] |

**Every interval covers zero.** There is no horizon where the forecast carries
measurable directional information.

### The control that settles it

Shuffling the forecasts against the outcomes — destroying any real
correspondence — gives **IC +0.012**. The real pairing gives **−0.013**.

*The shuffled forecasts score as well as the real ones.*

### Two more diagnostics

- **Magnitude is heavily shrunk**: predicted move sd 0.207% against a realised
  0.439%. Averaging five sampled paths pulls the point forecast toward the
  mean. This affects magnitude, not direction, so it does not explain the IC.
- **The predicted range is unusable as a stop**: the forecast's own high/low
  band contains the realised range on **2.6–8.8%** of forecasts. Any rule
  taking its stop from the model's predicted low would be stopped out almost
  always.
- **Not even momentum**: correlation between predicted move and the prior
  bar's move is +0.040, so it is not silently doing continuation either.

## Step 2 — not run, on purpose

The pre-registered rule was: trade only if step 1 survives. It did not. With
an IC interval covering zero at every horizon and a shuffle control scoring
the same, no threshold, position size or confluence rule can recover signal
that is not there. Running the backtest anyway would have produced a number,
and this project has spent enough effort showing what such numbers are worth.

## What this does and does not say

**It does not say Kronos is a bad model.** Four things bound the claim, and
they should be read before quoting the result:

1. **This is Kronos-small**, 24.7M parameters. `base` is 102M and `large`
   (499M) is unreleased. A run of Kronos-base on SPY and QQQ is in progress
   and will be appended.
2. **5-minute US equity intraday over ≤1 hour is the hardest corner** of the
   space — the most arbitraged, the least predictable — and is plausibly out
   of distribution against a training mix spanning 45 exchanges.
3. **The detection floor is ~±0.10 IC.** At 456 forecasts a true IC of 0.05
   would not be reliably detected. The honest statement is *no IC larger than
   about 0.10 is present*, not *the IC is zero*. A real edge of 0.03–0.05
   would be economically interesting and invisible here; separating it would
   need several thousand forecasts.
4. **Forecast skill is not the model's only claim.** The paper also targets
   volatility prediction and synthetic data generation, neither tested here.

What it does say is narrow and solid: **on 5-minute US equity bars, at
horizons of five minutes to an hour, Kronos-small's directional forecasts were
indistinguishable from shuffled ones across 456 genuinely out-of-sample
predictions.**

```
python3 scripts/kronos_forecast.py <bars.json> <out-dir> <tag> [model]
python3 scripts/kronos_eval.py <forecast-dir>
```
