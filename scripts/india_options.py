"""Indian index options on the profile+flow plans. Two things differ from the US.

EXPIRY. There is no daily expiry to trade. SEBI's rationalisation left ONE
weekly expiry per exchange, and BANKNIFTY's weeklies were withdrawn entirely --
it is a monthly contract now. So "0DTE" in India exists on one day a week for
NIFTY and one day a month for BANKNIFTY, not every session. The weekday rules
below are parameters, not constants, because this is exactly the kind of fact
that moves; check them against your broker's contract master before relying on
a number from this file.

COST. Zero brokerage does not mean zero cost, and what is left is
PROPORTIONAL to premium rather than flat per lot. STT at 0.15% on the sell leg
is about 63% of a round trip that comes to roughly 0.24% of premium. A flat fee
would make the smallest lot worst; a proportional one makes the most expensive
option worst and drops lot size out of the arithmetic entirely.
"""
from __future__ import annotations
import datetime as dt
import json, os, statistics, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import india_volume as IV
import vp_of_pure as P
from hft.costs import NSE_MEMBER, BSE_MEMBER
from hft.pricing import bs_call, bs_put, bs_delta_call, bs_delta_put
from vp_confluence import combine
from vp_options import signals_for

YEAR = 365.0 * 24 * 3600
RF = 0.065                      # INR risk-free
CLOSE_UTC = 10 * 3600           # 15:30 IST

# lot and strike as at 2026-09; these move too
SPEC = {
    "NIFTY":     dict(lot=75,  step=50.0,  spread=0.50, iv_k=1.00,
                      expiry="weekly", weekday=1, cost=NSE_MEMBER),
    "BANKNIFTY": dict(lot=35,  step=100.0, spread=2.00, iv_k=1.15,
                      expiry="monthly", weekday=1, cost=NSE_MEMBER),
    "SENSEX":    dict(lot=20,  step=100.0, spread=2.00, iv_k=1.00,
                      expiry="weekly", weekday=3, cost=BSE_MEMBER),
}


def sessions(bars):
    out, cur, day = [], [], None
    for i, b in enumerate(bars):
        d = dt.datetime.utcfromtimestamp(b["t"]).date()
        if day is None or d != day:
            if cur:
                out.append((day, cur))
            cur, day = [], d
        cur.append(i)
    if cur:
        out.append((day, cur))
    return out


def expiry_dates(days, spec):
    """Map each session date to the expiry it would trade."""
    wd = spec["weekday"]
    cand = sorted({d for d in days if d.weekday() == wd})
    if spec["expiry"] == "monthly":
        last = {}
        for d in cand:
            last[(d.year, d.month)] = d
        cand = sorted(last.values())
    out = {}
    for d in days:
        nxt = [c for c in cand if c >= d]
        out[d] = nxt[0] if nxt else None
    return out


def price(is_call, s, k, t, iv):
    return bs_call(s, k, t, iv, RF) if is_call else bs_put(s, k, t, iv, RF)


def pick_strike(is_call, s, t, iv, target, step):
    best = None
    base = round(s / step) * step
    for i in range(-30, 31):
        k = base + i * step
        if k <= 0:
            continue
        d = (bs_delta_call(s, k, t, iv, RF) if is_call
             else bs_delta_put(s, k, t, iv, RF))
        e = abs(abs(d) - target)
        if best is None or e < best[0]:
            best = (e, k)
    return best[1]


