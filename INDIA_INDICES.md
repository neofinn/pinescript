# Indian indices

Same setups, same confluence rules, same 1:2, on NIFTY, BANKNIFTY and SENSEX.
Two obstacles had to be cleared before any of it could run, and both are worth
more than the result table.

## 1. Indian indices print no volume

Checked, not assumed. 374 five-minute bars each:

| | bars | volume > 0 |
|---|---|---|
| ^NSEI (NIFTY), ^NSEBANK, ^BSESN, ^CNXIT, ^NSMIDCP | 374 | **0** |
| NIFTYBEES, BANKBEES | 374 | 368 (98.4%) |
| RELIANCE, HDFCBANK, ICICIBANK | ~366 | ~360 (98.1%) |

A volume profile on a series with no volume is not a volume profile. So one had
to be built, as **traded value**: each constituent contributes price × volume,
summed per five-minute stamp. Share counts cannot be added across HDFC Bank at
~₹1,000 and Bajaj Finance at ~₹9,000; rupees can. 49 of 50 NIFTY constituents
and all 12 BANKNIFTY names, ₹265 cr and ₹73 cr median traded value per bar,
59 sessions.

**Then it was checked against a second witness.** The index ETFs have real
volume of their own, so the same session was built both ways and the levels
compared:

| | days | POC gap | as % of price | as % of session range |
|---|---|---|---|---|
| NIFTY vs NIFTYBEES | 59 | 12.9 pts | 0.053% | **10.5%** |
| BANKNIFTY vs BANKBEES | 59 | 30.8 pts | 0.054% | 7.5% |

Two independent volume sources agree to about five hundredths of a percent, so
the construction is measuring the right thing. But that gap is ~10% of a typical
day's range — **these levels are indicative, not precise**, and a rule trading
one to within a few points would be trading the construction.

> **SENSEX carries a caveat the other two do not.** Its synthetic volume uses
> the NSE NIFTY-50 basket as a proxy, because the 30 BSE constituents were not
> fetched separately. It is the weakest data here — and it happens to produce
> the best-looking numbers below. Treat them as the least trustworthy, not the
> most promising.

## 2. India has no daily expiry

This matters more than anything in the tables. SEBI's rationalisation left **one
weekly expiry per exchange**, and BANKNIFTY's weeklies were withdrawn entirely —
it is a monthly contract now.

| | expiry available |
|---|---|
| NIFTY | one weekly (NSE) |
| SENSEX | one weekly (BSE) |
| BANKNIFTY | **monthly only** |

So "0DTE every session", the whole frame of the last two runs, is a US
structure. In India it exists on one day a week for NIFTY and one day a month
for BANKNIFTY. *These weekday rules are parameters in the code, not constants —
the regime has changed more than once and will again. Check your broker's
contract master before trusting a number from this file.*

And zero brokerage is not zero cost. What remains is **proportional to
premium**, so lot size drops out of the arithmetic entirely:

| | round trip |
|---|---|
| NSE | **0.2383% of premium** |
| BSE | 0.2311% of premium |

STT at 0.15% on the sell leg is about 63% of that.

## Underlying result: nothing survives the split

Pooled across all three indices, 1:2 on the index, one futures spread each way
(0.5 pt NIFTY, 4 pt BANKNIFTY/SENSEX):

| plan | IS PF | IS pct | OOS PF | OOS pct |
|---|---|---|---|---|
| absorption_at_edge | 1.043 | **92.0** | 0.610 | **19.0** |
| conf2 | 1.173 | **88.3** | 0.781 | **18.7** |
| conf2_majority | 1.173 | 87.7 | 0.793 | 25.0 |
| conf3 | 1.721 | 84.7 | — | too few |
| cvd_divergence | 1.015 | 81.0 | 0.855 | 48.0 |
| conf2_distinct | 1.153 | 78.3 | 0.875 | 39.7 |
| naked_poc_flow | 1.077 | 70.0 | 0.799 | 27.0 |
| lvn_delta_traverse | 0.761 | 31.0 | 0.833 | 48.0 |
| delta_breakout | 0.783 | 19.0 | 0.773 | 16.7 |
| dva_edge_fade | 0.788 | 13.7 | 0.888 | 48.3 |

**Every plan has a profit factor below 1 out of sample.** Nothing reaches the
50th percentile of its control in OOS. The three that looked best in-sample
(92.0, 88.3, 87.7) land at 19.0, 18.7 and 25.0 — that is what fitting looks
like when you are allowed to see it fail.

The median trade is −8 to −28 index points everywhere, against a NIFTY session
range of ~123 points.

## Options: both expiry regimes

₹5,00,000 capital, 1% risk, India VIX for implied vol, lots 75 / 35 / 20,
statutory stack above.

**Nearest weekly or monthly expiry — everything loses.** `dva_edge_fade` posts
−₹5.36L in sample and −₹5.85L out, on ₹5L of capital: a **111.7% and 126.9%
drawdown**, which is not a drawdown, it is ruin. Fixed ₹5,000 risk keeps sizing
off the opening balance long after the balance is gone; equity-scaled it blows
up rather than going negative, but it blows up.

**Expiry day only — India's actual 0DTE — with a matched control:**

| plan | window | n | PF | control 95th | pct |
|---|---|---|---|---|---|
| delta_breakout | OOS | 52 | **2.284** | **3.11** | 82.6 |
| conf2_distinct | OOS | 28 | **1.873** | **5.51** | 64.3 |
| conf2_distinct | IS | 29 | 0.191 | 3.10 | **0.0** |
| absorption_at_edge | IS | 34 | 1.445 | 2.20 | 84.0 |
| absorption_at_edge | OOS | 39 | 0.595 | 2.16 | 46.0 |
| cvd_divergence | IS | 67 | 1.404 | 2.32 | 75.3 |
| cvd_divergence | OOS | 84 | 0.677 | 2.12 | 21.3 |
| naked_poc_flow | OOS | 11 | 0.495 | **6.18** | 18.0 |

A profit factor of 2.28 sounds like a system. At 52 trades the control reaches
3.11, so it is the 82.6th percentile — and the same plan sits at 43.2 in sample.
`conf2_distinct` runs **0.0 percentile in sample and 64.3 out**: the sign flips
between halves, which is the signature of no effect at n≈28.

Nothing clears 95 in either window. Nothing clears 50 in both.

## What this adds to the rest of the study

This is the **universe swap at the level of a whole market**. `dva_edge_fade`
was the one signal that cleared its control on the ten largest US names in both
halves, across fifteen parameter settings, under trimming, with the volume
ablations supporting it. On Indian indices it is the **worst plan in the
table** — 13.7th percentile in sample, ruinous in options.

Five markets' worth of evidence now point the same way: these levels carry
something on the specific baskets where they were first measured, and nothing
that transfers.

The honest reading for Indian index trading specifically: the data here cannot
support the strategy. The volume is synthetic and agrees with its cross-check to
only a tenth of a session's range; there is no daily expiry to scalp; and the
statutory 0.24% of premium is charged whether or not your broker charges you.
Any real attempt would need **tick data with the aggressor side** and a **real
options chain with real bid-ask**, neither of which is reachable from here — the
NSE feed returns 403 and BSE serves a challenge page.

```
python3 scripts/india_validate.py <dir>    # the two-witness check
python3 scripts/india_run.py <dir>         # underlying, IS/OOS, per index
python3 scripts/india_options.py <dir>     # both expiry regimes
```
