# VWAP + supply/demand confluence

Added both layers to the profile+flow plans and tested them the same way as
everything else: 5% compounding stop, the full 160-cell grid per gate, and a
random control **matched to each gate's own trade count**.

## The threshold is the result

The first version of this script admitted any cell with 8+ trades. The H1
baseline winner then came back as a **9-trade cell reading 51.89×**, against
31.16× for the 35-trade cell a stricter run had found. Raising the floor to 20
trades removed it.

A gate that leaves eight trades has not been tested, it has been described.

## M5 — 59 sessions

| gate | best plan | n | kept | final | × | maxDD | vs random |
|---|---|---|---|---|---|---|---|
| none | delta_breakout | 46 | 100% | ₹16,62,614 | 3.33 | 27.8% | **0th** |
| **vwap_trend** | delta_breakout | 46 | **100%** | ₹16,62,614 | 3.33 | 27.8% | 0th |
| vwap_revert | lvn_delta_traverse | 23 | 50% | ₹4,61,051 | **0.92** | 15.0% | 0th |
| **zone** | delta_breakout | 48 | 104% | **₹19,07,358** | **3.81** | 26.1% | **33rd** |
| vwap+zone | delta_breakout | 48 | 104% | ₹19,07,358 | 3.81 | 26.1% | 0th |

## H1 — all of 2026

| gate | best plan | n | kept | final | × | maxDD | vs random |
|---|---|---|---|---|---|---|---|
| none | delta_breakout | 35 | 100% | ₹1,55,79,726 | 31.16 | 33.2% | 0th |
| **vwap_trend** | delta_breakout | 35 | **100%** | ₹1,55,79,726 | 31.16 | 33.2% | 0th |
| vwap_revert | cvd_divergence | 21 | 60% | ₹9,97,641 | 2.00 | 48.7% | 0th |
| zone | delta_breakout | 32 | 91% | ₹1,30,66,671 | 26.13 | 33.4% | 0th |
| vwap+zone | delta_breakout | 32 | 91% | ₹1,30,66,671 | 26.13 | 33.4% | 0th |

## VWAP adds nothing, and the reason is structural

`vwap_trend` produced an **identical trade count and an identical equity curve**
on both windows. That is not a coding failure — it is redundancy, and it can be
measured directly:

| plan | signals | already agree with VWAP |
|---|---|---|
| **delta_breakout** (M5) | 449 | **449 — 100%** |
| **delta_breakout** (H1) | 61 | **61 — 100%** |
| naked_poc_flow (M5) | 345 | 345 — 100% |
| dva_edge_fade (M5) | 680 | 56 — 8.2% |
| cvd_divergence (M5) | 374 | 2 — **0.5%** |

`delta_breakout` fires on a close above the **developing value-area high** with
cumulative delta at a session extreme. VWAP is a volume-weighted mean and sits
*inside* the value area, so a close above the VAH is above VWAP by
construction. The gate can never remove a trade.

The mirror case is `cvd_divergence`, which fades new extremes and therefore
agrees with VWAP on 0.5% of its signals — a VWAP-trend filter would delete it
almost entirely.

**Adding VWAP to a volume-profile breakout is adding a coarser version of a
measurement the profile already contains.** If you want VWAP to do work, it has
to be paired with a signal that is not already a profile-location signal.

## Supply/demand is the only layer that moved anything

The `zone` gate — requiring room to the target before the nearest live opposing
zone — is the one gate that improved M5: 3.33× → **3.81×**, and the only cell in
the entire table to rise off the floor against its control, from the 0th to the
**33rd percentile**. On H1 it slightly hurt (31.16× → 26.13×).

It also *raised* the trade count to 104%, which looks impossible for a filter
and is not: removing an early signal frees the engine to take a later one that
was previously blocked by an open position. Filters change which trades happen,
not only how many.

## Fading VWAP is decisively worse than trading with it

`vwap_revert` is the worst gate in both windows — **0.92× on M5** (a loss) and
2.00× on H1 against 31.16× ungated. Whatever these signals have, it is not
mean-reversion against the session mean.

## The verdict

Nothing here clears its control. The best cell in the study — supply/demand
gated, M5 — sits at the **33rd percentile** of what random reaches under the
same search, and every other cell sits at the 0th. Random's median is ₹27–71
lakh on M5 and ₹81–811 crore on H1.

Two things are worth keeping regardless:

1. **VWAP is redundant with volume-profile location, provably**, at 100% overlap
   on the winning plan. That is a reason to drop it from the stack rather than a
   reason to tune it.
2. **Supply/demand room is the only added layer that did anything**, and the
   effect was small, one-sided across windows, and still short of the control.

```
python3 scripts/vwap_zone_confluence.py <data-dir> 0.05
```
