# Two-sided stop orders, stop-and-reverse — the straddle bot

The machine, as specified:

> Stop orders on both sides. Whichever side gets hit, the other side trails as
> the stop loss, with an active stop order resting for the next move.

**The signal is real — it sits at the 100th percentile against shuffled data on
every test. On hourly bars its own transaction costs destroy it completely. As a
daily multi-market portfolio it beat buy-and-hold on return and drawdown — and
that outperformance came entirely from BTC and ETH. Remove those two and it
loses to holding.**

---

## What was built

- `bots/straddle_bot.py` — the live bot. Dry-run by default; a broker adapter
  and credentials are required before it can send anything.
- `bots/paper_broker.py` — serves real bars, fills nothing, so the state
  machine can be watched without an account existing.
- `scripts/straddle_sar.py` — the backtest engine. The bot's state machine is
  deliberately the same logic, so what runs is what was measured.
- `straddle_sar.pine` — the chart version.

## Data and fill assumptions

30 markets × 730 days hourly (272,848 bars) and 30 markets × 20 years daily.
Futures, indices, ETFs, single names, FX and crypto. Costs 1–10 bps by vehicle.

A stop fills at its price or at the bar's **open** if the bar gapped past it,
never better. Costs are charged on **every leg**, so a reversal costs twice an
entry — the dominant expense in any SAR system and not hidden here. If one bar
spans both entry levels while flat, the order of fills is unknowable from bar
data, so the pessimistic reading is taken: the losing side fills first and is
immediately stopped. Those whipsaws are counted separately (197 at the tightest
setting, 5 at the widest).

## 1. On hourly bars it loses, in 24 of 24 configurations

| mode | entry | trail | trades | mean × | mean CAGR | mean DD | beat hold |
|---|---|---|---|---|---|---|---|
| SAR | 20 | donchian 10 | 18,413 | 0.998 | −3.26% | 35.3% | 3/30 |
| flat | 20 | donchian 10 | 12,335 | 1.022 | −1.28% | 28.7% | 4/30 |
| flat | 50 | ATR 3.0 | 8,066 | 1.076 | **+1.69%** | 23.2% | 2/30 |

Buy-and-hold, equal weight: **19.07% CAGR**.

- cells with positive mean CAGR: **4 / 24**
- cells beating buy-and-hold: **0 / 24**

The gradient is unmistakable and it points at one thing: every configuration
with fewer trades does better. Always-in SAR is worse than flat-and-rearm in
every pairing.

## 2. It is costs, not the absence of signal

The same system with the spread scaled:

| cost × | trades | mean × | mean CAGR |
|---|---|---|---|
| **0.00** | 18,413 | **1.825** | **+17.03%** |
| 0.25 | 18,413 | 1.465 | +10.31% |
| 0.50 | 18,413 | 1.241 | +4.88% |
| **1.00** (real) | 18,413 | **0.998** | **−3.26%** |
| 2.00 | 18,413 | 0.785 | −13.47% |

**At zero cost it returns +17% a year. At the real spread, −3.3%.** The idea is
worth about twenty points of CAGR and the execution costs more than that. That
is a completely different failure from every other pattern in this repo, and it
points at a fix rather than a wall.

## 3. It beats shuffled data at the 100th percentile

The right control for a trend system is not a random entry level — it is the
same data with the **order destroyed**. Every bar's shape and the whole return
distribution are kept; only serial correlation is removed. A trend follower's
entire thesis is that order matters.

| config | real CAGR | shuffled median | shuffled 95th | pct |
|---|---|---|---|---|
| as asked (SAR, donchian) | −3.26% | −9.21% | −5.24% | **100** |
| best hourly cell | +1.69% | −6.60% | −2.35% | **100** |

50 shuffles per market. The system is genuinely harvesting trend. It just
cannot keep what it harvests at hourly frequency.

## 4. Slower bars, as the cost result predicts

| timeframe | trades | mean CAGR | hold CAGR |
|---|---|---|---|
| h1 (2.4y) | 18,413 | −3.26% | 19.07% |
| h4 (2.4y) | 4,735 | +1.43% | 19.05% |
| **daily (20y)** | 8,862 | **+5.39%** | 12.53% |
| daily, flat-and-rearm | 6,144 | **+6.84%** | 12.53% |

