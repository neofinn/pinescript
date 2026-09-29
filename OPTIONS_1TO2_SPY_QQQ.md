# SPY + QQQ, bought options, 1:2 RR, $100k

Ran the profile+flow setups plus Part 1's best profile signal as **bought
options** on SPY and QQQ. Stop from the profile structure, target at **twice
the stop distance on the underlying**, $100,000 starting balance, 1% risk
per trade.

> "SKY" read as **SPY**. SKY is Champion Homes, a small-cap whose options
> chain is too thin for this test to mean anything. Say so if you meant it.

## What is real here and what is assumed

| | source |
|---|---|
| implied vol | **VIX for SPY, VXN for QQQ**, daily close over the window |
| expiry | SPY/QQQ list daily expiries; 0DTE = that session's 20:00 UTC close |
| option price | Black-Scholes **revalued** at exit spot and exit clock |
| strike | nearest $1 strike to the target delta |
| cost | $0.02 spread + $0.65/contract, both ways |
| sizing | ex-ante: contracts set from the modelled loss at the stop |

VIX and VXN are **30-day** implied vols being used to price **same-day**
options. That is wrong in a direction I cannot pin down, so it is swept rather
than asserted — and the sweep turns out to decide the whole result.

## Headline

| setup | n | PF | win% | net $ | final $ | maxDD | median | opt RR | ctl95 | pct |
|---|---|---|---|---|---|---|---|---|---|---|
| **dva_edge_fade** | 527 | 1.162 | 33.2 | **+46,031** | 146,031 | 21.0% | −693 | 2.34 | 1.23 | 90.5 |
| naked_poc_flow | 174 | 1.506 | 33.9 | **+44,059** | 144,059 | 17.8% | −584 | 2.94 | 2.40 | 55.0 |
| delta_breakout | 356 | 0.929 | 29.8 | −13,949 | 86,051 | 42.8% | −654 | 2.19 | 1.67 | 14.5 |
| cvd_divergence | 577 | 0.913 | 30.3 | −25,800 | 74,200 | 46.3% | −603 | 2.10 | 1.18 | 47.5 |
| lvn_delta_traverse | 319 | 0.739 | 27.6 | −37,945 | 62,055 | 43.9% | −529 | 1.94 | 1.03 | 51.5 |
| absorption_at_edge | 302 | 0.690 | 30.1 | −38,357 | 61,643 | 40.0% | −509 | 1.60 | 0.95 | 57.5 |

Two make money. **Neither clears its control.** `dva_edge_fade` reaches the
90.5th percentile, short of 95. `naked_poc_flow` looks better on profit factor
and is worse on evidence — random entries with the same stop distances reach
**PF 2.40** at its trade count, against its 1.506, so it sits at the 55th
percentile. That gap is the whole reason this project scores against a control:
174 trades is not enough for 1.5 to mean anything.

**The median trade loses money in every row**, −$509 to −$693. This is a
lottery-ticket distribution: a third of trades win, and they have to be big
enough to carry the other two thirds.

## A 1:2 on the index is not a 1:2 on the option

The intended ratio is 2.0. The realised dollar ratio is 1.60 to 2.94. Gamma
makes the winners bigger than delta predicts, and the effect is strongest where
gamma is largest:

| DTE | target hit → option | stopped → option | realised $ RR |
|---|---|---|---|
| **0** | **+64.9%** | −32.2% | **2.34** |
| 1 | +18.7% | −9.8% | 1.53 |
| 5 | +7.9% | −4.4% | 1.60 |

At 0DTE the option preserves the 2:1 the underlying trade was designed to have.
At 1DTE the same index move moves the option a fifth as far, and the payoff
ratio collapses to 1.5 — which is below what the strategy needs at a 33% hit
rate. **This is not a position-sizing artefact**: quantity stays at 20–24
contracts and mean intended risk at $959–973 across every DTE, with an
identical exit mix (65% stop, 32% target, 1% bell). It is the payoff shape.

| DTE | net $ (dva_edge_fade) |
|---|---|
| 0 | +46,031 |
| 1 | **−118,114** |
| 2 | −86,358 |
| 5 | −58,333 |

If you buy options on this, buy same-day. Anything longer needs a different
target, not a different size.

## The assumption that decides it

| iv multiplier | 0.70 | 0.85 | **1.00** | 1.25 | 1.50 |
|---|---|---|---|---|---|
| dva_edge_fade | +79,080 | +35,236 | **+46,031** | **−6,025** | −41,940 |
| cvd_divergence | +39,985 | +3,497 | −25,800 | −59,206 | −84,041 |
| delta_breakout | +34,098 | +6,406 | −13,949 | −38,255 | −58,019 |
| naked_poc_flow | +93,641 | +63,116 | +44,059 | +20,618 | **+4,159** |

**`dva_edge_fade` flips sign at 1.25×.** Real 0DTE at-the-money IV runs below
the 30-day VIX on quiet days and well above it around events, so 1.25× is not
a stress case — it is inside the plausible range. The +$46k is a statement
about the IV assumption at least as much as about the signal.

`naked_poc_flow` is the only setup positive at every multiplier, which is the
one point in its favour. It still does not beat its control.

Spreads say the same thing:

| spread | $0.01 | **$0.02** | $0.05 | $0.10 |
|---|---|---|---|---|
| dva_edge_fade | +66,021 | **+46,031** | +151 | −55,809 |
| naked_poc_flow | +49,039 | +44,059 | +28,606 | +10,954 |

At a nickel, `dva_edge_fade` is exactly flat. SPY 0DTE at-the-money really does
quote a penny or two; QQQ is wider. There is no margin for a worse fill.

Delta is the one axis that behaves well — 0.40 best for `dva_edge_fade`
(+$71,189), 0.30 for `naked_poc_flow` (+$58,578), degrading smoothly either
side rather than spiking.

## Sized to lose $1,000

| setup | mean loss | sd | p90 | worst | >2× intended |
|---|---|---|---|---|---|
| dva_edge_fade | $806 | $231 | $1,021 | $2,225 | 1% |
| naked_poc_flow | $757 | $254 | $1,043 | $1,421 | 0% |
| cvd_divergence | $738 | $252 | $978 | $2,362 | 0% |

Sizing an option position to lose a fixed amount does not make it lose that
amount. The mean comes in under target because many trades exit at the bell
part-way to the stop; the worst case runs to 2.2× because a gap through the
stop is filled at the gap, not at the level.

## The thing that matters most

`dva_edge_fade` is the signal from Part 1 that **failed the universe swap** —
strong on the ten largest US names, absent on the next ten over identical
dates. SPY and QQQ are two of the ten it worked on. So this $46k is the same
basket-specific result as before, now leveraged through options, and options
leverage a result whether or not it is real.

Nothing here changes the Part 1 verdict. What it does add is a clean measure of
what option buying does to a marginal edge: at 0DTE convexity preserves the
payoff ratio the underlying plan wanted, and simultaneously makes the outcome
hostage to an implied-vol number you do not observe and a spread you do not
control. A signal at the 90th percentile of its control becomes a −$42k account
at 1.5× IV.

Reproduce:

```
python3 scripts/vp_options.py <bars-dir> <vol-dir>         # the table
python3 scripts/vp_options.py <bars-dir> <vol-dir> sweep   # risk + sweeps
```
