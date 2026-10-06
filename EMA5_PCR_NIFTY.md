# 5 EMA + PCR on NIFTY and BANKNIFTY

The 5 EMA setup as it is normally taught: a candle that forms entirely **above**
the 5 EMA (its low never touches) is over-extended — rest a sell-stop at that
candle's low with the stop-loss at its high. Mirror for longs. Then filter it
with the Put-Call Ratio.

**The strategy does not work: the 5 EMA alone is negative in 35 of 36 cells, and
no PCR filter rescues it. But the PCR half produced a finding worth more than
the strategy — the PCR everyone quotes has no predictive content at all, and
the one nobody quotes does.**

---

## PCR here is real, not a proxy

No free source publishes a PCR history, so it was rebuilt from NSE's own F&O
settlement files: **548 trading days** of bhavcopy (2024-07-08 → 2026-10-01),
every option contract's open interest and volume, giving

- **PCR-OI** = Σ put open interest / Σ call open interest
- **PCR-volume** = Σ put volume / Σ call volume

each for the near expiry and for all expiries. Median PCR-OI came out at 1.07
for NIFTY and 0.77 for BANKNIFTY — the right neighbourhood, which is the first
check that the reconstruction is sound.

**PCR is published after the close, so day *d*'s PCR gates day *d+1* onward.**
Using the same day's PCR intraday would be look-ahead, and it is the easiest
way to manufacture a result here.

Price data: NIFTY and BANKNIFTY, 5,043 hourly bars (3 years) and ~4,680 daily
bars (19 years). Costs 2 bps.

## 1. The 5 EMA alone

Mean average-R across six series (both indices × h1/h4/daily):

| side | RR 1.5 | RR 2.0 | RR 3.0 | cells positive |
|---|---|---|---|---|
| **short** | −0.334 | −0.297 | −0.272 | **0 / 18** |
| **long** | −0.166 | −0.167 | −0.141 | **1 / 18** |

**35 of 36 cells negative.** The single exception is BANKNIFTY daily long at
RR 3.0, at +0.015 — zero to three decimal places.

Profit factors run 0.48–0.95. The short side is consistently the worse of the
two, which is what happens when a mean-reversion short is applied to indices
that rose throughout.

## 2. PCR-OI predicts nothing

Permutation test, 10,000 shuffles of the pairing between PCR and the forward
5-day return:

| index | field | Q5−Q1 bps | percentile | Spearman |
|---|---|---|---|---|
| NIFTY | **pcr_oi_all** | +1.9 | 52.6 | +0.026 |
| NIFTY | **pcr_oi_near** | +18.0 | 75.9 | +0.028 |
| BANKNIFTY | **pcr_oi_all** | −1.5 | 48.4 | −0.034 |
| BANKNIFTY | **pcr_oi_near** | −7.9 | 38.7 | −0.024 |

Four measures, two indices, 544 days each. Every one sits in the middle of its
own permutation distribution. Spearman correlations of ±0.03 are noise.

**This is the number every Indian option-chain screen displays and every PCR
rule is built on.** Against 548 days of NSE's own settlement data it has no
relationship with what the index does next.

## 3. PCR-volume does carry something

| index | field | Q5−Q1 bps | percentile | Spearman |
|---|---|---|---|---|
| NIFTY | **pcr_v_near** | **−53.5** | **1.8** | −0.100 |
| NIFTY | pcr_v_all | −36.9 | 7.1 | −0.092 |
| BANKNIFTY | pcr_v_near | −37.8 | 10.4 | −0.066 |
| BANKNIFTY | pcr_v_all | −34.9 | 12.1 | −0.058 |

All four negative, in both indices, with the same sign and similar size — and
the sign is the **opposite of the conventional reading**. High put *volume*
precedes **lower** forward returns. It is a momentum signal, not a contrarian
one: heavy put buying is followed by the market falling, not bouncing.

Honest accounting: only one of eight measures clears 95% on its own, and eight
were tested. What argues for it is the consistency — four volume measures all
negative, four OI measures all ~zero — not any single percentile.

## 4. The ablation: is it just "the market already fell"?

Put volume spikes during selloffs, so the obvious explanation is that PCR-volume
is a slow proxy for the trailing return.

| index | predictor | Q5−Q1 bps | Spearman |
|---|---|---|---|
| NIFTY | PCR-volume | −36.9 | −0.092 |
| NIFTY | trailing 5-day return | −33.9 | −0.046 |
| **NIFTY** | **PCR within trailing-return quintiles** | **−50.5** | |
| BANKNIFTY | PCR-volume | −34.9 | −0.058 |
| BANKNIFTY | trailing 5-day return | **−6.6** | −0.011 |
| **BANKNIFTY** | **PCR within trailing-return quintiles** | **−27.3** | |

On NIFTY the raw effect is nearly the same size as the trailing return's, so
much of it *is* "the market already fell." But holding the trailing return
fixed and sorting by PCR **within** each quintile still gives −50.5 bps. On
BANKNIFTY the trailing return explains almost nothing (−6.6), so there PCR-volume
is close to independent.

**The signal survives the ablation on both indices** — which is more than the
SPX/DJI ratio managed in this repo, where the single-series control beat the
combination 8 times out of 8.

## 5. Putting them together

PCR-volume used directionally (heavy put volume → favour shorts):

| sym | tf | filter | side | n | avg R | PF |
|---|---|---|---|---|---|---|
| NIFTY | h1 | none | short | 331 | −0.232 | 0.71 |
| NIFTY | h1 | **pcr_v_near > 0.99** | short | 99 | **−0.113** | 0.85 |
| NIFTY | h1 | none | long | 323 | −0.139 | 0.81 |
| BANKNIFTY | h1 | none | long | 304 | −0.274 | 0.65 |
| BANKNIFTY | h1 | **pcr_v_all < 0.88** | long | 104 | **−0.126** | 0.83 |
| NIFTY | 1d | pcr_v_all > 0.98 | short | 16 | +0.471 | 1.92 |

**The filter improved 10 of 12 cells, by +0.070 average-R.** It also left
**1 of 12 positive**, and that one has 16 trades.

Halving a loss is not an edge. The filter is doing real work — the improvement
is consistent and in the direction §3 predicted — but it is improving something
that starts at −0.23 and needs to reach +0.00.

## Verdict

Do not trade this. The 5 EMA setup is negative in 35 of 36 configurations across
both indices and three timeframes, and the best PCR filter available moves it
from roughly −0.23 R to roughly −0.12 R.

Two things are worth keeping:

1. **PCR-OI, the number on every option-chain screen, had no measurable
   relationship with forward returns over 548 days of NSE settlement data.** If
   a rule you use is built on it, that is the thing to check first.
2. **PCR-volume does, and it runs the other way from the textbook.** Heavy put
   volume preceded weakness, not strength. It survives controlling for the
   trailing return on both indices. It is small — tens of basis points over five
   days — but it is consistent in sign across four measures and two indices.

A filter that halves a loss would be worth having on a strategy that made money.
The 5 EMA is not that strategy.

## Files

- `scripts/ema5_pcr.py` — the 5 EMA setup, the PCR loader and the gate.
- `scripts/pcr_fetch.py` — rebuilds PCR from NSE bhavcopy; streams and discards
  each zip, so 548 days costs a few hundred KB rather than half a gigabyte.
- `ema5_pcr.pine` — the setup on a chart, with the PCR gate as an external input.
