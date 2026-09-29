"""A simulator that reproduces the thing the strategy trades: quote lag.

Nothing is learned from a simulator where option quotes are always correct --
the strategy would never fire. Here each option's quote follows its own fair
value with a configurable lag and jitter, which is exactly the inefficiency the
live strategy is trying to take. Set lag to zero and the strategy should go
silent; if it still trades, the edge calculation has a bug in it.

Fills are pessimistic on purpose: a taker order crosses the spread and is
subject to the quote being pulled. `fill_prob` is the share of takes that get
done rather than rejected, and it is the single most optimistic assumption in
any HFT backtest.
"""
from __future__ import annotations
import asyncio, random
from ..clock import now_ns
from ..pricing import bs_call, bs_put


class SimFeed:
    def __init__(self, u_token: int, contracts: list[dict], spot0: float,
                 t_years: float, iv: float, tick: float = 0.05,
                 lag_ms: float = 12.0, jitter_ticks: float = 1.5,
                 vol_bps_per_s: float = 25.0, hz: int = 200,
                 seed: int = 7) -> None:
        self.u_token = u_token
        self.contracts = contracts
        self.spot = spot0
        self.t_years = t_years
        self.iv = iv
        self.tick = tick
        self.lag_ns = int(lag_ms * 1e6)
        self.jitter = jitter_ticks
        self.vol = vol_bps_per_s / 10_000.0
        self.hz = hz
        self.rng = random.Random(seed)
        self._h = None
        self._stop = False
        self._hist: dict[int, list] = {c["token"]: [] for c in contracts}

    def set_handler(self, fn) -> None:
        self._h = fn

    def subscribe(self, tokens) -> None:
        pass

    def _round(self, x: float) -> float:
        return round(x / self.tick) * self.tick

    def step(self) -> None:
        """One tick of the world. Synchronous so a deterministic driver can own
        the clock; `run` is the same thing paced against a real one."""
        dt = 1.0 / self.hz
        sd = self.vol * (dt ** 0.5)
        self.spot *= (1.0 + self.rng.gauss(0.0, sd))
        t = now_ns()
        half = self.tick * 0.5
        self._h(self.u_token, self.spot - half, self.spot + half,
                self.rng.randint(50, 400), self.rng.randint(50, 400),
                self.spot, t)

        for c in self.contracts:
            fair = (bs_call(self.spot, c["strike"], self.t_years, self.iv)
                    if c["is_call"] else
                    bs_put(self.spot, c["strike"], self.t_years, self.iv))
            h = self._hist[c["token"]]
            h.append((t, fair))
            if len(h) > 512:
                del h[:256]
            # the quote reflects fair value as it was lag_ns ago
            cutoff = t - self.lag_ns
            lagged = fair
            for ts, f in h:
                if ts <= cutoff:
                    lagged = f
                else:
                    break
            j = self.rng.gauss(0.0, self.jitter) * self.tick
            mid = max(self.tick, lagged + j)
            sp = self.tick * self.rng.choice((2, 2, 3, 4, 6))
            bid = self._round(mid - sp * 0.5)
            ask = self._round(mid + sp * 0.5)
            if bid <= 0.0:
                bid = self.tick
            if ask <= bid:
                ask = bid + self.tick
            self._h(c["token"], bid, ask,
                    self.rng.randint(25, 300), self.rng.randint(25, 300),
                    mid, now_ns())

    async def run(self, seconds: float) -> None:
        dt = 1.0 / self.hz
        for _ in range(int(seconds * self.hz)):
            if self._stop:
                return
            self.step()
            await asyncio.sleep(dt)

    async def stop(self) -> None:
        self._stop = True


class SimGateway:
    """Pessimistic taker fills, and it charges every cost a real one would."""

    def __init__(self, feed: SimFeed, fill_prob: float = 0.70,
                 slip_ticks: float = 0.5, fee_per_lot: float = 25.0,
                 seed: int = 11) -> None:
        self.feed = feed
        self.fill_prob = fill_prob
        self.slip = slip_ticks
        self.fee = fee_per_lot
        self.rng = random.Random(seed)
        self.fills: list[dict] = []
        self.rejected = 0
        self._n = 0

    async def send(self, token, side, lots, price, ioc=True):
        self._n += 1
        if self.rng.random() > self.fill_prob:
            self.rejected += 1          # quote pulled before the take landed
            return None
        px = price + side * self.slip * self.feed.tick
        self.fills.append(dict(token=token, side=side, lots=lots, px=px,
                               fee=self.fee * lots, ts=now_ns()))
        return f"SIM{self._n}"

    async def cancel(self, order_id): return True
    async def cancel_all(self): return 0

    async def flatten(self):
        n = 0
        net: dict[int, int] = {}
        for f in self.fills:
            net[f["token"]] = net.get(f["token"], 0) + f["side"] * f["lots"]
        for tok, q in net.items():
            if q:
                n += 1
        return n
