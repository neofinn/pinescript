# NIFTY 50, September 2026, ATM option buying — maximum reward

You asked for the maximum. Here it is, and here is what it is worth.

**Setup.** NIFTY 50, September 2026 (20 sessions), buying **ATM** options —
taken literally as 0.50 delta, so the strike is not a tunable parameter.
₹5,00,000 capital, ₹5,000 risk per trade, lot 75, 50-point strikes, India VIX
at each session's **first** observation (using the day's last value would price
a 10am option with a number known only at 15:30). NSE statutory costs, 0.2383%
of premium round trip, plus half a point of spread.

**Grid.** 10 plans × 2 expiry choices × 4 reward-to-risk ratios × 2 hold caps
= **160 configurations**, 136 of which produced at least five trades.

## The maximum

| # | plan | expiry | RR | hold | n | net | PF | win% | maxDD | ret/DD |
|---|---|---|---|---|---|---|---|---|---|---|
| **1** | **conf2_distinct** | expiry-day | 3.0 | 2h | **9** | **₹49,565** | 4.05 | 55.6 | **1.8%** | 5.63 |
| 2 | conf2_distinct | expiry-day | 2.0 | none | 10 | ₹36,659 | 2.82 | 50.0 | 1.8% | 4.12 |
| 3 | delta_breakout | expiry-day | 3.0 | none | 21 | ₹32,054 | 1.67 | 23.8 | 5.0% | 1.28 |
| 4 | lvn_delta_traverse | expiry-day | 3.0 | none | 10 | ₹29,849 | 3.20 | 40.0 | 1.3% | 4.49 |
| 8 | conf2_distinct | expiry-day | 1.0 | none | 11 | ₹26,405 | 3.50 | **72.7** | 0.8% | 6.86 |

**+₹49,565 on ₹5,00,000 — a 9.9% month with a 1.8% maximum drawdown and a
profit factor of 4.05.** On nine trades.

That is a genuinely attractive-looking line, and if this document stopped here
you would have every reason to trade it.

## What the maximum is actually made of

Two things say not to.

**First, the grid is mostly losses.** Only **36 of 136** configurations made
money. The median configuration lost **₹20,027**. The winner is the right tail
of a distribution centred well below zero — picking it is picking the best of
136 draws, not discovering a rule.

**Second — and this is the number that settles it — random entries searched the
same way do better.** I ran the identical 160-cell grid on random entries
carrying the strategy's own stop distances, giving random the *same search
breadth* (each plan slot gets its own random plan per draw, so random searches
160 cells too, not 16):

| best-of-grid on random entries, 40 draws | |
|---|---|
| median | **₹144,557** |
| 90th percentile | ₹212,235 |
| maximum | ₹238,380 |
| **the strategy's best (₹49,565) sits at the** | **0th percentile** |

**All 40 random draws produced a better best-of-grid than the strategy did.**
The typical random search found nearly three times the strategy's maximum.

This is not a subtle effect. Over 20 sessions, with trade counts of 9 to 24, a
160-cell search finds six-figure "profits" in noise as a matter of course.
Maximising reward over a grid on a month of data does not measure a strategy —
it measures the grid.

## And August

September's winner, unchanged, in August: **5 trades**, ₹53,948, PF 14.20.

A profit factor of 14 on five trades is not confirmation of anything. It is the
same phenomenon one month earlier, and it is listed only so it is not mistaken
for out-of-sample support.

## The honest answer to the question

The maximum reward configuration on this data is `conf2_distinct`, expiry-day
only, RR 3.0, two-hour hold cap: **+9.9% with a 1.8% drawdown**.

I would not trade it, and the reason is not caution — it is that the control
says random does better. If you want a number from this exercise that means
something, it is not the ₹49,565. It is the **₹144,557 median that random
achieved under the same search**, which is the size of the illusion any grid
search over one month of an intraday Indian options strategy will generate.

What would make this answerable:

1. **More months.** Twenty sessions cannot support a 160-cell search. The same
   grid over two years, with the configuration chosen on the first half only,
   would be a test rather than a description.
2. **A real options chain.** Every premium here is Black-Scholes off India VIX,
   not a traded bid and ask. Weekly ATM NIFTY options are liquid, so the model
   is not absurd, but a real chain would remove an assumption that currently
   sits underneath every rupee in the table.
3. **Fix the configuration before looking.** One plan, one RR, one expiry rule,
   chosen for a reason and then tested. The search is what destroyed this
   result, and no amount of extra data fixes a search this wide on a sample
   this small.

```
python3 scripts/nifty_sept_atm.py <data-dir>
```
