"""Profile+flow setups traded as bought options on SPY and QQQ.

1:2 on the UNDERLYING -- and that is not 1:2 on the option, which is the first
thing this measures. A stop and a target equidistant-times-two in index points
map through a curved payoff: gamma makes the winner bigger than delta predicts
and the loser smaller, while theta takes from both. The realised option-level
payoff ratio is reported next to the intended one rather than assumed equal.

Inputs that are real rather than guessed:

  IV        VIX for SPY, VXN for QQQ, daily close over the same window. These
            are 30-day implied vols, so using them for a 0DTE option is
            wrong in a known direction -- hence the iv multiplier sweep, which
            is the honest way to carry an assumption you cannot pin down.
  expiry    SPY and QQQ list daily expiries. 0DTE means this session's 20:00
            UTC close. Held to the bell, T goes to zero and the option is
            worth intrinsic; that is not a modelling artefact, it is what
            happens.
  price     Black-Scholes REVALUED at the exit spot and exit time. Theta as a
            derivative overstates discrete decay near expiry, which this
            project has been caught by before.

Sizing is ex-ante: contracts are set from the loss the option WOULD take at the
stop given an assumed hold, using entry-time information only. The realised
risk then scatters around the intended figure, and that scatter is reported --
an option position sized to lose $1,000 does not lose $1,000.
"""
from __future__ import annotations
import datetime as dt
import json, math, os, random, statistics, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import vp_of_pure as P
import volume_profile as vp
import vp_signals as S
from hft.pricing import bs_call, bs_put, bs_delta_call, bs_delta_put

YEAR = 365.0 * 24 * 3600
RF = 0.04                       # US risk-free; the hft default is an INR rate
CLOSE_UTC = 20 * 3600           # 16:00 ET

# Per-instrument contract terms. These are not cosmetic: an ES option is
# $50 a point against SPY's $100 a point with strikes five points apart
# instead of one, and its at-the-money spread is a quarter point -- $12.50
# a round trip against SPY's $2. Running ES on SPY's numbers would flatter
# it by roughly six times on cost alone.
CONTRACT = {
    "SPY": dict(mult=100.0, step=1.0,  spread=0.02, comm=0.65),
    "QQQ": dict(mult=100.0, step=1.0,  spread=0.02, comm=0.65),
    # ES: CME lists daily expiries; ticks are 0.05 pt under 5.00 premium.
    # Commission is exchange + clearing + broker, per side.
    "ES":  dict(mult=50.0,  step=5.0,  spread=0.25, comm=1.25),
}


def price(is_call, s, k, t, iv):
    return bs_call(s, k, t, iv, RF) if is_call else bs_put(s, k, t, iv, RF)


def delta_of(is_call, s, k, t, iv):
    return (bs_delta_call(s, k, t, iv, RF) if is_call
            else bs_delta_put(s, k, t, iv, RF))


def pick_strike(is_call, s, t, iv, target, step):
    """Nearest listed strike to the target delta, searched outward from ATM."""
    best = None
    base = round(s / step) * step
    for i in range(-40, 41):
        k = base + i * step
        if k <= 0:
            continue
        d = abs(delta_of(is_call, s, k, t, iv))
        e = abs(d - target)
        if best is None or e < best[0]:
            best = (e, k, d)
    return best[1], best[2]


def session_closes(bars):
    """UTC epoch of each session's 16:00 ET close, in session order."""
    out = []
    for idxs in vp.sessions_of(bars):
        d = dt.datetime.utcfromtimestamp(bars[idxs[0]]["t"]).date()
        out.append(int(dt.datetime(d.year, d.month, d.day).timestamp()) + CLOSE_UTC)
    return out


def iv_for(vol, ts, mult):
    d = str(dt.datetime.utcfromtimestamp(ts).date())
    v = vol.get(d)
    if v is None:                       # holiday gap: last available close
        ks = [k for k in vol if k <= d]
        v = vol[max(ks)] if ks else 20.0
    return v / 100.0 * mult


