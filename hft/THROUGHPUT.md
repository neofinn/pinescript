# 40 orders per second, on an exchange-member seat with zero brokerage

Measured with `HFT_VIRTUAL_CLOCK=1 python -m hft.rate_lab`. Raw output in
`rate_sweep_output.txt`.

## What changed when the seat changed

An earlier pass of this document assumed a retail customer API and a flat Rs25
per lot per fill. Both were wrong for this setup, and they were wrong in
different ways — one was a level, the other was a *shape*.

| | retail assumption | exchange member, zero brokerage |
|---|---|---|
| cost model | Rs25/lot/fill, flat | 0.2383% of premium (NSE), 0.2311% (BSE) |
| NIFTY lot @ 150 premium | Rs50 round trip | **Rs23.23 round trip** |
| worst contract | SENSEX (smallest lot) | the **most expensive** option, any lot |
| order rate cap | 10/s, 400/min, 5,000/day | member session rate, per your agreement |

The flat fee made lot size decisive: a fixed charge spread over 20 units hurts
more than over 65, so SENSEX looked structurally worst. A proportional charge
makes lot size **drop out of the arithmetic entirely**. What decides the hurdle
now is how expensive the option is — and that is a choice you make, not a
constant you inherit.

## The cost that survives zero brokerage

One NIFTY lot (65) at premium 150, round trip:

| item | Rs | share |
|---|---|---|
| STT (0.15%, sell leg) | 14.62 | **63.0%** |
| exchange txn (0.03553% x2) | 6.93 | 29.8% |
| GST 18% | 1.27 | 5.5% |
| stamp duty (0.003%, buy leg) | 0.29 | 1.3% |
| IPFT | 0.10 | 0.4% |
| SEBI turnover | 0.02 | 0.1% |
| brokerage | 0.00 | 0% |
| **total** | **23.23** | |

Zero brokerage removed the flat part. The part that scales with size is
untouched, and STT is 63% of it. STT on option sales went 0.0625% → 0.10% on
2024-10-01 and 0.10% → **0.15%** on 2026-04-01; NSE added Rs300/crore to the
options transaction charge on 2026-03-01. These rates move — check `costs.py`
against your own contract notes before trusting anything downstream of it.

## The floor, in ticks

`breakeven_ticks = 0.2383% x premium / 0.05`

| premium | break-even ticks | typical of |
|---|---|---|
| 10 | 0.48 | far OTM weekly |
| 50 | 2.38 | OTM |
| 100 | 4.77 | NIFTY near-ATM |
| 150 | 7.15 | NIFTY ATM weekly |
| 250 | 11.91 | |
| 400 | 19.06 | BANKNIFTY ATM |
| 500 | 23.83 | SENSEX ATM |

## 1. 40 orders/sec is already there

Order supply vs contracts watched, rate cap held non-binding, 3 draws each:

| each_side | contracts | orders/sec | per contract |
|---|---|---|---|
| 2 | 30 | 21.8 | 0.73 |
| 4 | 54 | 28.6 | 0.53 |
| 6 | **78** | **42.7** | 0.55 |
| 10 | 126 | 59.6 | 0.47 |
| 14 | 174 | 111.5 | 0.64 |
| 20 | 246 | 139.8 | 0.57 |

Roughly 0.55 orders/sec per contract, near enough linear. **40/sec needs about
75 contracts — what `each_side=6` already watches.** With the broker quota gone
there is nothing left to raise.

> Correction: an earlier pass put this at 0.107 orders/sec/contract and claimed
> 374 contracts were needed. That came from a side probe, not from the driver
> the sweeps use, and it under-counted about 4x. The table above is from
> `run_det`, the same code path as every other number here.

## 2. Lowering the entry bar still does nothing

Threshold swept 16x (`spread_frac` 0.80 → 0.05), cap wide open, 5 draws:

