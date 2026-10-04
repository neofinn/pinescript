# Close beyond the prior candle, in that candle's direction — hourly, both sides

The pattern as given:

> If the H1 candle closes red and the next candle closes below its low, go
> short, with the main candle's high as the stop. If it happens with a green
> candle, go long. Take maximum return on both sides.

**This is the first pattern in this repo whose own components demonstrably do
work. It beats its matched random control at the 100th percentile on every cell
tested, the red/green requirement genuinely helps, and a stricter body filter
helps more. It is still a losing strategy: it beat buy-and-hold in 1 of 30
markets, turning 1.00 into 0.887 where holding turned it into 1.689.**

Those two facts are both true and the gap between them is the whole document.

---

## Why this one deserved a real run

Two things separate it from the inside-bar pattern tested earlier, and both are
in its favour:

- **The stop is wide.** Entry is beyond one end of the main candle and the stop
  sits at the other end, so risk is the candle's whole range plus the break.
  The inside-bar pattern failed *because* its stop sat inside ordinary noise.
  This one cannot fail that way.
- **The entry is a close, not a touch.** The confirming candle must close past
  the level, so there is no wick-through-and-reverse fill and no gap-fill
  assumption is needed. Entry is at a price that actually printed.

## Data

30 hourly series, 730 days each, ~262,000 bars: ES NQ YM RTY GC SI CL NG ·
SPX DJI NDX RUT NIFTY SENSEX BANKNIFTY FTSE DAX N225 · SPY QQQ GLD TLT AAPL
NVDA TSLA JPM · EURUSD JPY · BTC ETH.

Costs by vehicle: 1 bp futures and FX, 2 bps indices, 3 bps ETFs and single
names, 10 bps crypto. Exit model, cost handling and the pessimistic tie-break
(a bar touching both stop and target is scored a **loss**) are the same code
every other study in this repo used.

## 1. The pattern as stated — RR 2.0, 24-bar time stop

35,617 trades.

| | n | avg R | PF | win % |
|---|---|---|---|---|
| **SHORT** | 17,660 | **−0.162** | 0.76 | 32.3 |
| **LONG** | 17,957 | **−0.055** | 0.91 | 36.9 |

- markets with a positive short: **0 / 30**
- markets with a positive long: 12 / 30

The short side loses in every market tested. Not one exception out of thirty.

## 2. "Max return both sides" — sweeping target and time stop

| RR | hold | SHORT total R | LONG total R | **combined** |
|---|---|---|---|---|
| 1.0 | 24 | −4,027 | −2,674 | −6,701 |
| 2.0 | 24 | −2,857 | −987 | −3,844 |
| 3.0 | 48 | −2,213 | −65 | −2,278 |
| 5.0 | 48 | −1,900 | +463 | −1,438 |
| **8.0** | **48** | **−1,747** | **+724** | **−1,023** |

**Cells with a positive combined total: 0 / 18.** The maximum is the least
negative, not a profit. Return improves monotonically as the target widens
because the wide-target long converges on simply staying in the market — see §4.

## 3. The ablation, and it goes the other way for once

Every previous pattern in this repo got worse when its defining condition was
kept. This one gets worse when it is **removed**:

| RR | variant | SHORT avg R | LONG avg R | combined total R |
|---|---|---|---|---|
| 1.5 | colour required (the pattern) | **−0.174** | **−0.084** | **−5,003** |
| 1.5 | colour ignored (break only) | −0.249 | −0.157 | −10,166 |
| 2.0 | colour required | **−0.162** | **−0.055** | **−3,844** |
| 2.0 | colour ignored | −0.243 | −0.143 | −8,808 |
| 3.0 | colour required | **−0.153** | **−0.021** | **−2,803** |
| 3.0 | colour ignored | −0.237 | −0.108 | −7,164 |

The red/green condition improves both sides at every target tested, and roughly
halves the loss. Tightening it further helps again:

| filter | SHORT avg R | LONG avg R | combined |
|---|---|---|---|
| any red/green close | −0.162 | −0.055 | −3,844 |
| **body ≥ 50% of range** | **−0.125** | **−0.015** | **−1,691** |

So the idea behind the pattern — break in the direction the prior candle
*committed* to — is real and measurable. It is simply not large enough.

## 4. The control says there is genuine information here

Price-matched random control, 200 draws, pooled across all 30 markets. The
control keeps each setup's shape — trigger and stop as fractions of price — and
places it at a random bar, so trade count, stop distances and firing rate are
all held fixed. Only the alignment with the candle is destroyed.

| side | RR | hold | n | total R | control median | pct |
|---|---|---|---|---|---|---|
| short | 2.0 | 24 | 17,660 | −2,857 | −4,759 | **100** |
| long | 2.0 | 24 | 17,957 | −987 | −3,802 | **100** |
| short | 8.0 | 48 | 11,396 | −1,747 | −3,130 | **100** |
| long | 8.0 | 48 | 10,942 | **+724** | −1,004 | **100** |
| long | 5.0 | 48 | 11,580 | +463 | −1,533 | **100** |

**100th percentile on all five.** This is not a marginal result — the pattern is
far better than placing identically-shaped trades at random bars. There is real
information in it.

And it still loses, in four of those five cells. Beating a random control and
making money are different questions, and this is the cleanest example of the
gap anywhere in this repo.

## 5. Where the positive long came from

The long side only turns positive at RR 8 with a 48-bar hold. At those settings
it is **in the market 72–82% of the time**. That is not a trading strategy; it
is being long with occasional gaps, during two years in which these markets
rose 1–77% a year.

Measured per unit of time exposed against simply holding each market:

**the entry rule beat holding in 9 of 30 markets.** Worse than a coin flip.

## 6. In money, both sides together

Trades from both directions merged in time order, one position at a time, 1% of
live equity risked per trade, compounding, over the same 730 days:

| | strategy | buy-and-hold |
|---|---|---|
| mean across 30 markets | **0.887×** | **1.689×** |
| markets beaten | **1 / 30** | |

Only CL (crude) beat holding. AAPL: 0.584× against 1.91×. NVDA: 0.822× against
5.32×. BTC: 0.213× against 1.37×.

## Why it loses, exactly

At RR 2.0 the pattern wins **32.3%** of the time. A driftless random walk with a
stop at *r* and a target at *2r* resolves in the target's favour **33.3%** of
the time.

The pattern is within one percentage point of a fair coin. That one point is
real — the control and the ablations both confirm it — but it is on the wrong
side of fair, and costs and the ambiguous-bar rule take more than it is worth.
Dropping the colour requirement pushes the win rate further below fair; adding
the body filter pushes it back toward fair. Nothing available moves it past it.

## Verdict

Trade it and you would be taking a bet that is very nearly fair, slightly
against you, roughly 600 times per market per year. The structure is real. The
edge is about one point of win rate in the wrong direction, and the transaction
costs are larger than that.

The honest version of "max return both sides" is that the maximum over 18
target/hold combinations is −1,023R, and that the configuration producing it is
79% invested — at which point the relevant comparison stops being other
strategies and becomes holding, which beat it in 29 of 30 markets.

## Files

- `scripts/break_close.py` — setup generation; reuses the shared exit engine.
- `break_close_h1.pine` — the pattern on a chart, both sides, with the body
  filter exposed as an input since it is the one knob that measurably helped.
