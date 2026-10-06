# Deep intraday history: why not TradingView, and what instead

Every fast-timeframe study in this repo has been limited by the data source,
not by the method. Yahoo serves **1-minute data for about a month** and
**30-minute for 60 days**, and refuses `period1`/`period2` windows past those
caps — verified, not assumed. That is why the 3-minute gold run had 22 sessions
and why its numbers sat in the same inflated band as every other thin sample.

## TradingView is not the answer

TradingView publishes **no official data API**, and its terms of service
prohibit automated extraction of chart data. The libraries that appear to do
this work by reverse-engineering an undocumented internal websocket. I have not
built that and would not recommend running it: it can break without notice, and
it puts the account at risk.

## Dukascopy is, and it is better

Dukascopy publishes an **open historical tick feed** — one LZMA-compressed file
per instrument per hour, back to roughly 2003, no key and no account:

```
https://datafeed.dukascopy.com/datafeed/{SYMBOL}/{YYYY}/{MM-1:02d}/{DD:02d}/{HH:02d}h_ticks.bi5
```

20 bytes per tick, big-endian: milliseconds into the hour, ask in points, bid
in points, ask volume, bid volume. An empty file means the market was closed,
which is how weekends appear.

Verified reachable for XAUUSD, XAGUSD and EURUSD back to 2010 in this
environment.

### It carries both sides of the book

This matters as much as the depth. **Every cost figure in this repo was an
assumption.** These files carry the real bid and the real ask, so the spread can
be measured per bar.

| gold, one hour | ticks | median spread | max | bps |
|---|---|---|---|---|
| Mon 14:00 UTC (London/NY overlap) | 24,240 | **$0.580** | $0.970 | 1.4 |
| Mon 02:00 UTC (Asia) | 14,836 | **$0.780** | $0.900 | 1.9 |
| Tue 12:00 UTC | 15,001 | $0.590 | $0.970 | 1.4 |
| 2025, 14:00 UTC | 11,927 | $0.510 | $0.840 | 1.5 |
| 2010, 14:00 UTC | 2,654 | $0.404 | $0.584 | 3.5 |

**The real gold spread is about $0.58/oz. This repo had been charging $0.25
plus $0.07 commission — understating the spread by 1.8×.** The spread is also
widest in Asian hours, which no flat assumption captures.

## The correction, applied

Median gold price over the h1 sample is $3,390, so $0.32 is 0.94 bps and $0.65
is 1.92 bps:

| cell | assumed 0.9 bp | **real 1.9 bp** | stress 2.9 bp | n |
|---|---|---|---|---|
| h1 P break aligned RR 20 | +0.368 | **+0.330** | +0.291 | 317 |
| h1 P break aligned RR 5 | +0.277 | **+0.240** | +0.201 | 317 |
| h1 P break aligned RR 2 | +0.180 | **+0.143** | +0.104 | 317 |
| d1 P break aligned RR 5 (weekly) | +0.130 | **+0.121** | +0.112 | 438 |

**About 10% of the edge was the cost assumption.** It survives, and so do all
three controls at the real spread:

| | h1 (n=317) | d1 weekly (n=438) |
|---|---|---|
| avg R at real spread | **+0.330** | **+0.121** |
| direction-neutral | +0.339 (long +0.504, short +0.175) | +0.120 (long +0.180, short +0.059) |
| shuffle control | real +0.330 vs best −0.951 → **100th pct** | real +0.121 vs best −0.498 → **100th pct** |
| split-half | +0.445 / +0.226 | +0.192 / +0.052 |

The correction is small **because the stops are wide** — median $11/oz on h1,
so an extra $0.33 is 3% of one R. Cost only bites when the stop is tight, which
is exactly what the 1-minute and 3-minute studies showed.

## Practical notes

- **Latency-bound, not bandwidth-bound.** ~15 s per hourly file through this
  environment's proxy. Serially that is 38 hours for a year of gold; the
  fetcher uses a 32-thread pool and does it in under two. It is resumable —
  hours already in the output file are skipped.
- **Store bars, not ticks.** One hour of gold is ~24,000 ticks. The fetcher
  aggregates to 1-minute bars (carrying mean and max spread) and discards the
  ticks, so a year costs tens of megabytes rather than many gigabytes.
- **Bars are built from the MID**, so they are side-neutral; the spread is
  charged explicitly at execution via `use_bar_spread=True` rather than baked
  into the prices.
- Expect ~10% transient request failures through the proxy; re-running the
  fetcher fills the gaps.

## Other options, briefly

- **Your own MT5 terminal** gives deep history from your broker for free, and
  it is the broker you will actually trade against — the most faithful source
  available to you.
- **Databento, Polygon, Tiingo** — paid, legitimate, well documented.
- **Binance and other crypto exchanges** — free deep 1-minute history, but no
  gold.

## Files

- `scripts/dukascopy.py` — tick fetcher, parser, bar aggregator with measured
  spreads, threaded and resumable.
