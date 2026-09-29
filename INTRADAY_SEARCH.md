# Pre-registered search over intraday signals

`scripts/intraday_lab.py` · `scripts/intraday_signals.py`

**12 instruments** (SPY, QQQ, IWM, DIA, XLF, XLE, GC=F, CL=F, NVDA, AAPL, TSLA,
AMD), 5-minute bars, 2026-07-21 → 09-17. **14 signals × 8 filters**, fixed before
anything was run. Identical execution for every one — next-bar-open entry, same
ATR stop, same R multiple, same per-instrument cash cost — so a difference
between two rows is a difference between two signals and nothing else.

Split once: **in-sample = first half, out-of-sample = second half.** Selection
happened only on IS. The OOS was spent exactly once.

## The headline

**Nothing survived.** The best in-sample combination reversed completely out of
sample:

| | in-sample | out-of-sample |
|---|---|---|
| gap fade | **PF 1.30** | **PF 0.78** |
| null (random, same window) | 1.07 | 1.01 |
| **edge** | **+0.224** | **−0.228** |
| instruments above null | 7 / 10 | **1 / 10** |

Per-instrument OOS: 0.29, 0.64, 0.71, 0.75, 0.78, 0.79, 0.81, 0.81, 0.86, 1.42.

And the in-sample result looked *good*. It beat the null on 7 of 10 instruments,
it had prior support (overnight gap reversion is a documented effect), and it
survived the robustness check everyone runs — vary the stop:

| stop | PF | null | edge |
|---|---|---|---|
| 2.0 × ATR | 1.30 | 1.07 | **+0.224** |
| 3.0 × ATR | 1.18 | 0.94 | **+0.243** |
| 4.0 × ATR | 1.23 | 0.91 | **+0.318** |

All three positive, and the edge *grew* with stop distance. That is exactly what
a real effect is supposed to look like — and it was still noise. **~57 cells were
tested and the maximum was taken.** Parameter robustness is not out-of-sample
evidence; it never was.

## Two harness bugs the controls caught

Neither would have been visible without running random entries through the same
machinery.

**1. The cost was 10× too large and killed everything.** A flat 2 bps across a
basket spanning XLF at \$57 and gold at \$4,400 is not one assumption, it is
twelve. On SPY it charged \$0.15 against a real penny spread — **37% of the risk
budget per trade**. Every one of the 14 signals came back in the band 0.55–0.77,
which looked like a clean sweep of negatives. It was the cost:

| cost | random null PF |
|---|---|
| 0 bps | 1.031 |
| 0.15 bps | 1.003 |
| **2 bps** | **0.789** ← where all 14 "results" sat |

Fixed to per-instrument cash costs (one spread each way).

**2. At a tight stop the data cannot decide the trade.** With a 0.75 × ATR stop,
a single 5-minute bar often contains *both* the stop and the target, and OHLC
cannot say which came first. The choice is not neutral — signals fire at volatile
moments, so they meet this case more often than random entries do:

| signal | stop-first | target-first |
|---|---|---|
| volume climax fade | 0.75 | **1.34** |
| volume thrust | 0.73 | 1.06 |
| gap fade | 0.84 | 1.12 |

The same data, two defensible assumptions, opposite conclusions. Widening the
stop to 2.0 × ATR drops ambiguity to **0%** and makes both readings identical, so
the experiment became answerable rather than assumed.

## In-sample, all 14, once it was decidable

Null = 1.073. Only two cleared it, and both are on this list of failures now:

| signal | PF | vs null |
|---|---|---|
| gap fade | 1.30 | **+0.224** |
| range position | 1.11 | +0.040 |
| vwap cross | 1.05 | −0.020 |
| bollinger reversion | 1.04 | −0.030 |
| momentum vs atr | 0.99 | −0.081 |
| volume climax fade | 0.98 | −0.091 |
| channel breakout | 0.96 | −0.113 |
| vwap reversion | 0.96 | −0.115 |
| ema 9/21 cross | 0.93 | −0.146 |
| volume thrust | 0.92 | −0.149 |
| rsi2 reversion | 0.92 | −0.152 |
| opening range break | 0.92 | −0.157 |
| first bar continue | 0.75 | −0.326 |
| initial balance break | 0.75 | −0.328 |

RSI(2), Bollinger reversion, opening range breakout, initial balance, VWAP
reversion, EMA cross — the whole retail canon, plus the desk-flavoured ones —
all at or below a random entry with the same stop and target.

## What this actually says

Not "intraday trading doesn't work." It says **two months of 5-minute bars on
twelve instruments cannot distinguish any of these from chance**, and that a
search this size will hand you a false positive every time if you stop at the
in-sample maximum.

The binding constraint is the same one this project has hit at every turn: **a
filter's cost is sample size**, and the data volume available here is too small
for the number of questions being asked. 57 cells against ~180 trades per cell
is not a search, it is a lottery with a good-looking winner.

## What would make this answerable

1. **Years, not months.** 5m bars over 3–5 years per instrument. Yahoo caps at
   60 days; this needs a paid or broker feed.
2. **More instruments**, so the cross-sectional median has power.
3. **Pre-registered, once.** The protocol here is right — the data isn't deep
   enough for it yet.

Against everything measured this session, one thing still stands: the
**order block + session + HTF bias** combination in `SMC_COMPONENTS.md` reached
the 98th percentile of its own control with both halves positive, on 82 trades.
That is the only candidate that has not yet failed, and it deserves the same
treatment as above — a real out-of-sample, on data deep enough to spend one.
