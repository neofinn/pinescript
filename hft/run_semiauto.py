"""Semi-automatic trading: you call direction, the machine works the order.

Two modes.

  --console   reads instructions from stdin while the feed runs. This is the
              real one.
  --script    replays a timed list of instructions against the simulator, so
              the whole path can be exercised without a human in the loop.

CONSOLE COMMANDS
  arm                     enable trading (nothing executes before this)
  long  <lots> [u] [ttl]  build long; u = urgency 0..1, ttl in seconds
  short <lots> [u] [ttl]  build short
  flat                    square off now
  kill                    stop all new risk, cancel resting orders, KEEP the
                          position (squaring off is a separate instruction --
                          an automatic flatten on kill is a market order at the
                          worst possible moment)
  rearm                   clear a kill; only a human can do this
  status                  print position, intent, execution quality
  quit

Urgency is the one execution dial you are given, because it encodes the one
thing only you know: how quickly you think you are right. Everything else --
price, order type, slicing, when to cross -- is the machine's.
"""
from __future__ import annotations
import argparse, asyncio, sys

from .adapters.limitsim import LimitGateway
from .adapters.sim import SimFeed
from .clock import now_ns
from .execution import Executor
from .instruments import ALL
from .intent import IntentBook, Side, Reject
from .orders import OrdState
from .risk import RiskGate
from .semiauto import SemiAuto
from .session import Phase


def build(a):
    spec = ALL[a.symbol]
    risk = RiskGate(max_pos_lots=a.max_lots, max_net_delta=1e9,
                    max_order_value=a.capital * 0.25, max_orders=a.max_orders,
                    max_daily_loss=a.capital * a.loss_pct / 100.0,
                    orders_per_sec=a.orders_per_sec, min_gap_us=a.min_gap_us)
    ex = Executor(spec.tick, max_clip=a.max_clip, pov=a.pov,
                  cross_at=a.cross_at, improve_ticks=a.improve,
                  max_slip_ticks=a.max_slip, requote_ms=a.requote_ms)
    ib = IntentBook(flip_cooldown_s=a.flip_cooldown)
    eng = SemiAuto(1, spec.tick, spec.lot, risk, ex, ib)
    feed = SimFeed(0, [dict(token=1, strike=a.spot, is_call=True)], a.spot,
                   3.0 / 365.0, 0.14, tick=spec.tick, lag_ms=spec.expected_lag_ms,
                   hz=a.hz, seed=a.seed)
    gw = LimitGateway(spec.tick, eng.store, fee_per_lot=0.0, seed=5)
    return eng, feed, gw, spec


def handle(eng: SemiAuto, line: str) -> str:
    p = line.strip().split()
    if not p:
        return ""
    c = p[0].lower()
    mid = eng.book.mid or eng.book.last
    if c == "arm":
        eng.arm(); return "ARMED"
    if c == "kill":
        eng.kill("console"); return "KILLED (position retained)"
    if c == "rearm":
        eng.intents.re_arm(); eng.risk.killed = False; eng.risk.arm()
        return "RE-ARMED"
    if c == "status":
        return eng.status()
    if c == "flat":
        if eng.position == 0:
            return "already flat"
        side = Side.SHORT if eng.position > 0 else Side.LONG
        r = eng.intents.submit(side, abs(eng.position), urgency=1.0, ttl_s=60,
                               arrival_px=mid, net_position=eng.position,
                               note="flat")
        return f"FLAT -> {r.name}"
    if c in ("long", "short"):
        if len(p) < 2:
            return "usage: long <lots> [urgency] [ttl_s]"
        try:
            lots = int(p[1])
            urg = float(p[2]) if len(p) > 2 else 0.5
            ttl = float(p[3]) if len(p) > 3 else 300.0
        except ValueError:
            return "bad number"
        side = Side.LONG if c == "long" else Side.SHORT
        r = eng.intents.submit(side, lots, urg, ttl, arrival_px=mid,
                               net_position=eng.position, note="console")
        if r is Reject.OK:
            return (f"{side.name} {lots} urgency {urg} ttl {ttl:.0f}s "
                    f"arrival {mid:.2f}")
        return f"REFUSED: {r.name}"
    return f"unknown: {c}"


