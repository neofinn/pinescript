"""Kronos for direction, supply/demand for the stop. Nothing else.

This is the narrow hypothesis the rest of the project kept failing to be. One
signal, one filter, twelve cells instead of a hundred and sixty:

  DIRECTION   the sign of Kronos's predicted return over its 12-bar horizon.
              Magnitude is used only as an optional threshold, never to size.
  STOP        the nearest live opposing supply/demand zone. The zone is where
              the idea is wrong, which is what a stop is for, and it means the
              stop is structural rather than a number picked to fit.
  GATE        room: if the nearest opposing zone sits closer than the target,
              the trade has nowhere to go and is skipped.

Why so few cells: over this project a 160-cell grid beat random in zero windows
out of five, and its maximum grew with the data at the same rate random's did.
Twelve cells at 149 forecasts is a test. A hundred and sixty would not be.

CONTAMINATION. The hourly forecasts run 2025-09-10 to 2026-09-24, all after the
weights were frozen on 2025-09-09, so the model never saw these outcomes.
"""
from __future__ import annotations
import datetime as dt
import itertools, json, os, random, statistics, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import zones as Z
from india_options import SPEC, expiry_dates, sessions, YEAR, CLOSE_UTC
from nifty_sept_atm import price, atm_strike

CAP0 = 500_000.0
SL = 0.05          # 5% of live equity, the hard per-trade cap
MIN_STOP_FRAC = 0.0015   # a stop closer than 0.15% of price is noise, not structure


def build_plan(bars, fc, zn, thresh, rr, use_gate):
    """One entry per forecast, if it qualifies. Returns plan aligned to bars."""
    idx = {f["i"]: f for f in fc}
    plan = [None] * len(bars)
    for i, f in idx.items():
        if i >= len(bars) - 1:
            continue
        last = f["last_close"]
        pred = (f["p_close"][-1] - last) / last
        if abs(pred) < thresh:
            continue
        sd = 1 if pred > 0 else -1
        c = bars[i]["c"]
        # stop at the nearest opposing zone; if none, skip rather than invent
        if sd > 0:
            edge = Z.support_below(zn, i, c)
        else:
            edge = Z.overhead_supply(zn, i, c)
        if edge is None:
            continue
        dist = edge
        if dist < c * MIN_STOP_FRAC:
            continue
        stop = c - sd * dist
        if use_gate:
            r = Z.room(zn, i, c, sd)
            if r is not None and r < dist * rr:
                continue
        plan[i] = (sd, stop, None)
    return plan


