# pinescript

TradingView strategies and indicators.

## multi_strategy_confirmation.pine

A four-strategy confirmation system: an entry needs several independent reads
of the chart to agree before it fires.

| # | Strategy | Kind | Signal |
|---|---|---|---|
| 1 | Breakout | event | close beyond an N-bar range that excludes the live bar |
| 2 | Trend | state | Supertrend direction |
| 3 | S/R pushback | event | rejection at a confirmed swing pivot |
| 4 | Supply/Demand pushback | event | rejection inside a zone left by an impulse move |

**Confirmation.** `minConfirmations` votes must agree (default 2 of 4), no
strategy may oppose (`blockOnOpposition`), and at least one vote must be an
*event* this bar (`requireEvent`). That last rule matters more than it looks:
Supertrend is a *state* and votes on every bar for weeks at a time. Counting
states alone would enter the moment two conditions happened to line up and
never wait for anything to occur.

**Entries are limit orders at a retest**, `entryAtrMult` × ATR from the level
that justified them (default 0.1× — very tight). Two cases are handled
explicitly rather than left to chance:

- If the retest price is not on the correct side of the market the order is
  **not placed**. A buy limit at or above the market fills instantly at the
  market, which defeats the point of choosing a limit. Skipped signals get an
  `✕` on the chart so a triangle with no trade after it is explained.
- An unfilled order is **cancelled after `orderExpiryBars`**. A pending order
  left alive fills days later in a setup that no longer exists.

**Risk.** Initial stop `stopAtrMult` × ATR beyond the level. At
`breakevenR` × R the stop locks to entry. After that it trails at a distance
set by the 1–5 tightness dial (1 → 3.0× ATR, 5 → 1.0× ATR; default 2 → 2.5×).
The trail only ever ratchets — a stop that can loosen is not a stop. One
position at a time (`pyramiding = 0`).

### Lag, and what it costs

A swing pivot is not confirmed until `pivotRight` bars have printed after it,
so `ta.pivothigh()` returns a value already shifted back by that many bars.
That is correct — the script cannot see a pivot before the chart could — and
it means S/R levels arrive late. Lowering `pivotRight` makes them arrive
sooner and makes more of them false. No setting gives you early *and* correct.

### Reading the backtest

TradingView fills every limit order price touches, with no queue, no partial
fills, and no slippage beyond what you configure. Real fills are worse. Treat
a losing backtest as conclusive and a winning one as a reason to go and
measure the spread you actually pay.

### Webhook alerts

Entries and exits carry an `alert_message` shaped for the webhook gateway in
`neofinn/index-option-brain` (`scripts/start_here.sh` prints the URL and the
ingest secret). Set the secret in the script's **Webhook alerts** group, then
create an alert on the strategy with *Webhook URL* pointing at
`<base>/hook/strategy`.

### Not verified

TradingView is the only Pine compiler, and there isn't one in this
environment. This script has been reviewed line by line but **has not been
compiled or run on a chart.** Paste it into the Pine editor first; fix
anything it flags before trusting a backtest.
