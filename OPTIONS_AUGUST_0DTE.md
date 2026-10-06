# August 2026, 0DTE daily expiry — SPY, QQQ, E-mini

Same engine as `OPTIONS_1TO2_SPY_QQQ.md`, narrowed to **0DTE only**, **August
only**, with **ES** added. 1:2 on the underlying, $100,000, 1% risk.

**Sample warning first.** 21 sessions. Trade counts run 75 to 299 across all
three instruments — `naked_poc_flow` gets 22–27 trades *per instrument*. At
that size a random control with the same stop distances reaches **PF 2.69**, so
a profit factor under about 2.7 on this window means nothing on its own. One
month is a weaker test than anything else in this repo, and the numbers below
should be read that way.

## Contract terms, which are not cosmetic

| | multiplier | strikes | ATM 0DTE spread | commission |
|---|---|---|---|---|
| SPY | $100/pt | $1 | $0.02 | $0.65/side |
| QQQ | $100/pt | $1 | $0.02 | $0.65/side |
| **ES** | **$50/pt** | **5 pt** | **0.25 pt** | $1.25/side |

An ES round trip costs **$12.50 a contract against SPY's $2**. Running ES on
SPY's cost assumptions would have flattered it about six-fold, so it gets its
own.

## August result

| setup | n | PF | win% | net $ | final $ | maxDD | median | optRR | ctl95 | pct |
|---|---|---|---|---|---|---|---|---|---|---|
| **naked_poc_flow** | 75 | 1.372 | 32.0 | **+13,811** | 113,811 | 10.8% | −550 | 2.91 | 2.69 | 57.5 |
| delta_breakout | 222 | 0.905 | 33.3 | −10,324 | 89,676 | 32.8% | −603 | 1.81 | 1.49 | 47.5 |
| dva_edge_fade | 298 | 0.892 | 30.2 | −18,612 | 81,388 | 37.4% | −717 | 2.06 | 1.24 | 60.0 |
| absorption_at_edge | 166 | 0.562 | 30.7 | −31,137 | 68,863 | 31.1% | −533 | 1.27 | 1.08 | 37.0 |
| lvn_delta_traverse | 169 | 0.565 | 26.6 | −33,235 | 66,765 | 33.9% | −507 | 1.56 | 1.10 | 30.5 |
| **cvd_divergence** | 299 | 0.484 | 24.1 | **−87,120** | 12,880 | **90.7%** | −656 | 1.53 | 1.29 | 2.0 |

**One of six makes money, and it does not clear its control** — PF 1.372
against a 95th percentile of 2.69 puts it at the 57.5th percentile.

`cvd_divergence` takes the account from $100,000 to **$12,880**. At a 90.7%
drawdown, fixed $1,000 risk is fiction — you cannot risk 1% of your opening
balance when 87% of it is gone. Sizing at 1% of *live* equity instead:

| setup | fixed final | fixed DD | scaled final | scaled DD |
|---|---|---|---|---|
| naked_poc_flow | 113,811 | 10.8% | **113,789** | 12.8% |
| delta_breakout | 89,676 | 32.8% | 89,068 | 35.6% |
| dva_edge_fade | 81,388 | 37.4% | 78,802 | 38.4% |
| lvn_delta_traverse | 66,765 | 33.9% | 71,258 | 28.9% |
| cvd_divergence | 12,880 | 90.7% | **41,295** | 60.1% |

Scaling rescues the disaster case and changes nothing else, which is what it
should do.

## Per instrument — and ES is the worst of the three

| setup | SPY n | SPY $ | QQQ n | QQQ $ | ES n | ES $ |
|---|---|---|---|---|---|---|
| dva_edge_fade | 106 | −3,664 | 94 | −1,100 | 98 | **−13,848** |
| cvd_divergence | 102 | −41,557 | 92 | −11,194 | 105 | −34,369 |
| delta_breakout | 75 | −6,230 | 71 | −8,613 | 76 | **+4,518** |
| naked_poc_flow | 22 | +7,935 | 27 | +1,159 | 26 | +4,718 |
| absorption_at_edge | 63 | −18,202 | 46 | −2,645 | 57 | −10,290 |
| lvn_delta_traverse | 56 | −15,019 | 62 | −10,417 | 51 | −7,799 |

ES contributes three quarters of `dva_edge_fade`'s August loss on a third of
the trades. That is the cost structure doing it: a quarter-point spread on a
$50 multiplier is roughly six times SPY's drag per unit of risk, and these
setups have no margin to absorb it.

## The part worth knowing more than the August table

August is the month the previous run's winner *lost*:

| setup | Jul | Aug | Sep | Jul–Sep |
|---|---|---|---|---|
| **dva_edge_fade** | **+42,471** | **−18,612** | **+54,116** | +77,974 |
| naked_poc_flow | +7,318 | +13,811 | +11,109 | +32,237 |
| cvd_divergence | +16,547 | −87,120 | +2,347 | −68,226 |
| delta_breakout | −5,786 | −10,324 | −6,850 | −22,960 |
| lvn_delta_traverse | −7,272 | −33,235 | −5,746 | −46,253 |
| absorption_at_edge | −3,728 | −31,137 | −31,163 | −66,028 |

The $46k I reported last round on SPY+QQQ was **July and September carrying a
losing August**. On the same pair alone: +19,527 / −4,764 / +35,633. A single
month can flip a three-month result, which is the same lesson the universe swap
gave — a good aggregate is not a stable one.

`naked_poc_flow` is the only setup positive in **all three months**. That is
genuinely more than the others have, and it is still 22–27 trades a month
against a control that reaches 2.69.

## Assumptions, swept on the August window

| iv multiplier | 0.70 | 0.85 | **1.00** | 1.25 | 1.50 |
|---|---|---|---|---|---|
| naked_poc_flow | +33,577 | +23,281 | **+13,811** | +5,734 | −1,293 |
| dva_edge_fade | −15,252 | −34,875 | −18,612 | −47,269 | −66,315 |
| cvd_divergence | −69,361 | −80,256 | −87,120 | −95,546 | −104,114 |

| spread multiple | 0.5× | **1×** | 2× | 4× |
|---|---|---|---|---|
| naked_poc_flow | +15,101 | **+13,811** | +8,975 | +3,581 |
| dva_edge_fade | −9,106 | −18,612 | −41,040 | −68,104 |

`dva_edge_fade` is negative at **every** IV multiplier, **every** delta and
**every** spread in August — the sign does not depend on the assumptions here,
it is simply a losing month. `naked_poc_flow` stays positive until IV is 1.5×
or spreads are quadrupled, which is the most robust cell this project has
produced, on the smallest sample.

## Verdict

For the window you asked about, buying 0DTE on these setups across SPY, QQQ and
ES loses money in five of six cases, and the sixth is not separable from chance
at 75 trades. The one thing worth carrying forward is that `naked_poc_flow` is
positive in July, August and September and across the assumption sweeps — which
makes it worth a **larger sample**, not worth trading yet.

The obvious next test is `naked_poc_flow` over the full window on the ten names
that *failed* the Part 1 universe swap. If it holds there, it is the first
thing in this project that has.

```
python3 scripts/vp_options.py <bars-dir> <vol-dir> 2026 8         # August
python3 scripts/vp_options.py <bars-dir> <vol-dir> 2026 8 sweep   # + sweeps
```
