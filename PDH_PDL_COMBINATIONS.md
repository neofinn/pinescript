# Previous-day high / low breaks: every combination

The state space of a session relative to yesterday's range is finite, so it can
be enumerated rather than sampled. 30 markets, **19,761 sessions**, hourly bars
over ~2 years.

**Fading a previous-day break is the clearest loser measured anywhere in this
repo: −0.26 to −0.38 R per trade over ~17,000 trades, and worse than shuffled
data at the 0th percentile. Following a break beats shuffled data at the 100th
percentile — and is still only worth +0.004 R once direction is neutralised.**

---

## 1. Base rates — how a session ends

| state | meaning | share |
|---|---|---|
| **H** | only the previous day's **high** broke | **43.4%** |
| **L** | only the previous day's **low** broke | **34.7%** |
| NONE | neither broke — an inside day | 12.1% |
| HL | high broke first, then the low (failed breakout) | 5.4% |
| LH | low broke first, then the high (failed breakdown) | 4.4% |

Remarkably stable across all 30 markets — NONE ranges 7.4%–19.2%, both-sides
2.1%–8.7%, with no market an outlier.

- **one side breaks and holds: 78.0%**
- both sides taken: 9.8%
- neither: 12.1%

## 2. The causality rule that shapes everything

At the moment PDH breaks you know whether PDL **already** broke today. You do
**not** know whether it will break later.

So "first break" and "second break" are tradeable conditions. "Only one side
broke all day" is a classification that needs the session to end — it can never
be a filter. The H and L states above are base rates only; no strategy here is
allowed to condition on them.

That leaves exactly eight causal combinations: first/second break × high/low
side × follow/fade.

## 3. All eight, pooled over 30 markets

ATR stops so every combination is comparable. RR 0 = hold to the session close.
Best row per combination at a 3×ATR stop:

| combination | n | avg R | PF | win % |
|---|---|---|---|---|
| **1st PDH break → LONG (follow)** | 9,636 | **+0.022** | **1.08** | 49.9 |
| 1st PDL break → SHORT (follow) | 7,732 | −0.007 | 0.97 | 46.0 |
| 2nd PDL after PDH → SHORT | 1,067 | −0.078 | 0.70 | 42.9 |
| 2nd PDH after PDL → SHORT | 879 | −0.139 | 0.52 | 29.5 |
| 2nd PDH after PDL → LONG | 879 | −0.144 | 0.54 | 41.8 |
| 2nd PDL after PDH → LONG | 1,067 | −0.251 | 0.26 | 23.7 |
| **1st PDL break → LONG (fade)** | 7,732 | **−0.275** | 0.33 | 30.2 |
| **1st PDH break → SHORT (fade)** | 9,636 | **−0.258** | 0.36 | 29.2 |

**96 cells tested, 4 with positive average R.** All four are the PDH-follow-long
at a wide stop.

Two structures are visible and both are large:

- **Follow beats fade by roughly 0.28 R per trade**, at every stop width and
  every target, in both directions. Over ~17,000 fade trades there is no stop
  or target that rescues it.
- **Second breaks do not reverse.** Taking the failed-breakdown long (2nd PDH
  after PDL) returns −0.144; the trades conventionally described as "trap"
  reversals are the worst cells in the table.

Wider stops improve everything monotonically: PDH-follow goes −0.042 at 1×ATR
→ +0.001 at 2× → +0.022 at 3×.

## 4. Why fading loses, in one number

19,761 sessions; 17,370 broke at least one side (87.9%). Of those, both sides
were taken in 1,939 — **11.2%**.

**Once a level breaks, the opposite level is reached 11.2% of the time.** Fading
a break is a bet on that 11.2%. The measurement simply confirms the arithmetic.

## 5. The shuffle control — the path is real

Bars are reordered **within** each session. The session's high, low and close
are unchanged, so PDH and PDL are identical; only the order in which price
visits them is destroyed. 30 shuffles across all 30 markets:

| combination | real | shuffled median | shuffled best of 30 | pct |
|---|---|---|---|---|
| 1st PDH break → LONG (follow) | **+0.022** | −0.133 | −0.128 | **100** |
| 1st PDH break → SHORT (fade) | **−0.258** | −0.150 | −0.145 | **0** |

The follow trade beats **every one of 30 shuffles**, by +0.155 R over the best
of them. The fade is worse than every shuffle.

So the sequence genuinely carries information, and what it says is
*continuation*. This is not a marginal statistical artefact — it is the
strongest path-dependence result in this repo.

## 6. And it is still fully priced

| | mean avg R | positive in |
|---|---|---|
| 1st PDH break → LONG | +0.021 | 19 / 30 markets |
| 1st PDL break → SHORT | −0.012 | 16 / 30 markets |
| **average of the two (direction-neutral)** | **+0.004** | |

The correlation between each market's (long − short) gap and its own drift is
only **+0.114**, so the asymmetry is not cleanly explained by drift either — it
is mostly a small long bias plus noise.

**Direction-neutral, the pattern is worth +0.004 R per trade.** Real information,
no money in it: the market has priced the continuation tendency to within half a
basis point of a 3-ATR risk unit.

## Verdict

- **Never fade a previous-day high or low break.** −0.26 to −0.38 R per trade
  across ~17,000 trades, 0th percentile against shuffled data, and the base rate
  says you are betting on an 11.2% outcome. This is the single most strongly
  negative result in this repo.
- **Never take the second break as a reversal.** All four second-break
  combinations are negative; the "trap reversal" long is −0.144 and the worst
  cell in the table.
- **Following a break is approximately free.** Beats shuffled data decisively,
  which means the continuation tendency is real — and nets +0.004 R once
  direction is neutralised, which means it is already in the price.
- If you trade it at all, use a **wide stop (3×ATR) and hold to the session
  close**, which was the best of 96 cells at +0.022 R and PF 1.08.

The useful output of this study is the base-rate table in §1 and the 11.2% in
§4, not a strategy.

## Files

- `scripts/pdh_pdl_combos.py` — state classification, the eight combinations,
  and a guard that refuses the stop placement which made every fade lose
  exactly 1R (the opposite level is the fade's target, not its stop).
