# 40 orders per second: what it runs into

Measured with `HFT_VIRTUAL_CLOCK=1 python -m hft.rate_lab`. Read the first
section before the rest — it invalidates every earlier number in this repo that
was produced without it.

## 0. The simulator was measuring scheduler jitter

Every timing decision in this system reads `clock.now_ns`: token-bucket refill,
the per-contract gap, book staleness, minimum hold. Under a real clock those
decisions depend on how fast the interpreter happens to run.

Six runs, identical config, identical seeds:

```
net  +6,138  +2,218  +2,564  +2,564  +2,955  +1,309
mean +2,958   sd 1,511   range 1,309..6,138   (4.7x)
```

The first pass of the threshold sweep appeared to find an optimum at
`spread_frac 0.30` (+11,433 against +3,998 either side). It was noise. Under a
deterministic clock that peak does not exist.

`HFT_VIRTUAL_CLOCK=1` binds `now_ns` to a clock the driver advances, and a run
becomes bit-reproducible. `real_ns` stays available for latency, which is the
one thing that has to be measured against a real clock — run *without* the env
var when latency is what you are measuring.

## 1. The floor, which no order rate moves

```
breakeven_edge_per_unit = round_trip_fee / lot_size
```

At Rs25 per lot per fill (Rs50 round trip), capture_frac 0.60, tick 0.05:

| index | lot | Rs/unit needed | ticks to capture | entry edge needed |
|---|---|---|---|---|
| NIFTY | 65 | 0.769 | 15.4 | 25.6 ticks |
| BANKNIFTY | 30 | 1.667 | 33.3 | 55.6 ticks |
| SENSEX | 20 | 2.500 | 50.0 | 83.3 ticks |

The fee is fixed per round trip and does not shrink when the edge does, so this
number is identical at one order a minute and at forty a second. Raising the
rate does not lower the floor. It means paying it more often.

SENSEX is worst because its lot is *smallest* — the fixed fee is spread over
the fewest units. The intuition that a small lot is a cheap lot is backwards.

## 2. You cannot buy trades by accepting smaller edges

Entry threshold swept 16x, rate cap wide open, 75 contracts, 5 draws each:

| spread_frac | orders | net | sd |
|---|---|---|---|
| 0.80 | 240 | +12,854 | 8,418 |
| 0.55 | 247 | +12,831 | 8,622 |
| 0.30 | 255 | +12,692 | 9,373 |
| 0.10 | 257 | +12,662 | 9,335 |
| 0.05 | 257 | +12,662 | 9,335 |

A 16x looser bar bought **7% more orders**. Below 0.20 it saturates completely —
0.10 and 0.05 are identical to the rupee — because `need` is
`max(edge_ticks*tick, spread*spread_frac)` and the tick floor takes over.

Every net difference here is a fraction of its own sd. There is no threshold
effect to find. "More trades, smaller returns" is not a dial this strategy has.

## 3. What actually limits the rate: contracts watched

Signals that fired, 8 virtual seconds, marketable:

| contracts | cap 40/s | cap 1000/s | signals fired | supply |
|---|---|---|---|---|
| 75 | 41 sent | 64 sent | 64 | **8 orders/sec** |
| 246 | 42 sent | 778 sent | 778 | **97 orders/sec** |

At 75 contracts, raising the cap from 200/s to 1000/s changes nothing: supply
is exhausted at 64. The throttle is not the constraint — the number of
contracts being watched is. Reaching 40 orders/sec needs roughly 374 option
contracts across the three indices, about 62 strikes per index counting calls
and puts.

Caveat on the 246-contract number: the simulator applies the same *absolute*
jitter (1.5 ticks) to every contract regardless of moneyness, so deep-OTM
strikes get proportionally enormous mispricings that a real book would not
show. Supply scaling superlinearly with strike count (0.85 signals/contract at
each_side 6 vs 3.16 at each_side 20) is partly that artifact. Treat the 75-
contract figure as the trustworthy one.

## 4. The cap that decides it

Zerodha Kite Connect published limits, checked 2026-09:

| cap | value | vs 40/s |
|---|---|---|
| orders/second (burst) | 10 | 4.0x over |
| orders/minute | 400 | 6.0x over |
| orders/day | 5,000 | **125 seconds of trading** |

The per-minute cap makes the sustainable rate **6.7 orders/sec**, not 10. The
per-second figure is the burst. The daily cap is the one that settles it: at 40
orders/sec the entire day's quota is gone in 125 seconds, and it is per API key
per user, so a second strategy on the same key competes for it.

Other brokers publish higher per-second numbers, but all of them carry
per-minute and per-day caps alongside. 40/s is an exchange-membership rate, not
a retail-API rate.

Separately: SEBI's revised order-to-trade framework (circular 4 Feb 2026)
exempts equity option orders within +/-40% of LTP or +/-Rs20, whichever is
higher, from OTR penalty. Orders at the touch are inside that, so OTR is not
the binding problem here — the broker quota is.

## 5. What 40/s costs before any P&L question

At Rs25 per lot per fill, one lot per order, every order filling:

```
fees          1,000 /sec        60,000 /min
gross needed  1,000 /sec just to break even
```

## 6. The part that is still circular

The P&L in sweeps A–D comes from a simulator that was *told* option quotes lag
10–16ms and then paid for capturing exactly that. It is an assumption with a
number attached, not a measurement. The fee sweep (D) is the only part of it
that means anything, and only as a sensitivity:

| fee/lot/fill | fees | net | fee share of gross |
|---|---|---|---|
| 0 | 0 | +85,096 | 0% |
| 10 | 9,236 | +75,860 | 9% |
| 25 | 23,090 | +62,006 | 22% |
| 34 | 31,402 | +53,693 | 30% |
| 50 | 46,180 | +38,916 | 44% |

Gross per fill is Rs96 and gross per round trip Rs159, so at a Rs34 fee the
fixed cost is already 43% of what a round trip earns. Every step down in edge
quality moves that toward 100% at a rate the order count cannot compensate for,
because the fee scales with order count exactly as fast.

The single measured, non-circular number in this system remains tick-to-signal
latency: **15.6us mean, 100us p99** on the real clock.
