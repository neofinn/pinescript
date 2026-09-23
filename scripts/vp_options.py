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
STRIKE_STEP = 1.0               # SPY and QQQ both list $1 strikes


def price(is_call, s, k, t, iv):
    return bs_call(s, k, t, iv, RF) if is_call else bs_put(s, k, t, iv, RF)


def delta_of(is_call, s, k, t, iv):
    return (bs_delta_call(s, k, t, iv, RF) if is_call
            else bs_delta_put(s, k, t, iv, RF))


def pick_strike(is_call, s, t, iv, target):
    """Nearest listed strike to the target delta, searched outward from ATM."""
    best = None
    base = round(s / STRIKE_STEP) * STRIKE_STEP
    for i in range(-40, 41):
        k = base + i * STRIKE_STEP
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


def run_options(st, plan, vol, cfg, lo, hi):
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
                gross = (px - pos["prem"]) * 100 * pos["qty"]
                cost = (cfg["spread"] * 100 + cfg["comm"] * 2) * pos["qty"]
                trades.append(dict(pnl=gross - cost, why=why, qty=pos["qty"],
                                   prem=pos["prem"] * 100 * pos["qty"],
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
            k, d = pick_strike(call, e, t0, iv, cfg["delta"])
            prem = price(call, e, k, t0, iv)
            if prem <= 0.02:                 # unquotable; a real book has none
                geo += 1
                continue
            # ex-ante loss at the stop, after an ASSUMED hold. Entry-time
            # information only -- using the real hold would be look-ahead.
            t_then = max(0.0, t0 - cfg["hold"] / YEAR)
            px_stop = price(call, stop, k, t_then, iv)
            loss = (prem - px_stop) * 100 + cfg["spread"] * 100 + cfg["comm"] * 2
            if loss <= 0:
                geo += 1
                continue
            qty = int(cfg["risk_$"] // loss)
            cap = int(cfg["equity"] * cfg["max_prem"] // (prem * 100))
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
SYMS = ("SPY", "VIX"), ("QQQ", "VXN")
BASE = dict(dte=0, delta=0.50, iv_mult=1.0, hold=45 * 60, spread=0.02,
            comm=0.65, risk_="", equity=100_000.0, max_prem=0.25)
BASE["risk_$"] = 1000.0


def signals_for(st, name):
    if name == "dva_edge_fade":
        # Part 1's best profile-only signal, carried over for comparison.
        # It has no stop of its own, so it borrows the structure the pure
        # setups use: one row past the bar that pierced the edge.
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


def control(st, plan, vol, cfg, count, seed, draws=200):
    """Random timing and direction, the strategy's own stop distances."""
    dists = []
    for i, p in enumerate(plan):
        if p is not None and p[1] is not None:
            dists.append(abs(st["bars"][i]["c"] - p[1]))
    if not dists or count < 5:
        return None
    rng = random.Random(seed)
    out = []
    for _ in range(draws):
        rp = [None] * st["n"]
        for i in range(st["n"] - 1):
            sd = rng.choice((-1, 1))
            c = st["bars"][i]["c"]
            rp[i] = (sd, c - sd * dists[rng.randrange(len(dists))], None)
        tr, _ = run_options(st, rp, vol, cfg, 0, st["n"])
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


def main():
    data = sys.argv[1]
    voldir = sys.argv[2]
    st, vols = {}, {}
    for sym, vx in SYMS:
        st[sym] = P.state(json.load(open(os.path.join(data, f"{sym}.json"))))
        vols[sym] = json.load(open(os.path.join(voldir, f"{vx}.json")))

    names = ["dva_edge_fade"] + list(P.REGISTRY)
    sigs = {sym: {nm: signals_for(st[sym], nm) for nm in names} for sym in st}

    print("SPY + QQQ, bought options, 1:2 on the underlying, $100k, 1% risk")
    print(f"base: 0DTE, {BASE['delta']:.2f} delta, IV = VIX/VXN, "
          f"${BASE['spread']:.2f} spread, ${BASE['comm']:.2f}/contract\n")
    print(f"{'setup':<20}{'n':>5}{'PF':>7}{'win%':>6}{'net $':>10}{'final $':>10}"
          f"{'maxDD%':>8}{'med $':>8}{'opt RR':>8}{'ctl95':>7}{'pct':>6}")
    rows = []
    for nm in names:
        allt, counts = [], {}
        for sym, _ in SYMS:
            cfg = dict(BASE)
            tr, geo = run_options(st[sym], sigs[sym][nm], vols[sym], cfg,
                                  0, st[sym]["n"])
            counts[sym] = len(tr)
            allt += tr
        allt.sort(key=lambda t: t["t_in"])
        s = stats(allt, BASE["equity"])
        if s is None:
            print(f"{nm:<20}   no trades"); continue
        dist = []
        for sym, _ in SYMS:
            d = control(st[sym], sigs[sym][nm], vols[sym], dict(BASE),
                        counts[sym], seed=abs(hash((nm, sym))) % 10**6)
            if d:
                dist.append(d)
        c95 = pct = float("nan")
        if len(dist) == 2:
            merged = sorted((a + b) / 2 for a, b in zip(dist[0], dist[1]))
            c95 = merged[int(len(merged) * 0.95)]
            pct = 100.0 * sum(1 for v in merged if v < s["pf"]) / len(merged)
        rows.append(dict(setup=nm, **s, c95=c95, pct=pct))
        print(f"{nm:<20}{s['n']:>5}{s['pf']:>7.3f}{s['win']:>6.1f}"
              f"{s['net']:>10,.0f}{s['final']:>10,.0f}{s['dd']:>8.1f}"
              f"{s['med']:>8,.0f}{s['rr']:>8.2f}{c95:>7.2f}{pct:>6.1f}",
              flush=True)
    json.dump(rows, open(os.path.join(data, "vp_options.json"), "w"),
              indent=1, default=str)
    return st, vols, sigs, names




def sweep(st, vols, sigs, names):
    """The assumptions that are not measurements, moved one at a time.

    IV matters most and is the least pinned down: VIX and VXN are 30-day
    implied vols and these are same-day options. Real 0DTE at-the-money IV
    runs below the 30-day figure on quiet days and far above it around events,
    so a result that only survives at one multiplier is a result about the
    multiplier.
    """
    axes = (("iv_mult", (0.7, 0.85, 1.0, 1.25, 1.5)),
            ("dte", (0, 1, 2, 5)),
            ("delta", (0.60, 0.50, 0.40, 0.30)),
            ("spread", (0.01, 0.02, 0.05, 0.10)))
    for axis, vals in axes:
        print(f"\n== {axis} ==")
        head = "".join(f"{v:>9}" for v in vals)
        print(f"{'setup':<20}{head}      (net $, 100k start)")
        for nm in names:
            cells = []
            for v in vals:
                cfg = dict(BASE)
                cfg[axis] = v
                allt = []
                for sym, _ in SYMS:
                    tr, _ = run_options(st[sym], sigs[sym][nm], vols[sym],
                                        cfg, 0, st[sym]["n"])
                    allt += tr
                s = stats(allt, BASE["equity"])
                cells.append(f"{s['net']:>9,.0f}" if s else f"{'-':>9}")
            print(f"{nm:<20}{''.join(cells)}", flush=True)


def risk_report(st, vols, sigs, names):
    """An option position sized to lose $1,000 does not lose $1,000."""
    print(f"\n== realised risk vs the $1,000 intended ==")
    print(f"{'setup':<20}{'mean $':>9}{'sd $':>8}{'p90 $':>8}{'worst $':>9}"
          f"{'>2x':>6}{'qty med':>9}")
    for nm in names:
        losses, qty = [], []
        for sym, _ in SYMS:
            tr, _ = run_options(st[sym], sigs[sym][nm], vols[sym], dict(BASE),
                                0, st[sym]["n"])
            losses += [-t["pnl"] for t in tr if t["pnl"] < 0]
            qty += [t["qty"] for t in tr]
        if not losses:
            continue
        losses.sort()
        over = 100.0 * sum(1 for x in losses if x > 2000) / len(losses)
        print(f"{nm:<20}{statistics.mean(losses):>9,.0f}"
              f"{statistics.pstdev(losses):>8,.0f}"
              f"{losses[int(len(losses) * 0.9)]:>8,.0f}{losses[-1]:>9,.0f}"
              f"{over:>5.0f}%{statistics.median(qty):>9.0f}")


if __name__ == "__main__":
    _st, _vols, _sigs, _names = main()
    if len(sys.argv) > 3 and sys.argv[3] == "sweep":
        risk_report(_st, _vols, _sigs, _names)
        sweep(_st, _vols, _sigs, _names)
