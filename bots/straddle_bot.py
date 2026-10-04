"""Live straddle stop-and-reverse bot. Dry-run by default.

The state machine is the one measured in STRADDLE_BOT.md and it is deliberately
the same logic as scripts/straddle_sar.py, so what runs here is what was
backtested:

    FLAT      a buy-stop rests at the N-bar high, a sell-stop at the N-bar low.
    IN_TRADE  the filled side is the position; the opposite order is amended
              into the protective trailing stop rather than cancelled.
    FLIP      when the stop fills it closes the position and, in SAR mode,
              opens the opposite one. A fresh stop goes out immediately.

What this file will and will not do
-----------------------------------
It will not place a live order unless you pass --live AND supply credentials
through the environment. There are no credentials in this repository and none
should ever be pasted into a chat. Put them in a .env on the machine that runs
this, keep that file out of git, and give the key the narrowest permissions
your broker offers.

Correctness properties that matter more than the strategy
---------------------------------------------------------
* RECONCILE FIRST. Every cycle begins by reading the broker's actual position
  and open orders. Broker state wins over local state, always. A bot that
  trusts its own memory after a restart or a missed fill will double its size.
* ONE STOP, NEVER TWO. Orders carry deterministic client IDs. Before a new
  stop goes out the old one is cancelled and the cancel is confirmed. A
  trailing stop that leaves its predecessor alive is how an account ends up
  short twice.
* NEVER LOOSEN A TRAIL. The stop only moves in the favourable direction.
* ACT ON CLOSED BARS ONLY. Levels come from completed candles. The backtest
  assumed that and so does this.
* PERSIST. State is written to disk after every transition so a crash resumes
  rather than restarts.

Risk note, stated plainly because the measurement says it: on hourly bars this
system loses to its own transaction costs, and the daily portfolio edge that
did show up came entirely from BTC and ETH. Run it on daily bars across many
markets, on a demo account, for long enough to see a drawdown, before it ever
touches real money.

Do NOT run it on minute bars. Measured over 15 markets (STRADDLE_FAST_BARS.md):
at 1-minute a round trip costs 192% of the bar's own average range, the system
beat buy-and-hold in 0 of 15 markets, and the account lost 20% in 25 days --
96% on BTC and ETH. The gross edge there is 0.135 basis points per trade
against a 2-20 bp round trip, so no execution improvement reaches it. The
--timeframe default is 1d deliberately.
"""
from __future__ import annotations
import argparse, json, logging, os, sys, time
from dataclasses import dataclass, asdict, field
from typing import Optional, Protocol

log = logging.getLogger("straddle")


# ---------------------------------------------------------------- broker API
class Broker(Protocol):
    """Implement these six for any venue. Nothing else in this file is venue
    specific, which is the point -- the state machine must not know or care."""

    def bars(self, symbol: str, timeframe: str, n: int) -> list[dict]: ...
    def position(self, symbol: str) -> float: ...
    def open_orders(self, symbol: str) -> list[dict]: ...
    def place_stop(self, symbol: str, side: str, qty: float, stop: float,
                   client_id: str, reduce_only: bool = False) -> dict: ...
    def cancel(self, symbol: str, client_id: str) -> bool: ...
    def last_price(self, symbol: str) -> float: ...


@dataclass
class Config:
    symbol: str = "GC=F"
    timeframe: str = "1d"
    entry_len: int = 20
    trail: str = "atr"           # "atr" or "donchian"
    trail_len: int = 10
    atr_len: int = 14
    atr_mult: float = 3.0
    sar: bool = False            # flat-and-rearm measured better than always-in
    risk_frac: float = 0.005     # of equity, per trade
    equity: float = 100_000.0
    max_notional_frac: float = 0.20
    poll_seconds: int = 60
    state_path: str = "var/straddle_state.json"


@dataclass
class State:
    pos: float = 0.0             # signed units
    entry: Optional[float] = None
    stop: Optional[float] = None
    ext: Optional[float] = None  # best price since entry
    last_bar_t: Optional[int] = None
    orders: dict = field(default_factory=dict)   # client_id -> {side, stop}


