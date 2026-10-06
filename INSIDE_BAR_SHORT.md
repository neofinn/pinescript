# Inside-bar breakdown short at a swing high

The pattern as given:

> Market swing high on a 30-minute candle. If a small candle is made inside the
> ATH candle, once its low is broken, take a short position.

**Result: it loses money in 283 of the 288 parameter cells tested, across seven
markets. The inside-bar requirement makes it worse, not better — removing that
one rule improves the average trade in five of six markets. The mechanism is
measured below, and it is the stop.**

---

## What had to be pinned down first

Four terms in the description are underdetermined. Each became a swept
parameter rather than a silent choice, because each one moves the answer:

| term | reading | swept |
|---|---|---|
| "the high" | a literal all-time high fires a handful of times a decade | new high over a **lookback** of 20 or 50 bars |
| "small" | inside is necessary, not sufficient | inside range ≤ **1.0** or **0.6** × the reference range |
| "once broken" | on the tick, or on a close below? | **break** and **close**, both |
| staleness | a trigger cannot stay live forever | valid for **3** bars |

Plus the trade management: reward:risk 1.5 / 2.0 / 3.0, stop above the inside
bar or above the reference bar, 16-bar time stop.

## Fill assumptions, all pessimistic on purpose

- A stop-sell that **gaps fills at the bar open**, not at the trigger price.
  This project measured 40–51% of option trades gapping through their stop; the
  same effect exists here and is modelled rather than waved at.
- A bar that touches **both** the stop and the target is scored a **loss**.
- The **entry bar's own high counts against the stop**. It may have printed
  before the break, so this is stricter than reality.

The second of those is an assumption strong enough to manufacture the result on
its own, so it is audited below. It does not.

## Data

| market | bars | window |
|---|---|---|
| 40 US symbols, 30m (SPY QQQ IWM DIA, 8 sectors, 25 large caps, GLD SLV USO TLT EEM FXI EWZ) | 31,160 | 2026-07-07 → 09-29 |
| ES 30m (from 5m) | 2,267 | 2026-07-21 → 09-29 |
| ES h1 | 11,430 | 2024-09-29 → 2026-09-29 |
| NQ h1 | 11,432 | 2024-09-29 → 2026-09-29 |
| NIFTY h1 | 5,046 | 2023-10-20 → 2026-09-29 |
| BANKNIFTY h1 | 3,441 | 2024-09-30 → 2026-09-29 |
| SENSEX h1 | 3,442 | 2024-09-30 → 2026-09-29 |

Costs: 0.6 bps round turn on futures, 3.0 bps on US equities/ETFs, 2.0 bps on
the Indian indices.

## The control

Every cell is scored against 200 draws of a **price-matched random control**:
the real setups are moved to random bars and re-priced to where they land, so
the trade count, the stop-distance distribution and the firing rate are held
identical to the strategy's. Only the alignment between the setup and the price
action is destroyed. A shifted-but-not-repriced control was tried first and
rejected — it carries absolute prices from months away, so in a trending market
its triggers are unreachable and it under-fires, which flatters the strategy.

## Headline

| market | cells | positive total R | beat the 95th pct of own control | expected best under the null | observed best |
|---|---|---|---|---|---|
| 40 syms 30m | 48 | **0** | 0 | 98.0th | 92nd |
| ES 30m | 42 | 13 | 3 | 97.7th | 96th |
| ES h1 | 48 | 0 | 8 | 98.0th | 100th |
| NQ h1 | 48 | 0 | 11 | 98.0th | 98th |
| NIFTY h1 | 48 | 0 | 0 | 98.0th | 78th |
| BANKNIFTY h1 | 48 | 3 | 2 | 98.0th | 96th |
| SENSEX h1 | 48 | 1 | 16 | 98.0th | 100th |

Two things are going on and they must not be confused:

1. **Absolutely, it loses.** 283 of 288 cells end negative. Profit factors sit
   between 0.28 and 0.92 almost everywhere.
2. **Relative to a random short, it sometimes wins** — SENSEX 16/48, NQ 11/48.
   That is the pattern losing *less than random shorting does*, in markets that
   rose. It is not an edge you can trade; there is no instrument that pays you
   for losing more slowly.

And the sub-readings flip sign between markets, which is the signature of noise:

- **ES 30m**: close entry beat break entry in every cell.
- **40-symbol 30m universe**: exactly reversed — break entry median 66th
  percentile, close entry median 21st, over 12,864 trades.
- **NIFTY h1**: the reference-bar stop is catastrophic (0th–10th percentile).
  **SENSEX h1**: the reference-bar stop is the *good* one.

The ES 30m finding was written down before the universe ran, and the universe
reversed it. That is the test that matters.

## Ablation: does the inside bar do anything?

RR 2.0, stop at the inside bar, entry on the break, lookback 20. Average R per
trade, and the exact mirror of the pattern at a new **low** going **long**:

| variant | short | long |
|---|---|---|
| full pattern | **−0.353** | −0.269 |
| drop the inside-bar rule | −0.311 | −0.214 |
| drop the new-high rule | −0.376 | −0.355 |

(mean across the six markets)

- **The full pattern is the worst short variant.** Deleting the inside-bar
  requirement — shorting the break of the low of whatever bar follows a new high
  — is better in five of six markets. The inside bar is not merely inert; it
  selects trades that do slightly worse.
- **The long mirror loses too.** So this is not "shorts lose because the market
  went up." The structure is negative in both directions.
- The new-high rule does carry a little of the weight: dropping it is worse than
  keeping it. What the pattern has is the "at a high" part, and the inside
  candle is dead weight on top of it.

## Audit of my own pessimistic rule

Bars that touched both the stop and the target were scored as losses. Re-scored
as wins — the most optimistic possible reading — the same cells give:

| market | trades | both-touched | pessimistic avg R | optimistic avg R |
|---|---|---|---|---|
| 40 syms 30m | 452 | 2.4% | −0.211 | −0.138 |
| ES 30m | 40 | 0.0% | −0.315 | −0.315 |
| ES h1 | 218 | 3.7% | −0.248 | −0.138 |
| NQ h1 | 212 | 2.4% | −0.277 | −0.206 |
| NIFTY h1 | 107 | 8.4% | −0.490 | −0.238 |
| SENSEX h1 | 86 | 17.4% | −0.577 | −0.054 |

Every market stays negative under the assumption most favourable to the
strategy. The tie-break rule is not what is producing the result.

## Why it loses: the stop is the pattern

On the 40-symbol universe at the pattern's own settings, 452 trades:

- 68% stopped out, 22% hit the 2R target, 10% timed out
- of the 405 that **resolved**, **24.4% hit the target**
- a driftless random walk with a stop at *r* and a target at *2r* resolves in
  the target's favour **33.3%** of the time

So the pattern is not a coin flip that loses to costs. It resolves *worse than a
coin flip*. The reason is geometric: "a small candle" makes the risk distance
small by construction, the stop sits a few ticks away inside ordinary noise, and
entering on the break means selling the low of that small bar — the worst price
in it — with gap fills making the entry worse still.

Widening the stop confirms the mechanism, and also shows it cannot be fixed.
Stop as a multiple of the reference bar's range, pooled across five markets,
average R per trade at RR 2.0:

| stop × ref range | 0.5 (≈ the pattern) | 1.0 | 1.5 | 2.0 | 3.0 | 5.0 |
|---|---|---|---|---|---|---|
| pooled avg R | **−0.383** | −0.133 | −0.083 | −0.054 | −0.050 | −0.028 |

Monotone improvement, never crossing zero. And at the wide end the improvement
is an illusion: at a 5× stop, **86% of trades time out** rather than resolving.
Widening the stop does not find an edge, it switches the trade off — the number
approaches zero-minus-costs because it is approaching *not trading*.

## What is in the repo

- `inside_bar_breakdown.pine` — the pattern as a TradingView strategy, every
  reading exposed as an input, non-repainting (both pattern bars are closed
  before the trigger is published).
- `scripts/inside_bar_short.py` — setups, the shared executor, the control
  generators. `execute` is shared by the strategy and every control, so a
  control differs in exactly one thing: which bars it fires on.
- `scripts/inside_bar_run.py` — the grid and the percentile machinery.

## The honest summary

The pattern is real and it is visible on charts. What it is not is profitable:
it loses in essentially every configuration, in both directions, on US futures,
US equities and ETFs, and Indian indices; the inside-bar condition that defines
it actively subtracts from the result; and the reason is that it places its stop
inside the noise it is trying to trade. Nothing here beats its own matched
control once the number of parameter combinations is counted.
