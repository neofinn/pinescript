# Making it live

## Read this first

Nothing in this project cleared its control. The best result — the rebalanced
three-index portfolio — sits at the **83rd percentile** of what shuffling
Kronos's predicted directions produces. Two candidates reached 90–92nd on small
control samples and both collapsed when the controls were run properly.

So: **the signal is not ready to risk money on.** What follows is how to build
the system anyway, because three things make that worth doing:

1. **The portfolio construction is real.** Splitting across sleeves and
   rebalancing daily cut drawdown 36.4% → 25.6% → 16.5% → 14.9% across three
   separate tests. That is signal-agnostic and will improve whatever you
   eventually trade.
2. **Forward paper data is the only evidence that counts.** Every backtest here
   is contaminated by the fact that I chose what to test after seeing the data.
   A live paper log is not.
3. **The infrastructure is the long pole.** Building it now, while nothing is at
   risk, is strictly better than building it under pressure later.

## What already exists

| module | what it does |
|---|---|
| `hft/orders.py` | order state machine, marketable-IOC vs passive, **no market orders anywhere** |
| `hft/risk.py` | pre-trade limits that **fail closed** — reject, never clamp |
| `hft/execution.py` | execution gate, aggression ramp, no-chase band |
| `hft/live.py` | live runner, **paper by default**, sending requires an explicit flag |
| `hft/costs.py` | the real statutory stack, STT/txn/stamp/GST |
| `hft/preflight_feeds.py` | feed reachability probe |
| `scripts/portfolio_rebalanced.py` | the three-sleeve daily-rebalanced allocator |

## What is missing, in priority order

### 1. A real options chain — this is the binding constraint

Every premium in this study is Black-Scholes off India VIX with **no smile and
no skew**, and every fill assumes one price with no book. That is the single
largest gap between these numbers and reality.

You need, from a broker API on your own machine:

- live bid/ask per strike, not a model price
- traded volume and open interest per strike
- depth at the touch, so a 40-lot order is checked against what is actually
  resting there

NSE's endpoints return **403 to this container** but respond from a normal
connection — `hft/preflight_feeds.py` tests that in one command.

### 2. Close the measured backtest-to-live gaps

These are not hypothetical. Each was measured in this project:

| gap | what was measured | what live will do |
|---|---|---|
| **stop slippage** | **40–51% of trades gapped through the stop**; the backtest floored the loss at the limit | fills worse. Removing the floor cut H1 from 8.12× to 1.95× |
| option pricing | BS off VIX, no skew | ATM 0DTE IV diverges most exactly where the strategy trades |
| lot sizes | derived from the ~₹7.5 lakh notional rule | look them up from the contract master |
| index volume | synthetic, from constituent traded value | agrees with the ETF to ~10% of a session's range — fine for context, not for a tick-precise level |
| order size | 476 lots assumed filled at one price | check depth; split or skip |
| Kronos latency | 4–8s per forecast on 4 CPU threads | fine hourly, tight on 5m. Keep the model resident |

### 3. Wire the strategy into the paper runner

The allocator is `scripts/portfolio_rebalanced.py`. It needs a live adapter that
each morning divides the balance three ways, and each hour asks Kronos for a
direction on NIFTY / BANKNIFTY / SENSEX, places the supply/demand stop, and
submits **through `hft/risk.py`** rather than around it.

## The staging that actually protects you

**Do not skip a stage because the previous one looked good.**

| stage | duration | gate to advance |
|---|---|---|
| **1. Paper, logged** | 3 months min | ≥60 trades, and live PF within the backtest's control band. If paper lands where shuffled directions land, stop here |
| **2. One lot, real** | 2 months | realised slippage vs modelled — this is where the 40% gap-through shows up |
| **3. 25% size** | 2 months | live drawdown ≤ backtest drawdown × 1.5 |
| **4. Full size** | — | only if 1–3 all held |

Stage 1 is not a formality. It is the only unbiased evidence this project will
ever produce, because it is the only test where the strategy was fixed before
the data existed.

## Hard rules for the live loop

- **Paper is the default.** Sending orders requires an explicit flag, every run.
- **Every order passes `hft/risk.py`.** No path around it. It rejects rather
  than clamps — a clamped order is still an order you did not intend.
- **Kill switch on daily loss.** The 5%-of-equity per-trade cap does not bound a
  day. Add a daily stop that flattens and refuses new entries.
- **No market orders.** Already enforced in `hft/orders.py`; keep it.
- **Reconcile positions against the broker every cycle**, not against internal
  state. Internal state is what is wrong when something is wrong.
- **Log the decision, not just the fill** — forecast, zone levels, size, and the
  reason for every rejection. Without that the paper stage teaches nothing.

## Credentials

Broker keys go in a `.env` **on your machine**, never in this repo and never
pasted into a chat. `.gitignore` already covers `var/` and `.env`. I cannot hold
or use them, and the live routing has to run from your machine under your own
authorisation — this container cannot reach NSE and should never hold a trading
credential.

## What I would actually do

Build stages 1 and 2 of the infrastructure now. Run paper for three months on
the rebalanced three-index portfolio **as specified, unchanged**, and log
everything.

Then compare the paper result against the direction-shuffled control band. If it
lands inside that band — as every backtest here did — you will have learned that
for the price of three months and no capital, which is the cheapest this lesson
is ever available.

If it lands above, you will have the first genuinely out-of-sample evidence in
the project, and *then* the money question is worth asking.