def run(bars, plan, vix, spec, rr, lo, hi, sl=SL, hold=10_000):
    # india_options.sessions() yields (date, [bar indices]), not bare indices
    ss = sessions(bars)
    ses_idx, day_of = {}, {}
    for k, (day, idxs) in enumerate(ss):
        for i in idxs:
            ses_idx[i] = k
            day_of[i] = day
    exp = expiry_dates([day for day, _ in ss], spec)
    rt = spec["cost"].round_trip_frac()
    lot, spread = spec["lot"], spec["spread"]
    eq = CAP0
    pos, tr = None, []
    for i in range(lo, min(hi, len(bars) - 1)):
        bb = bars[i]
        if pos is not None:
            t = max(0.0, (pos["expiry"] - bb["t"]) / YEAR)
            adverse = bb["l"] if pos["call"] else bb["h"]
            worst = price(pos["call"], adverse, pos["k"], t, pos["iv"])
            cost_at = lambda px: (rt * (pos["prem"] + px) * 0.5 * lot * pos["qty"]
                                  + spread * lot * pos["qty"])
            mtm = (worst - pos["prem"]) * lot * pos["qty"] - cost_at(worst)
            spot = None
            if mtm <= -pos["limit"]:
                spot = adverse
            else:
                sd = pos["side"]
                hs = bb["l"] <= pos["stop"] if sd > 0 else bb["h"] >= pos["stop"]
                ht = bb["h"] >= pos["targ"] if sd > 0 else bb["l"] <= pos["targ"]
                if hs:
                    spot = pos["stop"]
                elif ht:
                    spot = pos["targ"]
                elif ses_idx[i] != pos["ses"] or i - pos["i"] >= hold:
                    spot = bb["c"]
            if spot is not None:
                px = price(pos["call"], spot, pos["k"], t, pos["iv"])
                pnl = max((px - pos["prem"]) * lot * pos["qty"] - cost_at(px),
                          -pos["limit"])
                tr.append(pnl)
                eq = max(0.0, eq + pnl)
                pos = None
        if pos is None and eq > 0 and plan[i] is not None:
            sd, stop = plan[i][0], plan[i][1]
            e = bars[i + 1]["o"]
            if sd * (e - stop) <= 0:
                continue
            d = day_of.get(i + 1)
            xd = exp.get(d)
            if xd is None:
                continue
            expiry = int(dt.datetime(xd.year, xd.month, xd.day).timestamp()) + CLOSE_UTC
            t0 = (expiry - bars[i + 1]["t"]) / YEAR
            if t0 <= 0:
                continue
            iv = vix.get(str(d), 14.0) / 100.0 * spec["iv_k"]
            call = sd > 0
            k = atm_strike(e, spec["step"])
            prem = price(call, e, k, t0, iv)
            if prem <= spread:
                continue
            limit = sl * eq
            r = abs(e - stop)
            t_then = max(0.0, t0 - 2700 / YEAR)
            loss = ((prem - price(call, stop, k, t_then, iv)) * lot
                    + rt * prem * lot + spread * lot)
            if loss <= 0:
                continue
            qty = min(int(limit // loss), int(eq // (prem * lot)))
            if qty < 1:
                continue
            pos = dict(side=sd, stop=stop, targ=e + sd * rr * r, k=k, iv=iv,
                       call=call, prem=prem, qty=qty, expiry=expiry,
                       ses=ses_idx[i + 1], i=i + 1, limit=limit)
    return tr, eq


def stats(tr, eq):
    if not tr:
        return None
    e = peak = CAP0
    dd = 0.0
    for x in tr:
        e += x
        peak = max(peak, e)
        dd = max(dd, (peak - e) / peak)
    w = sum(x for x in tr if x > 0)
    l = -sum(x for x in tr if x <= 0)
    return dict(n=len(tr), final=eq, pf=(w / l) if l else float("inf"),
                dd=dd * 100,
                win=100.0 * sum(1 for x in tr if x > 0) / len(tr))


def shuffled_forecasts(fc, seed):
    """The decisive control: keep every entry time, stop and gate exactly as
    they are, and SHUFFLE ONLY THE PREDICTED DIRECTIONS between them. If the
    result survives that, Kronos's direction carried something. If it does not,
    the trades were made by the zones and the calendar."""
    rng = random.Random(seed)
    preds = [(f["p_close"][-1] - f["last_close"]) / f["last_close"] for f in fc]
    rng.shuffle(preds)
    out = []
    for f, p in zip(fc, preds):
        g = dict(f)
        g["p_close"] = list(f["p_close"])
        g["p_close"][-1] = f["last_close"] * (1 + p)
        out.append(g)
    return out


def main():
    d = sys.argv[1]
    vix = {}
    for b in json.load(open(os.path.join(d, "live", "INDIAVIX.json"))):
        k = str(dt.datetime.utcfromtimestamp(b["t"]).date())
        if k not in vix:
            vix[k] = b["c"]
    spec = SPEC["NIFTY"]
    print(f"KRONOS direction + SUPPLY/DEMAND stop. Nothing else.")
    print(f"Rs {CAP0:,.0f}, {SL:.0%} hard cap per trade, ATM options\n")

    jobs = [("H1  (149 forecasts, Sep 2025 - Sep 2026)",
             os.path.join(d, "htf", "NIFTY_h1.json"),
             os.path.join(d, "htf_fc", "NIFTY_h1.json")),
            ("M15 (78 forecasts, Aug - Sep 2026)",
             os.path.join(d, "htf", "NIFTY_m15.json"),
             os.path.join(d, "htf_fc", "NIFTY_m15.json"))]

    for name, barp, fcp in jobs:
        bars = json.load(open(barp))
        fc = json.load(open(fcp))
        zn = Z.find_zones(bars)
        lo = min(f["i"] for f in fc)
        hi = len(bars)
        med = statistics.median(
            abs((f["p_close"][-1] - f["last_close"]) / f["last_close"]) for f in fc)
        print(f"===== {name} =====")
        print(f"  {len(zn)} zones; median |predicted move| {med * 100:.3f}%")
        print(f"  {'thresh':<10}{'RR':>5}{'gate':>6}{'n':>5}{'final Rs':>13}"
              f"{'x':>7}{'PF':>7}{'win%':>7}{'maxDD%':>8}"
              f"{'shuffled median':>17}{'pct':>6}")
        cells = []
        for thresh, tlab in ((0.0, "none"), (med, "median")):
            for rr in (1.5, 2.0, 3.0):
                for gate in (False, True):
                    plan = build_plan(bars, fc, zn, thresh, rr, gate)
                    tr, eq = run(bars, plan, vix, spec, rr, lo, hi)
                    s = stats(tr, eq)
                    if s is None or s["n"] < 15:
                        print(f"  {tlab:<10}{rr:>5.1f}{str(gate):>6}"
                              f"{(s['n'] if s else 0):>5}   below 15 trades")
                        continue
                    # direction-shuffled control, same cell
                    sh = []
                    for k in range(40):
                        f2 = shuffled_forecasts(fc, 4000 + k)
                        p2 = build_plan(bars, f2, zn, thresh, rr, gate)
                        t2, e2 = run(bars, p2, vix, spec, rr, lo, hi)
                        if len(t2) >= 10:
                            sh.append(e2)
                    sh.sort()
                    pct = (100.0 * sum(1 for x in sh if x < s["final"]) / len(sh)
                           if sh else float("nan"))
                    smed = f"{statistics.median(sh):,.0f}" if sh else "-"
                    cells.append((s, pct))
                    print(f"  {tlab:<10}{rr:>5.1f}{str(gate):>6}{s['n']:>5}"
                          f"{s['final']:>13,.0f}{s['final'] / CAP0:>7.2f}"
                          f"{s['pf']:>7.2f}{s['win']:>7.1f}{s['dd']:>8.1f}"
                          f"{smed:>17}{pct:>6.0f}", flush=True)
        if cells:
            good = sum(1 for _, p in cells if p >= 95)
            print(f"  cells above the 95th percentile of their own "
                  f"direction-shuffled control: {good}/{len(cells)}\n")


if __name__ == "__main__":
    main()