Going slower turns the sign around, exactly as §2 says it should. Per single
market it still trails buy-and-hold.

## 5. As a portfolio — where it finally works

A trend system is not run one market at a time. One market's whipsaw is
another's trend. All 30 markets, daily, 0.5% of equity risked per trade, sized
by ATR, capped at 20% notional each. Matched window, 2017-11-09 → 2026-10-02:

| | final × | CAGR | max DD | MAR |
|---|---|---|---|---|
| **straddle bot** (entry 20, donchian, flat) | **5.01** | **19.87%** | **22.0%** | **0.90** |
| straddle bot (entry 50, ATR 3.0, flat) | 3.67 | 15.74% | 21.8% | 0.72 |
| straddle bot (entry 20, donchian, **SAR**) | 3.79 | 16.16% | 30.1% | 0.54 |
| equal-weight buy-and-hold, daily rebalanced | 4.12 | 17.25% | 30.4% | 0.57 |
| SPX alone | 2.99 | 13.09% | 33.9% | 0.39 |

**Higher return and a third less drawdown.** MAR 0.90 against 0.57.

And at portfolio level the shuffle control still clears everything:

| | CAGR |
|---|---|
| real portfolio | **19.87%** |
| shuffled median | 8.71% |
| shuffled 95th percentile | 15.20% |
| shuffled **best of 40** | 17.94% |

The real result beats the best of forty shuffles. **100th percentile.**

## 6. The caveat that decides it

| variant | final × | CAGR | max DD | MAR |
|---|---|---|---|---|
| headline, 30 markets | 5.01 | 19.87% | 22.0% | 0.90 |
| **without BTC and ETH** | **2.33** | **9.96%** | 23.8% | **0.42** |
| …against hold without BTC and ETH | 3.30 | **14.38%** | 30.4% | **0.47** |
| double the spread | 4.34 | 17.94% | 22.7% | 0.79 |
| quadruple the spread | 3.25 | 14.18% | 24.4% | 0.58 |

It survives four times the assumed spread. It does not survive removing two
markets. **Ex-crypto it returns 9.96% against buy-and-hold's 14.38%, and loses
on MAR too, 0.42 against 0.47.**

The entire measured edge lived in the two most strongly trending markets in the
sample — which are also the two with the highest costs and the shortest history.
That is not a reason the system is wrong; trend followers are *supposed* to make
their money in the few markets that trend hardest, and cutting the winners out
of a trend study is its own kind of error. It is a reason the 19.87% is not a
number to size a position against.

### A correction

My first portfolio benchmark returned 372,698× and a 97% drawdown. That was a
bug, not a result: markets with different trading calendars were contributing
multi-day returns as if they were single-day ones, and on weekends — when only
BTC and ETH have bars — crypto took the entire portfolio weight. Fixed by
putting every market on one calendar and forward-filling closed days to a zero
return. The corrected benchmark is the 4.12× / 17.25% above.

## How to run it

```
python3 bots/straddle_bot.py --symbol GC=F --timeframe 1d --once
```

Dry-run: it prints the orders it would rest and exits. Drop `--once` to loop.
`--live` requires a `broker_adapters.make_broker` and credentials in the
environment; without both it stays a dry run.

Credentials belong in a `.env` on your own machine, never in this repository and
never pasted into a chat. Give the key the narrowest permission your broker
offers.

## What matters more than the strategy

The bot's correctness properties, in the order they will bite you:

1. **Reconcile first.** Every cycle reads the broker's real position and orders.
   Broker state wins over local state. A bot that trusts its own memory after a
   restart or a missed fill doubles its size.
2. **One stop, never two.** Deterministic client IDs; the old stop is cancelled
   and confirmed before the new one goes out. A trail that leaves its
   predecessor alive is how an account ends up short twice.
3. **Never loosen a trail.**
4. **Closed bars only.** The backtest assumed it; so does the bot.
5. **Atomic state writes**, so a crash mid-write cannot corrupt the file.

## Verdict

Run it on daily bars or slower, across many markets, never on an hourly chart —
§2 is unambiguous that hourly is a cost problem with no fix available at that
frequency.

Paper-trade it long enough to sit through a 22% drawdown before any real money
is involved, and size it knowing that the headline number came from a 8.9-year
window in which two crypto markets did the work.
