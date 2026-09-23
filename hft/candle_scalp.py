"""Open-direction scalp inside a candle: no stop, TP only, flip on retracement.

The rules being tested, exactly as specified:

  * take direction from how the candle opens
  * no stop loss. Take profit at 1-2 index points
  * once +1 point is reached, trail, with a hard stop placed at a PROFIT level
  * on a retracement of the same candle, take the opposite direction
  * expect the candle to travel at least 5 points, and fire as many orders as
    the window allows

Removing the stop does not remove the loss. It removes the BOUND on the loss,
and it moves the loss out of the per-trade arithmetic into a tail you only see
when you plot the distribution. That is why this module simulates rather than
computes: with a capped win and an uncapped loss, the mean is not where the
information is. What matters is P(no TP) and how far the position has travelled
by the time something forces it out -- and something always does, because the
candle ends, the session ends, or the flip realises it.

The one genuinely favourable piece is the trailing hard stop at a profit level.
It caps give-back on winners, which is real. It does nothing for the trades that
never reach +1, and those are the entire risk.

Costs are charged per round trip at the measured statutory rate plus the
crossed spread, because "punch in maximum orders" pays that toll every time.
"""
from __future__ import annotations
import random
from dataclasses import dataclass, field

from .costs import CostModel, NSE_MEMBER
from .instruments import NIFTY, Spec
from .pricing import bs_call, bs_delta_call
from .scalp import strike_for_delta, breakeven_points


@dataclass
class Rules:
    tp_points: float = 2.0          # take profit
    stop_points: float = 0.0        # 0 = NO STOP, which is the case as stated
    arm_points: float = 1.0         # trail arms once this is reached
    trail_points: float = 0.5       # give-back allowed after arming
    lock_points: float = 0.2        # hard stop parks here once armed
    open_ticks_s: float = 5.0       # seconds of candle used to read direction
    open_min_points: float = 0.5    # opening move must be at least this
    retrace_points: float = 2.0     # retracement that triggers the flip
    max_entries: int = 40           # "maximum orders" inside the window
    reentry_gap_s: float = 2.0      # minimum seconds between entries
    candle_s: float = 300.0         # 5 minutes
    flat_at_end: bool = True        # the candle ends and you are out


@dataclass
class Outcome:
    pnl_points: float = 0.0         # net, in index points, after costs
    entries: int = 0
    tp_hits: int = 0
    trail_exits: int = 0
    end_exits: int = 0              # forced out at the candle close
    stop_exits: int = 0
    worst_open: float = 0.0         # deepest adverse excursion held
    costs_points: float = 0.0


def path(n: int, sigma_5m_points: float, rng: random.Random,
         drift_points: float = 0.0) -> list[float]:
    """Index path in POINTS relative to the open, n steps over the candle."""
    sd = sigma_5m_points / (n ** 0.5)
    mu = drift_points / n
    out, x = [0.0], 0.0
    for _ in range(n):
        x += rng.gauss(mu, sd)
        out.append(x)
    return out


def run_candle(px: list[float], rules: Rules, cost_points: float,
               steps_per_s: float) -> Outcome:
    """One candle, one pass of the rules. `cost_points` is the round trip."""
    o = Outcome()
    n = len(px) - 1
    open_i = int(rules.open_ticks_s * steps_per_s)
    if open_i >= n:
        return o

    # direction from the opening move; too small a move is no signal
    move = px[open_i]
    if abs(move) < rules.open_min_points:
        side = 0
    else:
        side = 1 if move > 0 else -1

    i = open_i
    last_entry_i = -10**9
    pos_side = 0
    entry_px = 0.0
    armed = False
    best = 0.0

    while i < n:
        i += 1
        p = px[i]

        if pos_side != 0:
            gain = pos_side * (p - entry_px)
            if gain > best:
                best = gain

            # trailing arms at +arm_points and parks a hard stop in profit
            if not armed and gain >= rules.arm_points:
                armed = True

            exit_now = False
            if rules.stop_points > 0.0 and gain <= -rules.stop_points:
                # a real stop, for the comparison against strategies that have
                # one. The rules as specified set this to 0.
                o.stop_exits += 1
                exit_now = True
            elif gain >= rules.tp_points:
                o.tp_hits += 1
                exit_now = True
            elif armed and gain <= max(rules.lock_points,
                                       best - rules.trail_points):
                o.trail_exits += 1
                exit_now = True

            if exit_now:
                o.pnl_points += gain - cost_points
                o.costs_points += cost_points
                pos_side = 0
                armed = False
                best = 0.0
                continue

            if gain < o.worst_open:
                o.worst_open = gain

            # the flip: a retracement of the candle takes the other side. The
            # open position is realised, not netted -- two opposite option legs
            # are not a hedge, they are two premiums decaying at once.
            retraced = (side > 0 and p <= px[open_i] - rules.retrace_points) or \
                       (side < 0 and p >= px[open_i] + rules.retrace_points)
            if retraced and pos_side == side:
                o.pnl_points += gain - cost_points
                o.costs_points += cost_points
                o.end_exits += 1
                pos_side = 0
                armed = False
                best = 0.0
                side = -side
            continue

        # flat: re-enter in the current direction
        if side == 0 or o.entries >= rules.max_entries:
            continue
        if i - last_entry_i < rules.reentry_gap_s * steps_per_s:
            continue
        pos_side = side
        entry_px = p
        o.entries += 1
        last_entry_i = i

    if pos_side != 0 and rules.flat_at_end:
        gain = pos_side * (px[n] - entry_px)
        o.pnl_points += gain - cost_points
        o.costs_points += cost_points
        o.end_exits += 1
        if gain < o.worst_open:
            o.worst_open = gain
    return o


