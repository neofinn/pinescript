# Orderflow + volume profile

Built both layers, tested six pre-registered signals across four orderflow
gates on ten instruments, then spent the rest of the run trying to kill the one
that survived. It died on the last test.

---

## What was built

| file | what it is |
|---|---|
| `scripts/volume_profile.py` | profile construction: rows, value area, HVN/LVN, developing, prior-session, naked POCs |
| `scripts/vp_signals.py` | the six pre-registered signals and the four orderflow gates |
| `scripts/vp_test.py` | the 48-cell table, each cell against a matched random control |
| `scripts/vp_ablate.py` | does the *volume* in the volume profile do any work |
| `scripts/vp_robust.py` | concentration, breadth, parameter sweep |
| `scripts/vp_confirm.py` | lag-1 across the sweep, and a second cross-section |
| `scripts/test_volume_profile.py` | 22 assertions on the builder |
| `orderflow_volume_profile.pine` | the chart tool, built on real 1-minute sub-bars |

---

## First, what this data can and cannot support

A real volume profile is built from trades. An OHLCV feed has none, so volume
is spread across each bar's own range — the same assumption TradingView makes
without tick data. That assumption is the error term, and it is measurable:
build the identical session from 1-minute bars and from 5-minute bars and
compare.

| | median | 90th pct |
|---|---|---|
| POC displacement, 5m-built vs 1m-built | **0.225 ATR** | **2.56 ATR** |
| value-area high | 0.179 ATR | — |
| value-area low | 0.128 ATR | — |

Typically the POC lands within a quarter of an ATR. **One day in ten it is
2.5 ATR away** — further than the stop this test uses. The level is not stable
to the decimal place a chart draws it at.

Same for orderflow. No feed carries the aggressor flag, so "delta" here is the
tick rule. Against a 1-minute reconstruction the 5-minute proxy correlates
**r = 0.675** (0.63–0.74 across names) — about half the variance of the thing
it stands in for. Volume itself reconciles exactly (1m sums to 5m, ratio
1.000), so the data is sound; the *inference* on top of it is the weak part.

---

## The test

Ten highest dollar-volume US names, 5m bars, 60 sessions. IS = first half,
OOS = second half. Stop 2.0 ATR, target 1.5R, session exit, 36-bar max hold.
Cost is one spread each way in **cash**, per instrument.

Every cell is scored against random entries **at its own trade count**, pooled
the same way, 300 draws — because a filter that cuts 700 trades to 60 buys
variance, and variance alone produces high profit factors.

### 48 cells, and only one shape survives

| signal | gate | IS pct | OOS pct |
|---|---|---|---|
| **dva_edge_fade** | none | **99.0** | **98.7** |
| **dva_edge_fade** | agree | **98.0** | **98.7** |
| **dva_edge_fade** | absorb | **98.7** | **96.7** |
| **dva_edge_fade** | strong | **98.7** | **96.7** |
| pva_edge_fade | none | 12.7 | 88.0 |
| pva_breakout | none | 92.7 | 80.7 |
| ppoc_reversion | none | 35.7 | 36.7 |
| naked_poc_magnet | none | 45.3 | 48.3 |
| lvn_break | none | 93.7 | 61.7 |

**The orderflow gates contributed nothing.** Ungated is as good as any gated
version of the same signal (99.0/98.7 vs 98.0/98.7 and 98.7/96.7). This is the
fourth time in this project a confluence layer has cost sample without buying
selectivity.

Note what *did* work: the **developing** value area, rebuilt bar by bar from
today's volume — not yesterday's levels. Every prior-session signal failed.

---

## Then four attempts to kill it

### 1. Is it the volume, or just the price geometry?

