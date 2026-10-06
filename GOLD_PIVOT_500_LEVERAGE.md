# Gold: pivots + 9 EMA at max RR, on $500 at 1:1000

Two questions, and they have independent answers.

**The strategy is the best-validated result in this repo**: pivot-P break with the
9 EMA returns **+0.373 R per trade** over 317 trades, is **direction-neutral**
(shorts profit in a market rising 26.6%/yr), beats **every one of 40 shuffles**,
and is positive in **both halves** of the sample.

**The 1:1000 leverage is irrelevant and dangerous.** At every risk setting that
survives, the strategy uses 7× to 34× leverage — between 0.7% and 3.4% of what
1:1000 allows. The leverage never binds. It only removes the broker's refusal to
let you take the size that destroys the account.

---

## Part 1 — the strategy

GC=F hourly, 13,722 bars, 733 sessions (2024-05 → 2026-10). Cost 0.8 bps round
turn (~$0.33/oz: $0.25 spread + $0.07 commission). 168 testable cells swept,
**53 positive**.

### Max RR, and what it actually means

| RR | n | hit target | stopped | closed out | avg R | win % |
|---|---|---|---|---|---|---|
| 1 | 317 | 51.7% | 43.8% | 4.4% | +0.043 | 53.6 |
| 2 | 317 | 37.2% | 53.9% | 8.8% | +0.186 | 42.0 |
| 5 | 317 | 11.7% | 62.1% | 26.2% | +0.283 | 32.5 |
| 8 | 317 | 3.8% | 63.1% | 33.1% | +0.303 | 31.5 |
| **20** | 317 | **0.3%** | 63.1% | 36.6% | **+0.373** | 31.5 |

Average R rises monotonically with RR, and the reason is not that distant
targets get hit — at RR 20 the target is reached **0.3%** of the time.
**"Max RR" is not a wider target; it is "remove the target and hold to the
session close with a stop."** That is a trend-following rule and must be judged
as one.

Best cell: **P, break, EMA-aligned, RR 20 → +0.373 R, n=317, PF 1.56.**

By level group (best EMA/mode at each RR):

| levels | RR 1 | RR 2 | RR 5 | RR 12 | RR 20 |
|---|---|---|---|---|---|
| **P** | 0.046 | 0.192 | 0.283 | 0.354 | **0.373** |
| R1/S1 | 0.005 | 0.098 | 0.181 | 0.190 | 0.211 |
| R2/S2 | −0.027 | 0.018 | −0.017 | −0.087 | −0.060 |
| R3/S3 | −0.032 | −0.051 | −0.023 | −0.068 | −0.068 |

Note this **inverts the NIFTY result**, where bounce-against-the-EMA won and P
break did not. On gold the pivot is a trend level; on NIFTY the outer levels
were reversion levels.

### The three validations it passes

**Not drift.** Gold rose 26.6%/yr over the sample, so a long bias would be
suspicious:

| | n | avg R |
|---|---|---|
| long | 150 | +0.547 |
| **short** | 167 | **+0.217** |
| **direction-neutral** | | **+0.382** |

Shorts are solidly profitable in a strongly rising market. This is not drift.

**Shuffle control** — bars reordered within each session, pivots untouched
(they come from the previous session), 40 draws:

| | real | shuffled median | shuffled best | pct |
|---|---|---|---|---|
| RR 2 | +0.186 | −0.899 | −0.804 | **100** |
| RR 20 | **+0.373** | −0.967 | −0.894 | **100** |

The real sequence beats the best of 40 shuffles by **+1.27 R**. The widest
margin measured anywhere in this repo.

**Split-half:** RR 20 gives +0.496 / +0.262; RR 2 gives +0.208 / +0.165. Both
halves positive at both targets.

168 cells were searched, so the ranking alone would prove nothing — but these
three checks are independent of the search, which is why this one is credible
where the NIFTY equivalent was not.

## Part 2 — $500 at 1:1000

### The arithmetic, before any backtest

$500 × 1000 = **$500,000 notional** = 120 oz = **1.20 lots**. At that size $1 of
gold movement is $120, so **the account is gone on a $4.17 move**. Gold's
hourly range is routinely three to five times that.

### The floor you cannot go below

Median stop distance: **$11.03/oz** (0.30% of price).

The smallest position a retail broker accepts is **0.01 lots = 1 ounce**. At the
median stop that minimum position risks **$11.03 — 2.2% of a $500 account.**

**So 2.2% per trade is the floor.** Any smaller risk setting is unreachable; the
broker rounds up to it. A $500 account is structurally forced into a risk level
most risk management would call aggressive, before any choice is made.

### What actually survives

| risk/trade | final $ | max DD | ruin rate | 5th pct | median $ |
|---|---|---|---|---|---|
| **2.2%** (the floor) | 4,487 | 62.6% | **1.7%** | 3,180 | 4,831 |
| 5.0% | **17,273** | 90.4% | 4.4% | 7,480 | 17,052 |
| 10.0% | 15,639 | **99.5%** | 17.3% | 0 | 18,271 |
| 20.0% | **0** | 100% | **90.7%** | 0 | 0 |
| 50.0% | **0** | 100% | **100%** | 0 | 0 |

Ruin rates are from 1,000 reshufflings of the same 317 trades — identical
statistics, only the order changed. At 20% risk the strategy's own edge is
intact and the account still dies in 90.7% of orderings.

Note that even the "survivable" rows are brutal: 5% risk turns $500 into
$17,273 but with a **90.4% drawdown** along the way. That is $500 → $48 before
it recovers. Almost nobody holds through that.

### The leverage never binds

| risk/trade | lots | notional | **leverage used** | % of 1:1000 allowed |
|---|---|---|---|---|
| 2.2% | 0.01 | $3,408 | **6.8×** | 0.7% |
| 5.0% | 0.02 | $6,817 | **13.6×** | 1.4% |
| 10.0% | 0.05 | $17,042 | **34.1×** | 3.4% |
| 20.0% | 0.09 | $30,675 | 61.3× | 6.1% |
| 50.0% | 0.23 | $78,391 | 156.8× | 15.7% |

**Every survivable setting uses under 35× leverage — under 3.5% of the 1:1000
allowance.** 1:1000 is between one and two orders of magnitude more than this
strategy ever asks for.

Leverage is not a strategy input. The stop distance and the risk fraction set
the position; leverage only determines whether the broker *permits* it. 1:1000
adds nothing at survivable sizes and removes the only mechanical brake at
dangerous ones.

## Verdict

- **The edge is real** and better validated than anything else here: +0.373 R,
  direction-neutral, 100th percentile against shuffles, positive in both halves.
- **Max RR means "no target, hold to the close with a stop."** The 20R label is
  misleading — the target fills 0.3% of the time.
- **Use 1:100 or less.** The strategy needs at most 34×. Taking 1:1000 changes
  nothing you want and enables everything you don't.
- **Risk 2.2% because you cannot risk less**, not because it is optimal. On
  $500 the broker's 0.01-lot minimum sets the floor.
- **$500 is a test account, not a trading account.** The expected path at the
  floor is $500 → ~$4,500 over 2.4 years with a 63% drawdown. Everything scales
  linearly with capital — including the drawdown.

## Files

- `scripts/pivot_ema.py` — trade records now carry entry, stop and per-unit risk
  so position sizing can be derived from the real stop distance.
- `scripts/gold_leverage_run.py` — the sizing, margin and ruin simulation.