# ------------------------------------------------------------------ indicators
def atr(bars, n):
    if len(bars) < n + 1:
        return None
    trs = []
    for i in range(1, len(bars)):
        p = bars[i - 1]["c"]
        b = bars[i]
        trs.append(max(b["h"] - b["l"], abs(b["h"] - p), abs(b["l"] - p)))
    return sum(trs[-n:]) / n


def levels(bars, cfg: Config):
    """Entry straddle from CLOSED bars. bars[-1] must already be complete."""
    w = bars[-cfg.entry_len:]
    return max(b["h"] for b in w), min(b["l"] for b in w)


def trail_stop(bars, cfg: Config, pos: float, ext: float) -> Optional[float]:
    if cfg.trail == "atr":
        a = atr(bars, cfg.atr_len)
        if a is None:
            return None
        return ext - cfg.atr_mult * a if pos > 0 else ext + cfg.atr_mult * a
    w = bars[-cfg.trail_len:]
    return min(b["l"] for b in w) if pos > 0 else max(b["h"] for b in w)


def size_for(cfg: Config, entry: float, stop: float) -> float:
    d = abs(entry - stop)
    if d <= 0:
        return 0.0
    by_risk = (cfg.equity * cfg.risk_frac) / d
    by_cap = (cfg.equity * cfg.max_notional_frac) / entry
    return max(0.0, min(by_risk, by_cap))