| variant | IS pct | OOS pct |
|---|---|---|
| real | **99.0** | **99.3** |
| volume-blind (every bar's volume = 1) | 78.0 | 85.0 |
| shuffled (volumes permuted within session) | 29.7 | 86.7 |
| extreme-only (running session high/low) | 88.7 | 65.0 |

The volume does real work. Strip it and the effect drops out; scramble the
price–volume pairing and it collapses in-sample. This one it passed.

### 2. Is it carried by a handful of trades?

The median trade is negative in every cell, so this mattered. Dropping the best
1% — **from the controls too**, or the comparison is rigged:

| | n | PF | ctl95 | pct |
|---|---|---|---|---|
| untrimmed IS | 741 | 1.241 | 1.155 | 99.3 |
| trimmed IS | 734 | 1.138 | 1.055 | **99.3** |
| untrimmed OOS | 741 | 1.178 | 1.117 | 98.0 |
| trimmed OOS | 734 | 1.075 | 1.021 | **98.0** |

Passed, and cleanly — the controls have the same tail, so trimming both moves
nothing. My first read of the raw "top 5 trades = 42% of net" figure was wrong;
against a trimmed control it is unremarkable.

### 3. Do the parameters matter?

Fifteen combinations of row count and value-area %. OOS percentile ≥ 73
everywhere, ≥ 96 at va = 0.70 for **every** row count (98.7, 99.3, 98.0, 99.0,
97.7). A ridge, not a spike. Passed.

### 4. Does it survive a different ten instruments?

This is the one it failed.

The value-area edge is computed from a window that includes the very bar
piercing it. That is legal — no future data — but part of the signal may be a
restatement of the bar's own range. Recomputing the edge through bar *i−1*:

| | IS pct | OOS pct |
|---|---|---|
| real-lag1 | **76.0** | 100.0 |

In-sample it stops clearing. And then the decisive test — ten *different*
names (dollar-volume ranks 11–20), **identical dates**, nothing about them used
to choose anything:

| variant | n | PF | ctl95 | ratio | pct |
|---|---|---|---|---|---|
| as-tested | 1481 | 1.019 | 1.124 | 0.906 | **76.7** |
| trimmed | 1467 | 0.803 | 0.895 | 0.897 | 73.7 |
| lag-1 | 1586 | 0.937 | 1.110 | 0.844 | **50.0** |

It does not clear. The lag-1 version lands on exactly the coin flip.

---

## The finding that generalises beyond this signal

My first guess was that the second half of the window was simply a good period.
The split test rules that out:

| set | half | dates | PF | pct |
|---|---|---|---|---|
| A | first | Jun 30 – Aug 11 | 1.241 | **99.3** |
| A | second | Aug 11 – Sep 23 | 1.178 | **98.7** |
| B | first | Jun 30 – Aug 11 | 1.153 | 88.7 |
| B | second | Aug 11 – Sep 23 | 0.823 | **19.0** |

Same dates, same code, opposite answers. Set A is strong in *both* halves; set
B collapses in the second. So it is not the period — it is the basket.

**An in-sample/out-of-sample time split with a fixed universe does not test
whether a result generalises.** Both halves share the same ten names, so
anything basket-specific passes twice and looks confirmed. This signal cleared
a matched control in both halves, at every parameter setting, under trimming,
with the volume ablations supporting a real mechanism — and still failed the
first time the universe changed.

Breadth said so in advance and I under-weighted it: **6/10 names** above the
control median in both halves, with the result concentrated in META (100.0 /
95.7) and TSLA negative in both (21.0 / 15.7). Six of ten is near what a coin
gives. That was the tell, before the second cross-section confirmed it.

---

## What to actually do with this

**The Pine indicator is worth using; the mechanical entry is not.** Nothing
here supports the value-area fade as an automatic signal, and the signal plots
are off by default for that reason. The levels are useful as context — where
volume traded, where it did not, where yesterday's value sat — which is how
desks use a profile and is not a claim that needs a backtest.

If you want to push further, the honest next steps in order:

1. **Real tick data.** The delta proxy carries r = 0.68 of the real thing and
   the POC moves 2.5 ATR on one day in ten. Both ceilings come from the feed,
   not the method, and both would lift with trades-and-quotes data.
2. **Test on the universe you will trade.** If that is Indian index options,
   none of this transfers — it was measured on US equities.
3. **Fix the universe before looking, and swap it once.** That one swap did
   more work here than the entire IS/OOS split.

Reproduce:

```
python3 scripts/test_volume_profile.py       # 22 assertions
python3 scripts/vp_test.py <dir>             # the 48-cell table
python3 scripts/vp_ablate.py <dir>           # volume ablations
python3 scripts/vp_robust.py <dir>           # trimming, breadth, sweep
python3 scripts/vp_confirm.py <dirA> <dirB>  # lag-1 and the second basket
```

---

# Part 2 — the two layers combined, and nothing else

Part 1 used orderflow as a *gate* on profile signals, and the execution came
from outside both: a 2.0 ATR stop and a 1.5R target. ATR is a volatility model,
not a profile or a flow reading, so that test measured the pair-plus-ATR.

This part removes everything else. No moving average, no RSI, no VWAP, no ATR,
no time-of-day filter, no volume surge. The constraint reaches the exit, which
is where these tests usually cheat:

| | comes from |
|---|---|
| entry | a profile level **and** a flow condition, both required |
| stop | one row beyond the structure the trade leans on |
| target | the next profile level in the trade's direction |
| flat | session close — a developing profile does not survive the bell |
| scale unit | value-area width, not ATR |

Five setups, each needing both layers by construction — a level alone fires
nothing, a flow reading alone fires nothing:

| setup | the claim |
|---|---|
| `absorption_at_edge` | aggressive flow into a value edge that doesn't get paid |
| `delta_breakout` | value break with flow behind it *and* cvd at a session extreme |
| `lvn_delta_traverse` | crossing a thin price with someone pushing |
| `cvd_divergence` | new price extreme the flow doesn't confirm, at the value edge |
| `naked_poc_flow` | flow pointing at an untouched POC |

**The control had to change too.** Randomising entries while keeping an ATR
stop compares two different machines. Here every control entry borrows a
(stop distance, target distance) pair from the strategy's *own* realised
entries in the same window, so the risk geometry is identical and only the
timing and direction are random. That isolates the question: does the pair of
layers pick better moments than chance, given the same exits.

## Result: nothing passes

Fifteen cells — five setups × {set A first half, set A second half, set B
whole}. Set B is the universe swap that killed Part 1's survivor, so it is in
from the start this time.

| setup | A-IS | A-OOS | B-ALL | PF range | hit rate |
|---|---|---|---|---|---|
| absorption_at_edge | 47.3 | 14.7 | 43.0 | 0.71–0.83 | 24–29% |
| delta_breakout | 84.3 | 14.0 | 60.7 | 0.83–1.18 | 24–32% |
| lvn_delta_traverse | **2.7** | **2.7** | 79.0 | 0.68–0.86 | 21–23% |
| cvd_divergence | 89.3 | **100.0** | 63.3 | 0.90–1.23 | 28–33% |
| naked_poc_flow | 78.0 | 18.0 | 43.7 | 0.81–1.13 | 28–33% |

One cell out of fifteen clears its control, and its own other two windows
don't. That is what one lucky draw in fifteen looks like.

**Absorption at the value edge is the worst of them** — and it is the most
cited setup in every orderflow course: PF 0.71–0.83 on a 24–29% hit rate,
negative median trade in all three windows.

The intrabar tiebreak doesn't rescue anything. Ties are under 1.5% of trades
and reading them target-first instead of stop-first moves PF by 0.01–0.03, so
both readings give the same verdict.

**The pure exits performed worse than the borrowed ones.** Part 1's ATR stop
with a fixed R multiple produced ~46% hit rates; the profile's own levels
produce 21–33%, because the stop sits one row past structure while the target
is a whole level away. Making the exit internally consistent did not make it
better — worth knowing before building a system on the principle that levels
should define the risk.

## The inversion, which is a trap worth showing

`lvn_delta_traverse` lands at the **2.7th percentile in both set-A windows** —
consistently worse than random, which is the classic invitation to just trade
it backwards. Mirroring the geometry so the flip is a fair trade:

| variant | A-IS | A-OOS | B-ALL | PF (A-IS / A-OOS / B) |
|---|---|---|---|---|
| as-built | 1.0 | 2.3 | 81.3 | 0.684 / 0.700 / 0.856 |
| inverted | 65.0 | **99.0** | **96.0** | 0.947 / 1.173 / **0.966** |

The inversion passes two of three windows including the universe swap — and
**loses money in two of those three**. On set B it sits at the 96th percentile
with a profit factor of 0.966.

That is the cleanest demonstration in this whole project that *beating the
control* and *making money* are different questions. The control shares the
strategy's exit geometry, and that geometry is a net loser after costs, so
beating it convincingly still hands you a losing system. A percentile is
evidence that a signal carries information. It is not evidence of profit, and
neither number substitutes for the other.

## What this says about the combination

The two layers do not rescue each other. Part 1 found the orderflow gate added
nothing to profile signals; Part 2 finds that setups requiring both layers do
no better, and the most-taught one does worst. Across both parts the pattern is
the same: **each added condition cost sample faster than it bought
selectivity**, and the unfiltered or simplest version was never beaten by a
more confluent one.

The ceiling is probably the data, not the idea. The delta here is the tick rule
at r = 0.68 against a 1-minute reconstruction, and the POC moves up to 2.5 ATR
depending on bar granularity. Absorption in particular is defined on
per-level bid/ask volume that no OHLCV feed carries — what is tested above is
the nearest thing that can be built, and it may simply be too blunt. Real
trades-and-quotes data would answer that; nothing short of it will.

`vp_orderflow_strategy.pine` implements all five setups with the level-based
exits, defaulting to `none`, with the result in its header.

```
python3 scripts/vp_of_run.py <dirA> <dirB>   # the 15-cell table
```