| bar | orders | gross | costs | net | sd |
|---|---|---|---|---|---|
| 0.80 | 240 | +20,304 | 3,651 | +16,653 | 9,936 |
| 0.55 | 247 | +20,516 | 3,834 | +16,682 | 10,118 |
| 0.30 | 255 | +20,597 | 3,883 | +16,714 | 10,887 |
| 0.10 | 257 | +20,652 | 3,919 | +16,733 | 10,806 |
| 0.05 | 257 | +20,652 | 3,919 | +16,733 | 10,806 |

7% more orders for a 16x looser bar, and it saturates to the rupee below 0.20
because `need` is `max(edge_ticks*tick, spread*spread_frac)` and the tick floor
takes over. Every net difference is a fraction of its own sd. Unchanged by the
new cost model — this was never a cost effect.

## 3. Premium band is the lever that does work

All bands at cap 1000/s, `each_side=20`, 5 draws. Contract counts differ per
band, so **net per contract watched** is the comparable column, not net:

| premium band | contracts | orders | gross | costs | net | cost % of gross | net/contract |
|---|---|---|---|---|---|---|---|
| 0–25 | 63 | 128 | +1,052 | 91 | +960 | 10% | 15 |
| 25–60 | 20 | 78 | +2,073 | 209 | +1,865 | 9% | 93 |
| 60–120 | 17 | 64 | +3,549 | 405 | +3,144 | 10% | 185 |
| **120–250** | 25 | 118 | +11,730 | 1,473 | **+10,257** | **10%** | **410** |
| 250+ | 121 | 424 | +59,212 | 18,182 | +41,030 | **31%** | 339 |
| all | 246 | 779 | +88,405 | 20,214 | +68,191 | 19% | 277 |

Cost is a flat ~10% of gross everywhere below Rs250 of premium and jumps to
**31%** above it. That is the arithmetic showing through: cost scales linearly
with premium while the lag edge, measured in ticks, does not. The 120–250 band
returns the most per contract watched.

This is also where `each_side=20` goes wrong. Widening the strike range pulls
in deep-ITM contracts at Rs500+ premium (sweep C, 246 contracts: mean premium
498, gross +1,138 against costs 1,105 — the trade barely clears its own STT).
Breadth is not free once cost is proportional: **the right 78 contracts beat
the wrong 246.**

## 4. What is still live at member level

- **Order-to-trade ratio** penalties fall on the member. SEBI's 2026-02-04
  revision exempts option orders within ±40% of LTP or ±Rs20, whichever is
  higher, so orders at the touch are outside the framework. A passive book that
  cancels most of what it quotes is the case to check — not this one.
- Every algo needs its exchange-approved unique identifier.
- NSE sets a message rate **per session per member**; colocation LAN sessions
  get the configured rate +10%. That figure is in your connectivity agreement.
  I could not find a public number and have not assumed one.

## 5. What is still circular

The gross in every table above comes from a simulator that was *told* option
quotes lag 10–16ms, and then paid for capturing exactly that. The cost side is
now real; the revenue side is an assumption with a number attached.

The measured, non-circular numbers remain:

- tick-to-signal latency **15.6us mean, 100us p99** (real clock)
- order supply **0.55/sec per contract watched**
- the cost stack, which is arithmetic over published rates

## 6. The determinism fix this all depends on

Every timing decision reads `clock.now_ns`. Under a real clock, six runs with
identical config and identical seeds gave net +6,138 / +2,218 / +2,564 / +2,564
/ +2,955 / +1,309 — sd 1,511 on a mean of 2,958, a 4.7x spread from scheduler
jitter alone. A first pass "found" a threshold optimum at `spread_frac 0.30`;
it was noise, and it does not exist under a deterministic clock.

`HFT_VIRTUAL_CLOCK=1` binds `now_ns` to a clock the driver advances. Runs are
bit-reproducible. Run *without* it when measuring latency — `real_ns` is
untouched.