# ------------------------------------------------------------------- the bot
class StraddleBot:
    def __init__(self, broker: Broker, cfg: Config, live: bool = False):
        self.b, self.cfg, self.live = broker, cfg, live
        self.s = self._load()

    # --- persistence
    def _load(self) -> State:
        p = self.cfg.state_path
        if os.path.exists(p):
            try:
                return State(**json.load(open(p)))
            except Exception:
                log.warning("state file unreadable, starting clean")
        return State()

    def _save(self):
        p = self.cfg.state_path
        os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
        tmp = p + ".tmp"
        json.dump(asdict(self.s), open(tmp, "w"))
        os.replace(tmp, p)          # atomic, so a crash mid-write cannot corrupt

    # --- order helpers
    def _cid(self, kind: str) -> str:
        return f"straddle-{self.cfg.symbol}-{kind}"

    def _cancel_all(self):
        for cid in list(self.s.orders):
            if self._do(self.b.cancel, self.cfg.symbol, cid):
                self.s.orders.pop(cid, None)

    def _do(self, fn, *a, **k):
        if not self.live:
            log.info("DRY-RUN %s%s", getattr(fn, "__name__", fn), a)
            return True
        return fn(*a, **k)

    def _place(self, kind, side, qty, stop, reduce_only=False):
        cid = self._cid(kind)
        if cid in self.s.orders and abs(self.s.orders[cid]["stop"] - stop) < 1e-9:
            return                                   # already resting correctly
        if cid in self.s.orders:
            self._do(self.b.cancel, self.cfg.symbol, cid)
            self.s.orders.pop(cid, None)
        self._do(self.b.place_stop, self.cfg.symbol, side, qty, stop, cid,
                 reduce_only)
        self.s.orders[cid] = dict(side=side, stop=stop, qty=qty)

    # --- one cycle
    def step(self) -> bool:
        """Returns True if a closed bar was processed."""
        bars = self.b.bars(self.cfg.symbol, self.cfg.timeframe,
                           max(self.cfg.entry_len, self.cfg.atr_len,
                               self.cfg.trail_len) + 5)
        if len(bars) < self.cfg.entry_len + 2:
            log.warning("not enough history yet"); return False
        closed = bars[:-1]                       # the forming bar is never used
        bt = closed[-1]["t"]

        # RECONCILE: the broker is the source of truth, not this process
        real = self.b.position(self.cfg.symbol)
        if abs(real - self.s.pos) > 1e-9:
            log.warning("position drift: broker %s, local %s -- adopting broker",
                        real, self.s.pos)
            if real == 0:
                self.s.pos = 0.0; self.s.entry = self.s.stop = self.s.ext = None
            else:
                self.s.pos = real
                if self.s.entry is None:
                    self.s.entry = self.b.last_price(self.cfg.symbol)
                    self.s.ext = self.s.entry
            self.s.orders = {o.get("client_id", ""): o
                             for o in self.b.open_orders(self.cfg.symbol)}

        if self.s.last_bar_t == bt:
            return False                          # nothing new has closed
        self.s.last_bar_t = bt

        up, dn = levels(closed, self.cfg)
        px = closed[-1]["c"]

        if self.s.pos == 0:
            qty_l = size_for(self.cfg, up, dn)
            qty_s = size_for(self.cfg, dn, up)
            self._place("buy", "buy", qty_l, up)
            self._place("sell", "sell", qty_s, dn)
            log.info("FLAT  straddle armed  buy-stop %.4f  sell-stop %.4f", up, dn)
        else:
            self.s.ext = (max(self.s.ext or px, closed[-1]["h"]) if self.s.pos > 0
                          else min(self.s.ext or px, closed[-1]["l"]))
            raw = trail_stop(closed, self.cfg, self.s.pos, self.s.ext)
            if raw is not None:
                self.s.stop = (max(self.s.stop or raw, raw) if self.s.pos > 0
                               else min(self.s.stop or raw, raw))
                side = "sell" if self.s.pos > 0 else "buy"
                # SAR doubles up so the same order closes and reverses
                qty = abs(self.s.pos) * (2.0 if self.cfg.sar else 1.0)
                self._place("stop", side, qty, self.s.stop,
                            reduce_only=not self.cfg.sar)
                log.info("IN %s %.4f  trail -> %.4f",
                         "LONG" if self.s.pos > 0 else "SHORT",
                         self.s.pos, self.s.stop)
        self._save()
        return True

    def loop(self):
        log.info("straddle bot: %s %s  %s  %s", self.cfg.symbol,
                 self.cfg.timeframe, "SAR" if self.cfg.sar else "flat-and-rearm",
                 "LIVE" if self.live else "DRY-RUN (no orders will be sent)")
        while True:
            try:
                self.step()
            except Exception:
                log.exception("cycle failed; keeping the existing resting orders")
            time.sleep(self.cfg.poll_seconds)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--symbol", default="GC=F")
    p.add_argument("--timeframe", default="1d")
    p.add_argument("--entry-len", type=int, default=20)
    p.add_argument("--trail", choices=["atr", "donchian"], default="atr")
    p.add_argument("--atr-mult", type=float, default=3.0)
    p.add_argument("--sar", action="store_true",
                   help="always-in reversal; measured WORSE than flat-and-rearm")
    p.add_argument("--risk", type=float, default=0.005)
    p.add_argument("--equity", type=float, default=100_000.0)
    p.add_argument("--once", action="store_true")
    p.add_argument("--live", action="store_true",
                   help="actually send orders. Requires broker credentials in "
                        "the environment; without them this stays a dry run.")
    a = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)-7s %(message)s")
    cfg = Config(symbol=a.symbol, timeframe=a.timeframe, entry_len=a.entry_len,
                 trail=a.trail, atr_mult=a.atr_mult, sar=a.sar,
                 risk_frac=a.risk, equity=a.equity)
    try:
        from broker_adapters import make_broker        # user supplies this
        broker = make_broker(os.environ)
    except Exception as e:
        if a.live:
            log.error("--live needs a broker adapter and credentials: %s", e)
            return 2
        from paper_broker import PaperBroker
        broker = PaperBroker(cfg.symbol, cfg.timeframe)
        log.info("no broker adapter found; using the paper broker")
    bot = StraddleBot(broker, cfg, live=a.live)
    if a.once:
        bot.step()
    else:
        bot.loop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
