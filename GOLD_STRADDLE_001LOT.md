# Gold straddle at 0.01 lot — wider initial stop and trailing, swept

0.01 lot XAUUSD is **one troy ounce**, so a $1 move in gold is $1 in the
account. Everything below is in those dollars, with fixed lot size — no
compounding, no risk-based sizing. Costs are retail: **$0.25 spread + $0.07
commission** per round turn, and **−$0.10/night swap**, all per 0.01 lot.

Data: GC=F (gold futures, the closest fetchable proxy for spot) — 13,722 hourly
bars over 2.4 years and 5,030 daily bars over 20 years.

**150 cells tested, 88 profitable. Costs are not the constraint here — fees are
2–8% of gross, nothing like the minute-bar study. But splitting the sample in
half kills four of the eight configurations examined, including the one with
the best headline number.**

---

## The honest benchmark

Holding 0.01 lot of gold is not free of risk either:

| timeframe | hold net | hold max DD | **hold $ per $ of DD** |
|---|---|---|---|
| h1 (2.4y) | +$1,794 | $1,671 | **1.07** |
| daily (20y) | +$3,600 | $1,631 | **2.21** |

On a small fixed-lot account the drawdown is what sizes the account, so
**dollars per dollar of drawdown** is the comparison that matters, not the
total.

## 1. The two knobs, full sample

| tf | pad | trail | n | net $ | max DD $ | **$/DD** | PF |
|---|---|---|---|---|---|---|---|
| h1 | 0.0 | donch 10 | 563 | **$2,144** | $584 | **3.67** | 1.28 |
| d1 | 0.0 | ATR 2 | 296 | **$2,428** | $564 | **4.30** | 1.51 |
| d1 | **1.0** | ATR 2 | 124 | $2,073 | **$224** | **9.25** | **2.46** |
| d1 | 0.5 | donch 20, delay 2 | 92 | $1,852 | $391 | 4.74 | 1.64 |

All four beat holding on $/DD. The widened straddle (pad 1.0) halves the net
but cuts the drawdown 60%, which more than doubles the ratio and lifts profit
factor from 1.51 to 2.46.

Pushing wider still — pad 2.0 — collapses: on daily it leaves 16–22 trades with
profit factors of 0.1–0.5. The channel stops being touched.

## 2. Costs are not the problem on gold at this speed

| tf | pad | spread | gross $ | fees $ | net $ |
|---|---|---|---|---|---|
| h1 | 0.0 | $0.15 | 2,364 | 124 | 2,200 |
| h1 | 0.0 | **$0.50** | 2,364 | 321 | **2,003** |
| d1 | 1.0 | $0.15 | 2,218 | 27 | 2,086 |
| d1 | 1.0 | **$0.50** | 2,218 | 71 | **2,042** |

Doubling or tripling the spread barely moves it. This is the opposite of the
minute-bar result, where a round trip cost 192% of one ATR; here it costs 2–8%
of gross.

**Swap matters more than spread on daily**, because trades are held ~8 days:

| tf | swap/night | net $ |
|---|---|---|
| d1, pad 0 | $0.00 | 2,664 |
| d1, pad 0 | −$0.10 | 2,428 |
| d1, pad 0 | **−$0.40** | **1,720** |

Check your broker's actual gold swap before anything else. A −$0.40 rate costs
more than quadrupling the spread.

## 3. Shuffle control

40 shuffles each — bar shapes and the return distribution kept, only the order
destroyed:

| tf | pad | trail | real net | shuffled median | shuffled best | pct |
|---|---|---|---|---|---|---|
| h1 | 0.0 | donch 10 | $2,144 | −$3,538 | −$1,472 | **100** |
| d1 | 0.0 | ATR 2 | $2,428 | $574 | $2,471 | 98 |
| d1 | **1.0** | ATR 2 | $2,073 | $79 | $1,843 | **100** |
| d1 | 0.5 | donch 20 | $1,852 | $103 | $3,147 | **82** |

Note the daily shuffles are *positive* — shuffling preserves gold's drift, so a
long-capable system still profits on scrambled data. Beating that median is the
real bar, and the pad-0.5 cell does not clear it.

