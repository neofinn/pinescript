# The IVB reel's components, tested one at a time

GC=F 15m, 2026-07-17 → 2026-09-17, 3,843 bars. Identical machinery for every
component — next-bar-open entry, 0.75 × ATR stop, 1:2 target, 0.45 points cost —
so only the signal differs. "vs random" is the percentile against side-matched
random entries with the same trade count.

The reel stacks five confluences and asks "MORE CONFLUENCES = ?". Stacked, they
cannot be evaluated: this project already measured one added filter taking a
strategy from 77 trades to 33, where random noise reaches PF 2.07 one time in a
hundred. So each is built and judged alone first.

## Alone

| component | trades | win% | PF | net | median trade | random median | random 95th | **vs random** |
|---|---|---|---|---|---|---|---|---|
| FVG (≥0.25 ATR) | **374** | 33.4 | 0.91 | −158.4 | −5.80 | 0.88 | 1.07 | 61st |
| FVG (any size) | **589** | 33.6 | 0.92 | −239.1 | −5.82 | 0.89 | 1.03 | 62nd |
| Order block (1.0 ATR) | 221 | 34.4 | 0.99 | −5.8 | −5.75 | 0.91 | 1.13 | 74th |
| Order block (1.5 ATR) | 68 | 35.3 | 0.99 | −1.9 | −6.29 | 0.87 | 1.32 | 72nd |
| Liquidity sweep | **334** | 31.7 | 0.82 | −285.3 | −5.86 | 0.89 | 1.08 | 28th |

**Not one of them beats random.** The best is order block at the 74th
percentile, which is nothing — you would want 95th or better.

These are the strongest results on this page, because the samples are large
enough to settle the question. **589 trades at PF 0.92 and the 62nd percentile
is a well-powered negative**: fair value gaps carry no directional information on
gold 15m. The same for liquidity sweeps at 334 trades — and at the 28th
percentile they are, if anything, slightly *worse* than random.

The median trade is about −5.8 for every single component.

## Stacked with session filter (07–21 UTC) and HTF bias alignment

| component | trades | kept | win% | PF | net |
|---|---|---|---|---|---|
| FVG (≥0.25 ATR) | 160 | 43% | 34.4 | 0.96 | −29.1 |
| FVG (any size) | 253 | 43% | 34.0 | 0.89 | −135.5 |
| **Order block (1.0 ATR)** | **82** | 37% | 42.7 | **1.46** | **+156.5** |
| **Order block (1.5 ATR)** | **33** | 49% | 51.5 | **1.86** | **+111.1** |
| Liquidity sweep | 92 | 28% | 29.3 | 0.72 | −128.6 |

Adding confluences did **not** lift everything. FVG and liquidity sweep stay
negative; the stack only moved order block.

## The one that moved, taken apart

| | OB 1.0 + session + bias | OB 1.5 + session + bias |
|---|---|---|
| trades | 82 | 33 |
| win% | 42.7 | **51.5** |
| PF | 1.46 | 1.86 |
| **median trade** | −5.56 | **+9.36** |
| binomial vs 33.3% | **p = 0.049** | **p = 0.023** |
| random median / 95th / 99th | 0.92 / 1.36 / 1.61 | 0.87 / 1.63 / 2.21 |
| **percentile of random** | **98th** | **98th** |
| top 3 trades | 50% of profit | 52% of profit |
| halves | 1.30 (37) / 1.59 (45) | 2.54 (15) / 1.50 (18) |

Both sit at the **98th percentile** of their own matched control, both halves are
positive, and the 1.5-ATR variant is the only configuration found anywhere in
this project whose **median trade is positive** (+9.36). That is the strongest
result this project has produced.

It is still not established:

- **~10 cells were tested here**, so one hit at p≈0.05 is roughly what chance
  delivers. The two order-block rows are not independent evidence — the 1.5 ATR
  set is largely a subset of the 1.0 ATR set, so this is one finding, not two.
- **Half the profit is three trades** in both variants.
- 82 and 33 trades, one instrument, two months, one rising regime.

## What this says about the model in the reel

Of the five advertised components, on this instrument and window:

- **fair value gap** — well-powered negative, twice (374 and 589 trades)
- **liquidity sweep** — well-powered negative (334 trades)
- **order block** — neutral alone (74th percentile), reaches the 98th when
  combined with session and bias, on a sample too small to confirm
- **session filter** and **HTF bias** — not signals on their own; they act only
  as filters, and they helped exactly one of the three base signals

"More confluences" did not improve things generally. It improved one component
and left two well-powered negatives untouched, while cutting every sample by
half to three-quarters. The cost of a confluence is paid in sample size whether
or not it buys anything.

## Worth doing next

The order-block + session + bias combination is the first thing in this project
that has cleared its own control with both halves positive. That earns a real
test, not adoption:

1. A **year** of 15m data rather than two months — Yahoo caps 15m at ~60 days,
   so this needs the broker feed.
2. **A second and third instrument.** If it only ever appears on gold it is a
   fitted cell.
3. **A falling regime**, since HTF-bias alignment in a rising market cannot be
   separated from long bias here.

Caveat on definitions: "order block" and "impulsive" have no standard
definition. `scripts/smc.py` uses the last opposing candle before a bar whose
body exceeds N × ATR, and takes the stricter reading where usage is ambiguous.
A looser definition makes the pattern appear everywhere, and a different one may
not reproduce these numbers at all.
