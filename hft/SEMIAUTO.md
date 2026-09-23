# Semi-automatic: you call direction, the machine executes

`python -m hft.run_semiauto --console`

## Why this split

Everything measured in this project failed at **direction**, and nothing failed
at execution. Tick-to-signal is **15.6µs**; fourteen pre-registered signals
scored at or below a random entry; two clipped strategies came back with an
in-sample to out-of-sample rank correlation of **+0.006 and +0.067**.

So the human supplies side, size and urgency. The machine supplies timing,
order type, price, slicing and exits. Neither is allowed into the other's job —
with no working intent the engine sits flat and does nothing, however tempting
the book looks.

## Console

```
arm                     nothing executes before this
long  <lots> [u] [ttl]  build long;  u = urgency 0..1,  ttl in seconds
short <lots> [u] [ttl]  build short
flat                    square off now
kill                    stop new risk, cancel resting orders, KEEP the position
rearm                   clear a kill — only a human can
status                  position, intent, execution quality
```

**Urgency is the only execution dial you get**, because it encodes the one thing
only you know: how quickly you think you're right. Everything else is the
machine's.

## What the machine does with it

| control | behaviour |
|---|---|
| **aggression ramp** | starts at your urgency, ramps to 1.0 as the TTL burns down — patient early, decisive late |
| **slicing** | clips capped absolutely and as a share of traded volume (PoV), so you aren't a large fraction of the tape |
| **no-chase** | never pays worse than arrival ± `max_slip`. When the band binds the algo **stops** |
| **re-quote** | a resting order the market walked away from is an option you wrote for free; age it out and re-post |

**No-chase is the control that matters.** Without it a ramping aggression
follows price wherever it goes and buys the top of the very move it was trying
to catch. Not filling is a legitimate outcome; chasing is not.

## The scorecard

Execution is measured as **implementation shortfall against the arrival price** —
the price on screen when you made the call, in basis points. Positive means the
fill was worse than your decision. It is the number that tells you whether
execution is giving back the edge you think you have.

Measured per intent, not per session. From a live run:

| call | arrival | filled | orders | shortfall |
|---|---|---|---|---|
| `long 6 0.4 12` | 221.41 | +6 | 2 posted, 0 crossed | **+63.1 bps** |
| `short 4 0.9 12` (flip) | — | −4 | 5 crossed | **−150.9 bps** |

Low urgency worked passively and posted; high urgency crossed. That is the
design behaving as specified.

> A bug worth recording: `avg_fill` was session-cumulative at first, which
> blended a long filled at 221 into a short filled at 373 and reported **+1,139
> bps** of slippage nobody incurred. Each intent now tracks its own fills.

## Safety rules

`python hft/test_semiauto_safety.py` — 20 assertions, all green.

| rule | why it exists |
|---|---|
| nothing before `arm` | a live feed should never be a live order router by default |
| **kill is one-way**, keeps the position | an automatic flatten on kill is a market order at the worst moment. Squaring off is its own instruction |
| **flip via flat** | LONG→SHORT is two instructions. Netting them leaves a moment that is neither side and risks both |
| **flip cooldown** | the most dangerous input is a reversal, and the usual cause is panic. A flip inside the cooldown is *refused*, not queued — a queued reversal fires exactly when you've changed your mind again |
| same-side duplicate refused | fat finger on the same call |
| **intent expiry** | a call made at 09:20 isn't still true at 09:45, but a machine will happily keep working it. On lapse it stops adding; what's filled is held, never silently added to |
| expiry holds, not flattens | auto-flattening a stale opinion sells at whatever price exists the moment you stopped watching |
| positions open on **fill**, never submit | booking on submission reports trades that never happened — with passive orders, where most are cancelled, that's the difference between a measurement and a fiction |

## Wiring it to a real broker

The two seams are `adapters/base.py`:

- **`Feed`** — `set_handler(fn)` then call `fn(token, bid, ask, bid_qty, ask_qty, last, ts_ns)` per tick
- **`Gateway`** — `send / cancel / cancel_all / flatten`, and call `eng.on_fill(side, lots, px)` on every confirmation

Nothing above those two changes. `run_semiauto.py` wires the simulator; swap in
your broker's adapter and the same engine drives it.

**Before going live:** run `--console` against the simulator until the safety
rules feel reflexive — especially that `kill` does *not* flatten. And set
`--max-slip` deliberately: the demo needed 60 ticks because 8 ticks on a ₹220
option is 0.18%, tight enough to stop every order.
