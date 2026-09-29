# Flat monthly fee, zero brokerage, member-routed

## What this fee structure changes

Earlier in this project I told you that "more trades, smaller returns" was
fatal. Under retail per-order pricing it was: a flat Rs20 per executed order
does not shrink when the edge does, so halving the edge and doubling the count
doubles the fixed cost against unchanged gross.

Your structure has **no fixed per-order term at all**:

```
net = lot x SUM over trades of ( edge_i - c x premium_i )  -  monthly_fee
```

where `c` = 0.2383% (NSE) / 0.2311% (BSE), the statutory round trip. Three
consequences:

1. **Trade count is economically neutral.** Doubling the rate doubles gross and
   doubles cost. It multiplies the average per-trade margin; it cannot change
   its sign. So the instinct behind "40 orders per second with small returns"
   is sound here — it just isn't a source of edge by itself.
2. **The per-trade test is local.** A trade contributes if and only if
   `edge_i > c x premium_i`. Independent of every other trade, and independent
   of the rate.
3. **The monthly fee is sunk.** It never enters the per-trade decision. It only
   sets a volume floor.

## 1. The per-trade test

At premium 150, capturing 10 ticks, one lot:

| index | lot | gross | cost | net | break-even ticks |
|---|---|---|---|---|---|
| NIFTY | 65 | 32.50 | 23.23 | **9.27** | 7.1 |
| BANKNIFTY | 30 | 15.00 | 10.72 | **4.28** | 7.1 |
| SENSEX | 20 | 10.00 | 6.93 | **3.07** | 6.9 |

Break-even ticks are near identical across indices because the cost is
proportional to premium and lot size cancels. `breakeven_ticks = 0.0477 x
premium`, so it is the option's price that sets the hurdle, not the index.

## 2. The monthly fee is a volume floor, not a constraint

At net 9.27 per round trip (premium 150, 10 ticks):

| monthly fee | round trips needed | per day | at 20 round trips/sec |
|---|---|---|---|
| 25,000 | 2,697 | 128 | **6 seconds** |
| 50,000 | 5,394 | 257 | **13 seconds** |
| 100,000 | 10,789 | 514 | 26 seconds |
| 250,000 | 26,972 | 1,284 | 64 seconds |

At HFT rates the fee is covered in the first minute of the month. Do not
optimise against it — optimise against the per-trade test above.

## 3. Latency is what decides it

The trade is to reach a stale quote before its maker reprices. If your round
trip — feed wire, decode, compute, order wire, exchange ack — exceeds the lag,
you arrive after the reprice **every time**, and the only fills left are the
ones where you were wrong. That is not a smaller edge, it is an inverted one.

Against a 10ms lag:

| your loop | budget used | verdict |
|---|---|---|
| 0.2 ms | 2% | comfortable |
| 1.0 ms | 10% | comfortable |
| 2.0 ms | 20% | comfortable |
| 5.0 ms | 50% | workable |
| **10.0 ms** | **100%** | **inverted — you are the slow side** |
| 25.0 ms | 250% | inverted |

Compute is not the problem: tick-to-signal is 15.6us = 0.0156ms, about 0.16% of
a 10ms budget. The wire is the problem, in both directions. Which hosting you
are on — colocation, proximity, or a leased line from another city — decides
this, not the code.

`python -m hft.viability --monthly-fee 50000 --lag-ms 10 --loop-ms 2`

## 4. The lag has never been measured

This is the important one. `Spec.expected_lag_ms` says 10ms for NIFTY, 14 for
BANKNIFTY, 16 for SENSEX. **Those numbers were typed in.** The simulator was
built to reproduce them and the strategy was then shown to capture them, which
demonstrates only that the simulator and the strategy agree with each other.

`hft/lag_probe.py` settles it against a real feed. For each option it keeps two
series sampled onto a common 1ms grid — theoretical value recomputed from the
underlying, and the option's own microprice — and cross-correlates their
**differences** (levels would correlate at ~1.0 at every shift and report a
confident peak that means nothing). If the quote lags, theo leads, and the
correlogram peaks at a positive shift equal to the lag.

Validated against feeds with a lag set by hand:

| true lag | estimated | peak corr | lead over zero-shift | verdict |
|---|---|---|---|---|
| 0.0 ms | 0.0 | 0.498 | 0.000 | **no exploitable lead** |
| 5.0 ms | 5.0 | 0.498 | 0.512 | lead present |
| 10.0 ms | 10.0 | 0.500 | 0.519 | lead present |
| 16.0 ms | 16.0 | 0.497 | 0.484 | lead present |
| 25.0 ms | 25.0 | 0.499 | 0.499 | lead present |

It recovers the answer exactly and correctly reports *no lead* when there is
none. Robust to quote jitter up to 10 ticks (lead 0.427 at jitter 10.0).

**Peak correlation matters more than peak location.** A 12ms lag at correlation
0.05 is not a 12ms opportunity, it is noise with an argmax. The report flags
this: if fewer than 30% of contracts show a lead of 0.05 over zero shift, the
verdict is that the quote is keeping up and there is nothing to capture.

```
# validate it first against a lag you set yourself
HFT_VIRTUAL_CLOCK=1 python -m hft.run_lag_probe --feed sim --sim-lag 12

# then against your broker's feed
python -m hft.run_lag_probe --feed yourmodule:make_feed --symbol NIFTY --seconds 120
```

The `--feed module:factory` seam is `adapters/base.py`'s `Feed` protocol. The
factory is called with `(u_token, contracts, spot, t_years, iv)` and nothing
above that line changes.

## 5. What to ask the broker

These are design inputs I cannot look up, and each one changes the build:

- **Orders per second** allowed on your session, and whether it is a burst or a
  sustained rate. Also how many sessions / NNF IDs you get.
- **Hosting** — colocation at the exchange, proximity, or a leased line. Ask for
  the measured round trip to the matching engine, not the marketing number.
- **Feed protocol and depth** — exchange binary, a vendor normaliser, or a
  WebSocket; full depth or top-of-book; snapshot cadence or true event-driven.
  A 1-second snapshot feed cannot see a 10ms lag at all.
- **OTR pass-through** — order-to-trade penalties land on the member. Ask
  whether they are passed to you and at what threshold. SEBI's 2026-02-04
  revision exempts option orders within +/-40% of LTP or +/-Rs20, so orders at
  the touch should be outside it, but confirm how they account for it.
- **Whether the statutory stack is exactly as modelled** in `costs.py` — check
  one real contract note against it before trusting any number here.
