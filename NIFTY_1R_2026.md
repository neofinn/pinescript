# 1R risk, maximum reward — every bar of 2026 that exists

## First: a year of M5 does not exist here

Checked rather than assumed. Yahoo serves 5-minute NIFTY for **60 days only** —
`1y`, `6mo`, `3mo` and `90d` at 5m all return HTTP errors; 15m and 30m are
capped the same way. The NSE endpoints that would carry more return 403 from
this container.

| | available | sessions |
|---|---|---|
| **M5** | Jul 8 – Sep 29 2026 | **59** |
| **H1** | Jan 1 – Sep 11 2026 | **171** |

So the run below is the whole 5m window that exists, plus **all of 2026 at
hourly** — the closest thing to the year you asked for, and the better test of
the two precisely because 171 sessions can support a 160-cell search where 20
cannot.

**1R** = ₹5,000 fixed per trade, no compounding, so the scoreboard is total R:
what the strategy earned per unit risked, independent of account size.

## M5 — 59 sessions

| # | plan | expiry | RR | n | net | **total R** | PF | maxDD |
|---|---|---|---|---|---|---|---|---|
| **1** | delta_breakout | expiry-day | 3.0 | 44 | ₹2,14,257 | **+42.9R** | 3.01 | 3.8% |
| 2 | delta_breakout | expiry-day | 3.0 | 46 | ₹2,04,988 | +41.0R | 3.03 | 3.7% |
| 3 | delta_breakout | expiry-day | 2.0 | 52 | ₹1,71,155 | +34.2R | 2.74 | 3.6% |
| 7 | dva_edge_fade | expiry-day | 3.0 | 57 | ₹88,110 | +17.6R | 1.58 | 7.9% |

Profitable cells **47/142**. Median cell **−6.1R**.

**Random best-of-grid, breadth matched: +77.0R median** (max +163.7R).
The strategy's best sits at the **3rd percentile**.

## H1 — all of 2026, 171 sessions

| # | plan | expiry | RR | n | net | **total R** | PF | maxDD |
|---|---|---|---|---|---|---|---|---|
| **1** | delta_breakout | weekly | 3.0 | 34 | ₹8,12,382 | **+162.5R** | 4.95 | 11.5% |
| 3 | delta_breakout | weekly | 2.0 | 33 | ₹7,07,467 | +141.5R | 4.34 | 11.5% |
| 5 | delta_breakout | weekly | 1.5 | 34 | ₹4,98,786 | +99.8R | 4.03 | 7.1% |

Profitable cells **22/80**. Median cell **−9.6R**.

**Random best-of-grid: +235.6R median** (max +342.7R).
The strategy's best sits at the **7th percentile**.

## The finding: more data did not fix it

In [the September run](NIFTY_SEPT_ATM.md) I wrote that twenty sessions could
not support a 160-cell search and that more months "would be a test rather than
a description." **That has now been tested, and it was wrong.**

| window | sessions | strategy best | random best (median) | percentile |
|---|---|---|---|---|
| September only | 20 | +9.9R | +28.9R | 0th |
| M5 full window | 59 | **+42.9R** | **+77.0R** | 3rd |
| H1 all of 2026 | 171 | **+162.5R** | **+235.6R** | 7th |

The strategy's maximum grew almost four-fold from 20 sessions to 171. So did
random's. **The search scales with the data at least as fast as the signal
does**, and the ranking barely moved — 0th, 3rd, 7th percentile.

More history does not rescue a wide search. It gives the search more room. What
a 160-cell grid needs is not more data, it is fewer cells: a single hypothesis
fixed before looking, which is the one thing this whole exercise has never
done.

## Two more things the longer windows exposed

**The winner changed.** September picked `conf2_distinct`; the 59-session and
171-session windows both pick `delta_breakout` — a different plan, and on H1 a
different expiry rule (weekly, not expiry-day). That is the same instability
[the walk-forward](WALK_FORWARD.md) measured directly: train→test rank
correlation +0.107 with a CI spanning zero. Whatever wins a window is not what
wins the next one.

**Most cells lose.** 47/142 and 22/80 profitable, with median cells at −6.1R and
−9.6R. The winner is the right tail of a losing distribution in both windows,
which is what makes the random comparison the only meaningful one.

## The number

If you want a single figure: **+162.5R** on hourly bars across 2026, PF 4.95,
11.5% drawdown, 34 trades. It is the best of 80 cells.

And random, searching the same 80 cells, typically found **+235.6R**.

```
python3 scripts/nifty_1R_year.py <data-dir>
```