def run_options(st, plan, vol, cfg, lo, hi, spec):
    """Walk the plan, trading one option position at a time.

    Exit rules are on the UNDERLYING: the profile stop, the 1:2 target, or the
    bell. The option is then revalued at that spot and that clock.
    """
    bars, ses, n = st["bars"], st["ses"], st["n"]
    closes = session_closes(bars)
    hi = n if hi is None else hi
    trades, pos, geo = [], None, 0
    for i in range(lo, min(hi, n - 1)):
        b = bars[i]
        if pos is not None:
            sd = pos["side"]
            hit_s = b["l"] <= pos["stop"] if sd > 0 else b["h"] >= pos["stop"]
            hit_t = b["h"] >= pos["targ"] if sd > 0 else b["l"] <= pos["targ"]
            spot = None
            why = None
            if hit_s:                       # stop-first on a tie, as before
                spot, why = pos["stop"], "stop"
            elif hit_t:
                spot, why = pos["targ"], "target"
            elif ses[i] != pos["ses"]:
                spot, why = b["c"], "bell"
            if spot is not None:
                t = max(0.0, (pos["expiry"] - b["t"]) / YEAR)
                px = price(pos["call"], spot, pos["k"], t, pos["iv"])
                m = spec["mult"]
                gross = (px - pos["prem"]) * m * pos["qty"]
                cost = (spec["spread"] * cfg["sp_mult"] * m
                        + spec["comm"] * 2) * pos["qty"]
                trades.append(dict(pnl=gross - cost, why=why, qty=pos["qty"],
                                   prem=pos["prem"] * m * pos["qty"],
                                   exit_px=px, entry_px=pos["prem"],
                                   risk=pos["risk"], side=sd, t_in=pos["t"],
                                   t_out=b["t"], under_r=abs(spot - pos["spot"])))
                pos = None
        if pos is None and plan[i] is not None:
            sd, stop, _ = plan[i]
            e = bars[i + 1]["o"]
            if stop is None or sd * (e - stop) <= 0:
                geo += 1
                continue
            r = abs(e - stop)
            targ = e + sd * 2.0 * r          # 1:2 on the underlying
            k_ses = ses[i + 1] + cfg["dte"]
            if k_ses >= len(closes):
                geo += 1
                continue
            expiry = closes[k_ses]
            t0 = (expiry - bars[i + 1]["t"]) / YEAR
            if t0 <= 0:
                geo += 1
                continue
            iv = iv_for(vol, bars[i + 1]["t"], cfg["iv_mult"])
            call = sd > 0
            k, d = pick_strike(call, e, t0, iv, cfg["delta"], spec["step"])
            prem = price(call, e, k, t0, iv)
            # below one tick there is no quote to lift; a model price of a
            # cent on a contract nobody makes a market in is not a fill
            if prem <= spec["spread"]:
                geo += 1
                continue
            # ex-ante loss at the stop, after an ASSUMED hold. Entry-time
            # information only -- using the real hold would be look-ahead.
            t_then = max(0.0, t0 - cfg["hold"] / YEAR)
            px_stop = price(call, stop, k, t_then, iv)
            m = spec["mult"]
            loss = ((prem - px_stop) * m
                    + spec["spread"] * cfg["sp_mult"] * m + spec["comm"] * 2)
            if loss <= 0:
                geo += 1
                continue
            qty = int(cfg["risk_$"] // loss)
            cap = int(cfg["equity"] * cfg["max_prem"] // (prem * m))
            qty = max(0, min(qty, cap))
            if qty < 1:
                geo += 1
                continue
            pos = dict(side=sd, stop=stop, targ=targ, spot=e, k=k, iv=iv,
                       call=call, prem=prem, qty=qty, expiry=expiry,
                       ses=ses[i + 1], risk=loss * qty, t=bars[i + 1]["t"],
                       delta=d)
    return trades, geo


def stats(trades, equity0):
    if not trades:
        return None
    pnl = [t["pnl"] for t in trades]
    w = sum(x for x in pnl if x > 0)
    l = -sum(x for x in pnl if x <= 0)
    eq, peak, dd = equity0, equity0, 0.0
    for x in pnl:
        eq += x
        peak = max(peak, eq)
        dd = max(dd, (peak - eq) / peak)
    wins = [x for x in pnl if x > 0]
    losses = [-x for x in pnl if x <= 0]
    return dict(n=len(pnl), pf=(w / l) if l else float("inf"),
                win=100.0 * len(wins) / len(pnl), net=sum(pnl),
                med=statistics.median(pnl), final=equity0 + sum(pnl),
                dd=dd * 100,
                avg_w=statistics.mean(wins) if wins else 0.0,
                avg_l=statistics.mean(losses) if losses else 0.0,
                rr=(statistics.mean(wins) / statistics.mean(losses))
                   if wins and losses else float("nan"),
                risk_sd=statistics.pstdev([t["risk"] for t in trades])
                        if len(trades) > 1 else 0.0,
                risk_mean=statistics.mean([t["risk"] for t in trades]))


# ── harness ──────────────────────────────────────────────────────────────
SYMS = ("SPY", "VIX"), ("QQQ", "VXN"), ("ES", "VIX")
BASE = dict(dte=0, delta=0.50, iv_mult=1.0, hold=45 * 60, sp_mult=1.0,
            equity=100_000.0, max_prem=0.25)
BASE["risk_$"] = 1000.0


def month_window(bars, year, month):
    """Bar index range covering one calendar month.

    The profile STATE is built on the whole series so the first session of the
    month still has a prior session behind it. Only the trading is windowed --
    warming up inside the window would hand the month a few sessions with no
    levels and call that a result.
    """
    lo = hi = None
    for i, b in enumerate(bars):
        d = dt.datetime.utcfromtimestamp(b["t"])
        if d.year == year and d.month == month:
            if lo is None:
                lo = i
            hi = i + 1
    return lo, hi


def signals_for(st, name):
    if name == "dva_edge_fade":
        # Part 1's best profile-only signal. It has no stop of its own, so it
        # borrows the structure the pure setups use: one row past the bar
        # that pierced the edge.
        out = []
        for i in range(st["n"]):
            vah, val, row = st["dvah"][i], st["dval"][i], st["row"][i]
            b = st["bars"][i]
            if vah is None or row is None:
                out.append(None); continue
            if b["h"] > vah and b["c"] < vah:
                out.append((-1, b["h"] + row, None))
            elif b["l"] < val and b["c"] > val:
                out.append((1, b["l"] - row, None))
            else:
                out.append(None)
        return out
    fn = P.REGISTRY[name]
    return [fn(st, i) for i in range(st["n"])]


def control(st, plan, vol, cfg, spec, count, lo, hi, seed, draws=200):
    """Random timing and direction, the strategy's own stop distances."""
    dists = [abs(st["bars"][i]["c"] - p[1]) for i, p in enumerate(plan)
             if p is not None and p[1] is not None and lo <= i < hi]
    if not dists or count < 5:
        return None
    rng = random.Random(seed)
    out = []
    for _ in range(draws):
        rp = [None] * st["n"]
        for i in range(lo, min(hi, st["n"] - 1)):
            sd = rng.choice((-1, 1))
            c = st["bars"][i]["c"]
            rp[i] = (sd, c - sd * dists[rng.randrange(len(dists))], None)
        tr, _ = run_options(st, rp, vol, cfg, lo, hi, spec)
        rng.shuffle(tr)
        tr = tr[:count]
        if len(tr) < count:
            continue
        pnl = [t["pnl"] for t in tr]
        w = sum(x for x in pnl if x > 0); l = -sum(x for x in pnl if x <= 0)
        out.append((w / l) if l else float("inf"))
    if len(out) < draws // 3:
        return None
    out.sort()
    return out


def run_all(st, vols, sigs, nm, cfg, win):
    allt, counts = [], {}
    for sym, _ in SYMS:
        lo, hi = win[sym]
        if lo is None:
            continue
        tr, _ = run_options(st[sym], sigs[sym][nm], vols[sym], cfg, lo, hi,
                            CONTRACT[sym])
        counts[sym] = len(tr)
        for t in tr:
            t["sym"] = sym
        allt += tr
    allt.sort(key=lambda t: t["t_in"])
    return allt, counts


def main():
    data, voldir = sys.argv[1], sys.argv[2]
    year = int(sys.argv[3]) if len(sys.argv) > 3 else 2026
    month = int(sys.argv[4]) if len(sys.argv) > 4 else 8
    st, vols, win = {}, {}, {}
    for sym, vx in SYMS:
        st[sym] = P.state(json.load(open(os.path.join(data, f"{sym}.json"))))
        vols[sym] = json.load(open(os.path.join(voldir, f"{vx}.json")))
        win[sym] = month_window(st[sym]["bars"], year, month)

    names = ["dva_edge_fade"] + list(P.REGISTRY)
    sigs = {sym: {nm: signals_for(st[sym], nm) for nm in names} for sym in st}

    print(f"SPY + QQQ + ES, 0DTE bought options, 1:2 on the underlying, "
          f"$100k, 1% risk")
    print(f"window: {year}-{month:02d} only")
    for sym, _ in SYMS:
        lo, hi = win[sym]
        ses = len({dt.datetime.utcfromtimestamp(b["t"]).date()
                   for b in st[sym]["bars"][lo:hi]}) if lo is not None else 0
        c = CONTRACT[sym]
        print(f"  {sym:<4} {ses:>3} sessions, {hi - lo:>5} bars   "
              f"x{c['mult']:.0f}/pt, {c['step']:.0f}-pt strikes, "
              f"{c['spread']} spread, ${c['comm']}/side")
    print()
    print(f"{'setup':<20}{'n':>5}{'PF':>7}{'win%':>6}{'net $':>10}{'final $':>10}"
          f"{'maxDD%':>8}{'med $':>8}{'optRR':>7}{'ctl95':>7}{'pct':>6}")
    rows = []
    for nm in names:
        allt, counts = run_all(st, vols, sigs, nm, dict(BASE), win)
        s = stats(allt, BASE["equity"])
        if s is None:
            print(f"{nm:<20}   no trades"); continue
        dists = []
        for sym, _ in SYMS:
            lo, hi = win[sym]
            if lo is None or counts.get(sym, 0) < 5:
                continue
            d = control(st[sym], sigs[sym][nm], vols[sym], dict(BASE),
                        CONTRACT[sym], counts[sym], lo, hi,
                        seed=abs(hash((nm, sym))) % 10 ** 6)
            if d:
                dists.append(d)
        c95 = pct = float("nan")
        if dists:
            merged = sorted(sum(v) / len(v) for v in zip(*dists))
            c95 = merged[int(len(merged) * 0.95)]
            pct = 100.0 * sum(1 for v in merged if v < s["pf"]) / len(merged)
        rows.append(dict(setup=nm, per_sym=counts, **s, c95=c95, pct=pct))
        print(f"{nm:<20}{s['n']:>5}{s['pf']:>7.3f}{s['win']:>6.1f}"
              f"{s['net']:>10,.0f}{s['final']:>10,.0f}{s['dd']:>8.1f}"
              f"{s['med']:>8,.0f}{s['rr']:>7.2f}{c95:>7.2f}{pct:>6.1f}",
              flush=True)

    print(f"\n== per instrument ==")
    print(f"{'setup':<20}{'SPY n':>7}{'SPY $':>10}{'QQQ n':>7}{'QQQ $':>10}"
          f"{'ES n':>7}{'ES $':>10}")
    for nm in names:
        allt, counts = run_all(st, vols, sigs, nm, dict(BASE), win)
        cells = []
        for sym, _ in SYMS:
            t = [x for x in allt if x["sym"] == sym]
            cells.append(f"{len(t):>7}")
            cells.append(f"{sum(x['pnl'] for x in t):>10,.0f}")
        print(f"{nm:<20}{''.join(cells)}")

    json.dump(rows, open(os.path.join(data, f"vp_opt_{year}{month:02d}.json"),
                         "w"), indent=1, default=str)
    return st, vols, sigs, names, win


def sweep(st, vols, sigs, names, win):
    """The assumptions that are not measurements, moved one at a time."""
    axes = (("iv_mult", (0.7, 0.85, 1.0, 1.25, 1.5)),
            ("delta", (0.60, 0.50, 0.40, 0.30)),
            ("sp_mult", (0.5, 1.0, 2.0, 4.0)))
    for axis, vals in axes:
        print(f"\n== {axis} ==   (net $ on a $100k start)")
        print(f"{'setup':<20}" + "".join(f"{v:>10}" for v in vals))
        for nm in names:
            cells = []
            for v in vals:
                cfg = dict(BASE)
                cfg[axis] = v
                allt, _ = run_all(st, vols, sigs, nm, cfg, win)
                s = stats(allt, BASE["equity"])
                cells.append(f"{s['net']:>10,.0f}" if s else f"{'-':>10}")
            print(f"{nm:<20}{''.join(cells)}", flush=True)


if __name__ == "__main__":
    _st, _vols, _sigs, _names, _win = main()
    if "sweep" in sys.argv:
        sweep(_st, _vols, _sigs, _names, _win)