async def pump(eng, gw, hz):
    """Work the order book: submit what the engine emitted, advance resting."""
    while True:
        for o, why in eng.drain():
            gw.submit(o, eng.book.bid, eng.book.ask)
            if o.state is OrdState.FILLED:
                eng.on_fill(o.side, o.filled, o.avg_px)
        for o in list(eng.store.all_live()):
            before = o.filled
            # An order resting INSIDE the spread is itself the best bid or
            # offer. Passing the untouched book would compare it against a
            # price it has already improved on, and it could never fill.
            eb = max(eng.book.bid, o.limit_px) if o.side > 0 else eng.book.bid
            ea = min(eng.book.ask, o.limit_px) if o.side < 0 else eng.book.ask
            gw.on_book(o, eb, ea, traded_lots=2,
                       micro_delta=eng.book.micro_delta)
            if o.filled > before:
                eng.on_fill(o.side, o.filled - before, o.avg_px)
        eng.store.sweep()
        await asyncio.sleep(0.002)


async def console(eng):
    loop = asyncio.get_event_loop()
    while True:
        line = await loop.run_in_executor(None, sys.stdin.readline)
        if not line or line.strip().lower() in ("quit", "exit"):
            return
        out = handle(eng, line)
        if out:
            print(out, flush=True)


async def main_async(a) -> int:
    eng, feed, gw, spec = build(a)
    feed.set_handler(eng.on_tick)
    eng.set_phase(Phase.ACTIVE)
    print(f"SEMI-AUTO  {a.symbol}  spot {a.spot}  lot {spec.lot}  "
          f"tick {spec.tick}")
    print(f"  max {a.max_lots} lots, clip {a.max_clip}, PoV {a.pov:.0%}, "
          f"cross at aggression {a.cross_at}, no-chase {a.max_slip} ticks")
    print("  type 'arm' to enable trading\n")
    tasks = [asyncio.create_task(pump(eng, gw, a.hz)),
             asyncio.create_task(feed.run(a.seconds))]
    if a.console:
        tasks.append(asyncio.create_task(console(eng)))
    if a.script:
        async def play():
            for step in a.script.split(";"):
                t, _, cmd = step.partition("@")
                await asyncio.sleep(float(t))
                print(f"[{float(t):>5.1f}s] > {cmd.strip()}")
                print("        " + handle(eng, cmd).replace("\n", "\n        "),
                      flush=True)
        tasks.append(asyncio.create_task(play()))
    try:
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for t in tasks:
            t.cancel()
    print("\n" + "=" * 62); print(eng.status())
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Semi-auto: manual direction, auto execution")
    p.add_argument("--symbol", default="NIFTY", choices=sorted(ALL))
    p.add_argument("--spot", type=float, default=23_200.0)
    p.add_argument("--capital", type=float, default=500_000.0)
    p.add_argument("--max-lots", type=int, default=10)
    p.add_argument("--max-clip", type=int, default=3)
    p.add_argument("--pov", type=float, default=0.10)
    p.add_argument("--cross-at", type=float, default=0.65)
    p.add_argument("--improve", type=float, default=1.0)
    p.add_argument("--max-slip", type=float, default=8.0,
                   help="no-chase band, in ticks either side of arrival")
    p.add_argument("--requote-ms", type=float, default=400.0)
    p.add_argument("--flip-cooldown", type=float, default=10.0)
    p.add_argument("--orders-per-sec", type=float, default=20.0)
    p.add_argument("--min-gap-us", type=int, default=1000)
    p.add_argument("--max-orders", type=int, default=2000)
    p.add_argument("--loss-pct", type=float, default=2.0)
    p.add_argument("--seconds", type=float, default=60.0)
    p.add_argument("--hz", type=int, default=200)
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--console", action="store_true")
    p.add_argument("--script", default="",
                   help="timed commands: '1@arm;2@long 5 0.3 20;12@status'")
    return asyncio.run(main_async(p.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
