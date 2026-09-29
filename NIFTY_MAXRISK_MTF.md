# Maximum risk, m5 / m15 / m45 / h1

NIFTY 50 ATM options, September 2026, ₹5,00,000 start. One rule held **fixed**
across all four timeframes — `conf2_distinct`, RR 3.0, 24-bar cap — so the
comparison is the bar size and not another search. Risk compounds off **live**
equity, which is what an account does and what sizing off the opening balance
hides.

## The headline you asked for

| timeframe | expiry | risk | n | final | × start | worst DD | **RUIN%** |
|---|---|---|---|---|---|---|---|
| **m5** | expiry-day | **100%** | 9 | **₹28,95,868** | **5.79×** | 93.9% | **12.9%** |
| m5 | expiry-day | 50% | 9 | ₹25,30,624 | 5.06× | 90.1% | 5.5% |
| m5 | expiry-day | 25% | 9 | ₹21,25,543 | 4.25× | 62.3% | 0.0% |
| m5 | expiry-day | 10% | 9 | ₹11,19,085 | 2.24× | 31.3% | 0.0% |
| m5 | expiry-day | 1% | 9 | ₹5,49,303 | 1.10× | 3.4% | 0.0% |

**₹5 lakh into ₹28.9 lakh in one month.** That is the maximum, and it is real
arithmetic on the trade sequence.

It is also a 9-trade sample, on the single cell that the September grid search
selected — and [the control on that search](NIFTY_SEPT_ATM.md) showed random
entries searched the same way beat it in **40 draws out of 40**. Maximum risk
does not repair that. It multiplies it.

## Every other timeframe

| timeframe | expiry | n | 1% risk | 100% risk | RUIN% at 100% |
|---|---|---|---|---|---|
| m5 | expiry-day | 9 | 1.10× | **5.79×** | 12.9% |
| m5 | weekly | 42 | 0.97× | 1.78× | 30.1% |
| m15 | expiry-day | 7 | 1.02× | **0.03×** | **100%** |
| m15 | weekly | 25 | 0.86× | 0.02× | **100%** |
| m45 | expiry-day | 3 | 0.97× | — | — |
| m45 | weekly | 9 | 0.90× | **0.00×** | **100%** |
| h1 | weekly | 3 | 0.99× | 0.13× | **100%** |

**One cell of seven makes money.** On m15, m45 and h1, maximum risk takes the
account to between ₹113 and ₹13,489 — a 97–100% loss — with ruin certain across
every ordering.

Note the trade counts. The rule needs bar density: at h1 it fires **once** in
September on expiry-day, three times on weekly expiries. A higher timeframe is
not a slower version of the same strategy, it is a different and much smaller
sample.

## The thing worth taking from this

My first version of this script reported median and percentile columns from
4,000 reshuffles of the trade order, and every one was identical to the
historical figure. That was not a broken shuffle — **terminal equity under
fixed-fractional compounding is START × ∏(1 + rᵢ), and multiplication
commutes.** Order cannot change where you end up.

Order changes whether you *get* there. So the reshuffle now measures the two
things that are genuinely order-dependent:

| m5, expiry-day | 1% | 10% | 25% | 50% | 100% |
|---|---|---|---|---|---|
| median drawdown | 1.9% | 19.0% | 42.7% | 74.4% | 82.4% |
| worst drawdown | 3.4% | 31.3% | 62.3% | 90.1% | 93.9% |
| **ruin frequency** | 0% | 0% | 0% | **5.5%** | **12.9%** |

At 100% risk the best cell in the study still ends below a fifth of its
starting capital in **one ordering in eight** — on the same nine trades that
produced 5.79×. The 5.79× and the 12.9% are not alternatives; they are the same
result described two ways.

And with nine trades, the 12.9% is itself an estimate with very little behind
it. The honest statement is *ruin is clearly possible at this sizing*, not
*ruin has probability 0.129*.

## What maximum risk actually did

It did not change which strategies work — one cell of seven made money at 1%
risk and the same one cell made money at 100%. Leverage has no view on edge. It
scaled a 9-trade search artifact into a 5.8× headline and a 94% drawdown, and
it scaled the six losing cells into near-total loss.

If the m5 expiry-day cell had a real edge, high risk would still be the wrong
way to express it at this sample size, because the drawdown that comes with it
is not survivable in practice — a 90% drawdown ends most accounts through
margin, nerve, or the broker, long before the arithmetic finishes.

```
python3 scripts/nifty_maxrisk_mtf.py <data-dir>
```
