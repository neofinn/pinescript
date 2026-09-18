# EMA + VWAP cross, tested

SPY, Yahoo. **5m: 3,277 bars, 2026-07-21 → 09-17.** **3m: 781 bars built from 1m,
09-10 → 09-17** (Yahoo caps 1m at ~7 days). Logic replicated block-for-block
from `ema_vwap_cross.pine`; entry next bar open, session-anchored VWAP on
`(O+H+L+C)/4` rebuilt each day, exit on close beyond the EMA, no stop, flat at
session end — exactly as the reel states.

**Tested on the underlying, not options.** The reel buys puts, but premium,
theta and the option spread sit *on top* of whatever the signal is worth. If the
signal has no directional edge in SPY itself, no option structure rescues it.

## The sweep

| tf | EMA | trades | win% | PF | net $ | median trade |
|---|---|---|---|---|---|---|
| 5m | 5 | 330 | 30.9 | **0.70** | −25.22 | −0.160 |
| 5m | 9 | 299 | 28.1 | **0.48** | −39.84 | −0.160 |
| 5m | 13 | 280 | 30.7 | **0.54** | −32.92 | −0.168 |
| 5m | 21 | 283 | 32.2 | **0.56** | −32.31 | −0.160 |
| 5m | 34 | 274 | 31.8 | **0.69** | −21.09 | −0.155 |
| 5m | 50 | 277 | 33.2 | **0.65** | −22.63 | −0.130 |
| 3m | 21 | 50 | 42.0 | 1.37 | +2.87 | −0.075 |
| 3m | 34 | 50 | 44.0 | 1.41 | +3.10 | −0.070 |

**The median trade is negative in all twelve cells.** The 5m sample is 274–330
trades over two months — large enough to settle it, and every EMA length loses.

## The 3m result is one trade

| | |
|---|---|
| net, 50 trades | +3.10 |
| best single trade | **+5.40 = 174% of the net** |
| top 3 trades | 237% of the net |
| net without the best trade | **−2.31** |
| median trade | −0.070 |

Forty-nine of the fifty trades collectively lose money.

And it is not the timeframe. Same eight days, both timeframes:

| set | EMA | trades | PF | net |
|---|---|---|---|---|
| 3m, 8 days | 34 | 50 | 1.41 | +3.10 |
| 5m, **same** 8 days | 34 | 39 | 1.07 | +0.61 |
| 5m, full 2 months | 34 | 274 | **0.69** | −21.09 |

That week was mildly kind on both timeframes. The two-month picture is not.

## It is worse than random, and it is not the fees

Random entries on the same bars, matched for count and long/short mix:

| | PF |
|---|---|
| random, 5th percentile | 0.70 |
| random, median | 0.95 |
| random, 95th percentile | 1.25 |
| **strategy (274 trades)** | **0.69 — 4th percentile** |

It underperforms 96% of random entry sets. And at **zero cost** it still loses:
PF 0.76, −$15.61. This is not a spread problem.

## Why: the two rules fight each other

**85% of trades exit within ONE bar.** Median bars held: 0.

The entry is a rejection at VWAP — price wicks through and closes back. But after
a wick through VWAP, price is *already at or near the EMA*, so "exit when a
candle breaks through the EMA" fires on the very next bar. The trade is closed
before it can do anything, and the round trip is paid every time.

## The obvious fix does not work either

Ignoring the EMA break for the first N bars — testing my own diagnosis rather
than asserting it:

| EMA | min hold 0 | 1 | 2 | 3 | 5 | 8 |
|---|---|---|---|---|---|---|
| 9 | 0.48 | 0.58 | 0.61 | 0.62 | 0.65 | 0.50 |
| 21 | 0.56 | 0.63 | 0.66 | 0.60 | 0.61 | 0.44 |
| 34 | 0.69 | 0.74 | 0.68 | 0.67 | 0.65 | 0.54 |

Eighteen cells, **every one negative**, PF never reaching 0.74. Holding longer
lifts PF slightly and makes the *median trade worse* (−0.16 → −0.28). So the
fast exit is a real mechanical flaw, but fixing it does not save the strategy —
the entry signal has no edge to preserve.

## Verdict

**Well-powered negative.** 274–330 trades over two months, all six EMA lengths
negative, worse than 96% of random entries, losing even at zero cost, and not
rescued by the one structural fix its own failure mode suggests.

The single positive cell is 50 trades in one week carried entirely by one trade.

On options this is worse, not better: the reel buys puts, and premium decay plus
the option spread are additive costs on a signal that already loses in the
underlying.

## Caveats

- One instrument, two months, one market regime.
- The **EMA length was never shown in the reel**. Six values were swept, 5 to
  50, and all lose on the well-powered sample — but if the intended value is
  something unusual, it was not among them.
- "Wicks thru VWAP" is read strictly (wick pierces, body closes back). The loose
  reading fires far more often and was not swept here.