## 4. The split-half test, which changes the answer

### Daily, 20 years, split down the middle

| cell | half | n | net $ | $/DD | PF |
|---|---|---|---|---|---|
| **pad 0.0, ATR 2** | first | 153 | $530 | **3.38** | 1.29 |
| **pad 0.0, ATR 2** | second | 142 | $1,863 | **3.30** | 1.64 |
| pad 1.0, ATR 2 | first | 67 | $388 | 1.94 | 1.54 |
| pad 1.0, ATR 2 | second | 56 | $1,663 | **7.42** | 3.35 |
| pad 1.0, ATR 3 | first | 61 | **−$62** | — | **0.93** |
| pad 1.0, ATR 3 | second | 47 | $887 | 2.53 | 1.96 |

*(holding: first half $760 at $/DD 0.88; second $2,849 at 1.75)*

**pad 0.0 with an ATR-2 trail replicates almost exactly — 3.38 and 3.30 across
two independent decades.** The pad-1.0 headline of 9.25 does not: its first
half is 1.94. The 9.25 is a second-half number wearing a full-sample label.

### Hourly, 2.4 years, split down the middle

| cell | half | n | net $ | $/DD | PF |
|---|---|---|---|---|---|
| pad 0.0, donch 10 | first | 294 | **−$62** | — | **0.98** |
| pad 0.0, donch 10 | second | 269 | $2,176 | 4.66 | 1.46 |
| pad 0.0, ATR 2 | first | 422 | **−$109** | — | **0.96** |
| pad 0.0, ATR 2 | second | 407 | $1,046 | 1.56 | 1.19 |
| **pad 1.0, ATR 5** | first | 108 | $236 | 1.64 | **1.21** |
| **pad 1.0, ATR 5** | second | 99 | $771 | 1.05 | **1.28** |

**On hourly the answer inverts.** The unpadded cells made everything in the
second half and nothing in the first. The only hourly configuration positive in
both halves is the **widened** one, and its profit factors are the most stable
numbers in this document — 1.21 and 1.28.

So: **widening the initial stop helps on hourly and is not needed on daily.**
Four of the eight split tests fail, and the full-sample table does not tell you
which four.

## 5. What this means for an account

Best cell that survives out of sample on daily — pad 0.0, ATR-2 trail:

- **295 trades over 20 years** — about 15 a year
- net **$2,428**, max drawdown **$564**, PF 1.51
- against holding: **$3,600 net, $1,631 drawdown**

You make **two thirds of holding's money with one third of its drawdown.**
That is the whole proposition. It is not a way to make more; it is a way to
make somewhat less, far more smoothly.

At 0.01 lot and gold near $4,160:

| leverage | margin per position |
|---|---|
| 1:100 | $41.62 |
| 1:200 | $20.81 |
| 1:500 | $8.32 |

Margin is irrelevant; the **drawdown** sizes the account. $564 at 3× cover is
~$1,700, at 5× ~$2,800.

Expected return is roughly **$120 a year on 0.01 lot**. That is the scale of a
live test, not an income. Everything here scales linearly with lot size — and
so does the drawdown.

## Verdict

- The system is genuinely profitable on gold net of realistic retail costs, and
  at this speed costs are not what decides it.
- On **daily**, use the plain channel with an **ATR-2 trail**. It is the one
  configuration that replicated across two independent decades.
- On **hourly**, use a **1-ATR wider straddle with an ATR-5 trail** — the only
  hourly cell positive in both halves.
- Do not go wider than ~1 ATR. At 2 ATR the channel stops being touched and the
  sample dies.
- Check the broker's gold swap before the spread. At −$0.40/night it costs more
  than tripling the spread.
- 88 of 150 cells were profitable and half the split tests failed. Treat any
  single cell's headline as an upper bound.

## Files

- `scripts/straddle_sar.py` — `entry_pad`, `trail_delay`, `cost_abs` and
  `swap_per_bar` added for this study.
- `scripts/gold_lot_sweep.py`, `scripts/gold_lot_controls.py` — the runs.