def run(st, plan, vix, spec, cfg, lo, hi, expiry_only=False):
    bars, ses, n = st["bars"], st["ses"], st["n"]
    ss = sessions(bars)
    days = [d for d, _ in ss]
    exp = expiry_dates(days, spec)
    day_of = {}
    for d, idxs in ss:
        for i in idxs:
            day_of[i] = d
    rt = spec["cost"].round_trip_frac()
    lot = spec["lot"]
    trades, pos, geo = [], None, 0
    for i in range(lo, min(hi, n - 1)):
        b = bars[i]
        if pos is not None:
            sd = pos["side"]
            hit_s = b["l"] <= pos["stop"] if sd > 0 else b["h"] >= pos["stop"]
            hit_t = b["h"] >= pos["targ"] if sd > 0 else b["l"] <= pos["targ"]
            spot = None
            if hit_s:
                spot = pos["stop"]
            elif hit_t:
                spot = pos["targ"]
            elif ses[i] != pos["ses"]:
                spot = b["c"]
            if spot is not None:
                t = max(0.0, (pos["expiry"] - b["t"]) / YEAR)
                px = price(pos["call"], spot, pos["k"], t, pos["iv"])
                gross = (px - pos["prem"]) * lot * pos["qty"]
                # statutory stack is a fraction of PREMIUM TURNOVER, charged
                # on both legs' own prices, plus the spread crossed twice
                # round_trip_frac already covers BOTH legs, so it applies
                # once to the average premium turnover -- not once per leg
                avg_turn = (pos["prem"] + px) * 0.5 * lot * pos["qty"]
                cost = rt * avg_turn + spec["spread"] * lot * pos["qty"]
                trades.append(gross - cost)
                pos = None
        if pos is None and plan[i] is not None:
            sd, stop = plan[i][0], plan[i][1]
            e = bars[i + 1]["o"]
            if stop is None or sd * (e - stop) <= 0:
                geo += 1; continue
            d = day_of[i + 1]
            xd = exp.get(d)
            if xd is None:
                geo += 1; continue
            if expiry_only and xd != d:
                continue
            expiry = int(dt.datetime(xd.year, xd.month, xd.day).timestamp()) \
                + CLOSE_UTC
            t0 = (expiry - bars[i + 1]["t"]) / YEAR
            if t0 <= 0:
                geo += 1; continue
            iv = vix.get(str(d), 14.0) / 100.0 * spec["iv_k"] * cfg["iv_mult"]
            call = sd > 0
            k = pick_strike(call, e, t0, iv, cfg["delta"], spec["step"])
            prem = price(call, e, k, t0, iv)
            if prem <= spec["spread"]:
                geo += 1; continue
            r = abs(e - stop)
            t_then = max(0.0, t0 - cfg["hold"] / YEAR)
            px_stop = price(call, stop, k, t_then, iv)
            loss = ((prem - px_stop) * lot + rt * prem * lot
                    + spec["spread"] * lot)
            if loss <= 0:
                geo += 1; continue
            qty = int(cfg["risk"] // loss)
            cap = int(cfg["equity"] * cfg["max_prem"] // (prem * lot))
            qty = max(0, min(qty, cap))
            if qty < 1:
                geo += 1; continue
            pos = dict(side=sd, stop=stop, targ=e + sd * 2.0 * r, k=k, iv=iv,
                       call=call, prem=prem, qty=qty, expiry=expiry,
                       ses=ses[i + 1])
    return trades, geo


# ── harness ──────────────────────────────────────────────────────────────
CFG = dict(delta=0.50, iv_mult=1.0, hold=45 * 60, equity=500_000.0,
           risk=5_000.0, max_prem=0.25)
IDX = ("NIFTY", "BANKNIFTY", "SENSEX")


def stats(tr, eq0):
    if not tr:
        return None
    w = sum(x for x in tr if x > 0); l = -sum(x for x in tr if x <= 0)
    eq, peak, dd = eq0, eq0, 0.0
    for x in tr:
        eq += x; peak = max(peak, eq); dd = max(dd, (peak - eq) / peak)
    return dict(n=len(tr), pf=(w / l) if l else float("inf"),
                win=100.0 * sum(1 for x in tr if x > 0) / len(tr),
                net=sum(tr), final=eq0 + sum(tr), dd=dd * 100,
                med=statistics.median(tr))


def main():
    d = sys.argv[1]
    st, vix = {}, {}
    raw = {str(dt.datetime.utcfromtimestamp(b["t"]).date()): b["c"]
           for b in json.load(open(os.path.join(d, "INDIAVIX.json")))}
    for ix in IDX:
        st[ix] = P.state(IV.with_volume(d, ix))
        vix[ix] = raw
    names = ["dva_edge_fade"] + list(P.REGISTRY)
    sigs = {ix: {nm: signals_for(st[ix], nm) for nm in names} for ix in IDX}
    plans = {nm: {ix: sigs[ix][nm] for ix in IDX} for nm in names}
    plans["conf2_distinct"] = {ix: combine(sigs[ix], st[ix]["n"],
                                           "conf2_distinct") for ix in IDX}

    spl = {ix: st[ix]["n"] // 2 for ix in IDX}
    wins = {"IS": {ix: (0, spl[ix]) for ix in IDX},
            "OOS": {ix: (spl[ix], st[ix]["n"]) for ix in IDX}}

    for eo, lab in ((False, "nearest weekly/monthly expiry"),
                    (True, "expiry day only (India's 0DTE)")):
        print(f"\n===== {lab} =====  capital Rs 5,00,000, 1% risk")
        print(f"{'plan':<20}{'win':<5}{'n':>6}{'PF':>8}{'win%':>7}"
              f"{'net Rs':>12}{'final Rs':>12}{'maxDD%':>8}{'med Rs':>9}")
        for nm, pl in plans.items():
            for wl in ("IS", "OOS"):
                allt = []
                for ix in IDX:
                    lo, hi = wins[wl][ix]
                    tr, _ = run(st[ix], pl[ix], vix[ix], SPEC[ix], CFG,
                                lo, hi, eo)
                    allt += tr
                s = stats(allt, CFG["equity"])
                if s is None or s["n"] < 5:
                    print(f"{nm:<20}{wl:<5}{(s['n'] if s else 0):>6}"
                          f"   too few trades")
                    continue
                print(f"{nm:<20}{wl:<5}{s['n']:>6}{s['pf']:>8.3f}"
                      f"{s['win']:>7.1f}{s['net']:>12,.0f}{s['final']:>12,.0f}"
                      f"{s['dd']:>8.1f}{s['med']:>9,.0f}", flush=True)


if __name__ == "__main__":
    main()