def simulate(n_candles: int = 20_000, sigma_5m_points: float = 3.13,
             rules: Rules | None = None, cost_points: float = 0.75,
             steps_per_s: float = 2.0, seed: int = 11,
             drift_points: float = 0.0) -> dict:
    rules = rules or Rules()
    rng = random.Random(seed)
    n = int(rules.candle_s * steps_per_s)
    pnls, entries, tps, trails, ends, worsts, stops = [], [], [], [], [], [], []
    for _ in range(n_candles):
        p = path(n, sigma_5m_points, rng, drift_points)
        o = run_candle(p, rules, cost_points, steps_per_s)
        pnls.append(o.pnl_points)
        entries.append(o.entries)
        tps.append(o.tp_hits)
        trails.append(o.trail_exits)
        ends.append(o.end_exits)
        stops.append(o.stop_exits)
        worsts.append(o.worst_open)
    pnls_sorted = sorted(pnls)
    m = len(pnls_sorted)
    tot_tr = sum(tps) + sum(trails) + sum(ends) + sum(stops)
    return dict(
        candles=n_candles,
        mean=sum(pnls) / m,
        median=pnls_sorted[m // 2],
        p05=pnls_sorted[int(m * 0.05)],
        p01=pnls_sorted[int(m * 0.01)],
        worst=pnls_sorted[0],
        best=pnls_sorted[-1],
        pos_share=sum(1 for x in pnls if x > 0) / m,
        entries=sum(entries) / m,
        trades=tot_tr / m,
        tp_share=sum(tps) / tot_tr if tot_tr else 0.0,
        trail_share=sum(trails) / tot_tr if tot_tr else 0.0,
        end_share=sum(ends) / tot_tr if tot_tr else 0.0,
        stop_share=sum(stops) / tot_tr if tot_tr else 0.0,
        worst_open=sum(worsts) / m,
        total=sum(pnls),
    )


def report(ranges=(5.0, 10.0, 20.0, 32.0), n: int = 20_000,
           cost_points: float = 0.75, lots: int = 38, delta: float = 0.45,
           lot_size: int = 65, capital: float = 500_000.0) -> str:
    out, a = [], None
    a = out.append
    rs_pt = delta * lot_size * lots
    r1 = Rules(tp_points=1.0)
    a(f"CANDLE SCALP  open-direction, no stop, TP+trail, flip on retracement")
    a(f"{n:,} five-minute candles per row. Cost {cost_points} points per "
      f"round trip.")
    a(f"E[range] = 1.5958 x sigma, so a candle whose range is R implies "
      f"sigma = R/1.5958.")
    a("")
    a("1. DOES THE STRUCTURE MAKE ANYTHING?  costs on vs costs off")
    a(f"   {'range':>8}{'entries':>9}{'with cost':>12}{'ZERO cost':>12}"
      f"{'cost x entries':>16}")
    for R in ranges:
        x = simulate(n, R / 1.5958, r1, cost_points=cost_points, seed=11)
        y = simulate(n, R / 1.5958, r1, cost_points=0.0, seed=11)
        a(f"   {R:>6.0f}pt{x['entries']:>9.1f}{x['mean']:>12.2f}"
          f"{y['mean']:>12.3f}{-cost_points*x['entries']:>16.2f}")
    a("   At zero cost the mean is zero. The rules are a coin flip and the")
    a("   whole result is the toll -- and the loss equals cost x entries to")
    a("   three figures, so 'maximum orders' multiplies the toll and nothing")
    a("   else. It is the one setting that is strictly, linearly harmful.")
    a("")
    a(f"2. THE TAIL IN RUPEES  ({lots} lots, delta {delta}, "
      f"1 point = Rs{rs_pt:,.0f})")
    a(f"   {'range':>8}{'mean/candle':>14}{'p05':>12}{'p01':>12}"
      f"{'worst':>13}{'% of capital':>14}")
    for R in ranges:
        s = simulate(n, R / 1.5958, r1, cost_points=cost_points, seed=11)
        w = s["worst"] * rs_pt
        a(f"   {R:>6.0f}pt{s['mean']*rs_pt:>14,.0f}{s['p05']*rs_pt:>12,.0f}"
          f"{s['p01']*rs_pt:>12,.0f}{w:>13,.0f}"
          f"{w/capital*100:>13.1f}%")
    a("   There are 75 five-minute candles in a session. Multiply column 2.")
    return "\n".join(out)


def main() -> int:
    import argparse
    p = argparse.ArgumentParser(description="Open-direction candle scalp")
    p.add_argument("--candles", type=int, default=20_000)
    p.add_argument("--cost-points", type=float, default=0.75)
    p.add_argument("--lots", type=int, default=38)
    p.add_argument("--delta", type=float, default=0.45)
    p.add_argument("--capital", type=float, default=500_000.0)
    a = p.parse_args()
    print(report(n=a.candles, cost_points=a.cost_points, lots=a.lots,
                 delta=a.delta, capital=a.capital))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
