"""Point the lag estimator at a feed and find out whether the premise holds.

Works against any object implementing adapters.base.Feed. Pass --feed as
`module:factory` and the factory is called with (u_token, contracts, spot,
t_years, iv) -- that is the seam where a broker's own feed goes, and nothing
above it changes.

Run it against the simulator first (--feed sim --sim-lag 12) so you can see the
estimator recover a lag you set yourself. An instrument that has not been shown
to recover a known answer should not be trusted with an unknown one.
"""
from __future__ import annotations
import argparse, asyncio, importlib

from . import clock
from .clock import now_ns
from .instruments import ALL
from .lag_probe import LagProbe
from .adapters.sim import SimFeed


def make_contracts(spot: float, step: float, each_side: int, base: int = 1):
    atm = round(spot / step) * step
    out, tok = [], base
    for i in range(-each_side, each_side + 1):
        k = atm + i * step
        for is_call in (True, False):
            out.append(dict(token=tok, strike=k, is_call=is_call))
            tok += 1
    return out


def load_feed(spec_str, u_token, contracts, spot, t_years, iv, tick, hz, lag):
    if spec_str == "sim":
        return SimFeed(u_token, contracts, spot, t_years, iv, tick=tick,
                       lag_ms=lag, hz=hz, seed=7)
    mod_name, _, fn_name = spec_str.partition(":")
    if not fn_name:
        raise SystemExit(f"--feed must be 'sim' or 'module:factory', got {spec_str!r}")
    mod = importlib.import_module(mod_name)
    return getattr(mod, fn_name)(u_token, contracts, spot, t_years, iv)


async def main_async(a) -> int:
    spec = ALL[a.symbol]
    contracts = make_contracts(a.spot, spec.strike_step, a.each_side)
    feed = load_feed(a.feed, 0, contracts, a.spot, a.days / 365.0, a.iv,
                     spec.tick, a.hz, a.sim_lag)
    probe = LagProbe(0, contracts, a.iv, a.days / 365.0,
                     grid_us=a.grid_us, size=a.samples)
    feed.set_handler(probe.on_tick)

    print(f"LAG PROBE  {a.symbol}  spot {a.spot:,.0f}  "
          f"{len(contracts)} contracts  feed={a.feed}")
    if a.feed == "sim":
        print(f"  simulator lag set to {a.sim_lag}ms -- the estimate below "
              f"should recover it")
    print(f"  grid {a.grid_us}us, up to {a.max_shift} steps "
          f"({a.max_shift * a.grid_us / 1000:.0f}ms of shift searched)")
    print()

    if a.feed == "sim":
        if clock.VIRTUAL is None:
            raise SystemExit("run the simulator with HFT_VIRTUAL_CLOCK=1")
        clock.VIRTUAL.reset()
        dt = int(1e9 / a.hz)
        for _ in range(int(a.seconds * a.hz)):
            clock.VIRTUAL.advance(dt)
            feed.step()
    else:
        await asyncio.wait_for(feed.run(), timeout=a.seconds + 5)

    print(probe.report(max_shift=a.max_shift, min_lead=a.min_lead))
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Measure option quote lag")
    p.add_argument("--symbol", default="NIFTY", choices=sorted(ALL))
    p.add_argument("--spot", type=float, default=23_200.0)
    p.add_argument("--feed", default="sim",
                   help="'sim', or 'module:factory' for your own feed")
    p.add_argument("--seconds", type=float, default=30.0)
    p.add_argument("--each-side", type=int, default=4)
    p.add_argument("--iv", type=float, default=0.14)
    p.add_argument("--days", type=float, default=3.0)
    p.add_argument("--grid-us", type=int, default=1_000)
    p.add_argument("--max-shift", type=int, default=45)
    p.add_argument("--samples", type=int, default=8192)
    p.add_argument("--min-lead", type=float, default=0.05)
    p.add_argument("--hz", type=int, default=2000, help="simulator tick rate")
    p.add_argument("--sim-lag", type=float, default=12.0)
    return asyncio.run(main_async(p.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
