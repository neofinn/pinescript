"""Top-20 F&O stocks: VWAP screens, Kronos directs, supply/demand stops.

Rs 10,00,000 capital, 5% hard cap per trade, ATM options, same rules as the
NIFTY run. Three things differ because the instrument does, and each one
changes the trade rather than decorating it:

  MONTHLY EXPIRY ONLY. Indian single-stock options have no weekly series. The
  NIFTY work leaned heavily on expiry-day contracts, where gamma is enormous
  and premium is small; here the nearest expiry can be four weeks out, so the
  same signal buys a far more expensive and far less convex option.

  IV IS PER STOCK AND IS ESTIMATED. There is no India-VIX equivalent for single
  names, so implied vol is each stock's own realised vol over the trailing 20
  sessions, scaled by 1.15 for the volatility risk premium. That multiplier is
  an assumption and is swept.

  CONTRACT SPECS ARE DERIVED. NSE sizes stock lots to roughly Rs 7.5 lakh of
  notional, so lot = round(750000 / price) with a 2.5% strike ladder. Real lots
  are revised periodically and will differ.

The screen never sees a forecast and the forecast never sees the screen's
outcome: VWAP picks the names at the second bar of the session, Kronos is asked
only about those, and supply/demand supplies the stop.
"""
from __future__ import annotations
import datetime as dt
import itertools, json, math, os, random, statistics, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import zones as Z
from fno_vwap_screen import load_top20, lot_for, strike_step, sessions_idx
from hft.costs import NSE_MEMBER
from hft.pricing import bs_call, bs_put

CAP0 = 1_000_000.0
SL = 0.05
YEAR = 365.0 * 24 * 3600
RF = 0.065
CLOSE_UTC = 10 * 3600
MIN_STOP_FRAC = 0.002


def price(is_call, s, k, t, iv):
    return bs_call(s, k, t, iv, RF) if is_call else bs_put(s, k, t, iv, RF)


def realised_vol(bars, i, n=120):
    """Annualised, from the trailing n hourly bars. Uses only past bars."""
    lo = max(1, i - n)
    rets = [math.log(bars[j]["c"] / bars[j - 1]["c"])
            for j in range(lo, i) if bars[j - 1]["c"] > 0]
    if len(rets) < 20:
        return None
    sd = statistics.pstdev(rets)
    return sd * math.sqrt(6 * 250)          # ~6 hourly bars per NSE session


def monthly_expiry(days, weekday=1):
    """Last <weekday> of each month present in the data."""
    last = {}
    for d in days:
        if d.weekday() == weekday:
            last[(d.year, d.month)] = max(last.get((d.year, d.month), d), d)
    cand = sorted(last.values())
    out = {}
    for d in days:
        nxt = [c for c in cand if c >= d]
        out[d] = nxt[0] if nxt else None
    return out


def trade_one(bars, i, sd, stop, rr, iv_mult, eq, sl=SL):
    """One position, opened at bar i+1's open, walked to its exit."""
    e = bars[i + 1]["o"]
    if sd * (e - stop) <= 0:
        return None
    days = sorted({dt.datetime.utcfromtimestamp(b["t"]).date() for b in bars})
    exp = monthly_expiry(days)
    d = dt.datetime.utcfromtimestamp(bars[i + 1]["t"]).date()
    xd = exp.get(d)
    if xd is None:
        return None
    expiry = int(dt.datetime(xd.year, xd.month, xd.day).timestamp()) + CLOSE_UTC
    t0 = (expiry - bars[i + 1]["t"]) / YEAR
    if t0 <= 0:
        return None
    rv = realised_vol(bars, i)
    if rv is None or rv <= 0:
        return None
    iv = rv * iv_mult
    lot = lot_for(e)
    step = strike_step(e)
    k = round(e / step) * step
    call = sd > 0
    prem = price(call, e, k, t0, iv)
    spread = max(0.05, prem * 0.01)       # 1% of premium, floored at 5 paise
    if prem <= spread * 2:
        return None
    rt = NSE_MEMBER.round_trip_frac()
    limit = sl * eq
    r = abs(e - stop)
    t_then = max(0.0, t0 - 3600 / YEAR)
    loss = ((prem - price(call, stop, k, t_then, iv)) * lot
            + rt * prem * lot + spread * lot)
    if loss <= 0:
        return None
    qty = min(int(limit // loss), int(eq // (prem * lot)))
    if qty < 1:
        return None
    targ = e + sd * rr * r
    ses = sessions_idx(bars)
    ses_of = {}
    for kk, (day, idxs) in enumerate(ses):
        for j in idxs:
            ses_of[j] = kk
    start = ses_of.get(i + 1)
    for j in range(i + 1, len(bars)):
        b = bars[j]
        t = max(0.0, (expiry - b["t"]) / YEAR)
        adverse = b["l"] if call else b["h"]
        worst = price(call, adverse, k, t, iv)
        cost_at = lambda px: (rt * (prem + px) * 0.5 * lot * qty
                              + spread * lot * qty)
        mtm = (worst - prem) * lot * qty - cost_at(worst)
        spot = None
        if mtm <= -limit:
            spot = adverse
        elif (b["l"] <= stop if sd > 0 else b["h"] >= stop):
            spot = stop
        elif (b["h"] >= targ if sd > 0 else b["l"] <= targ):
            spot = targ
        elif ses_of.get(j) != start:
            spot = b["c"]
        if spot is not None:
            px = price(call, spot, k, t, iv)
            return max((px - prem) * lot * qty - cost_at(px), -limit)
    return None


def build_and_run(data, fcs, thresh, rr, use_gate, iv_mult, shuffle_dirs=None):
    """Walk the screened forecasts in date order, one position at a time."""
    zn = {s: Z.find_zones(b) for s, b in data.items()}
    rows = sorted(fcs, key=lambda r: (r["day"], r["sym"]))
    preds = [(r["p_close"][-1] - r["last_close"]) / r["last_close"] for r in rows]
    if shuffle_dirs is not None:
        rng = random.Random(shuffle_dirs)
        rng.shuffle(preds)
    eq = CAP0
    tr = []
    busy_until = None
    for r, pred in zip(rows, preds):
        if abs(pred) < thresh:
            continue
        day = dt.date.fromisoformat(r["day"])
        if busy_until is not None and day <= busy_until:
            continue                      # one position at a time
        s, i = r["sym"], r["i"]
        bars = data[s]
        if i + 2 >= len(bars):
            continue
        sd = 1 if pred > 0 else -1
        c = bars[i]["c"]
        edge = (Z.support_below(zn[s], i, c) if sd > 0
                else Z.overhead_supply(zn[s], i, c))
        if edge is None or edge < c * MIN_STOP_FRAC:
            continue
        if use_gate:
            room = Z.room(zn[s], i, c, sd)
            if room is not None and room < edge * rr:
                continue
        pnl = trade_one(bars, i, sd, c - sd * edge, rr, iv_mult, eq)
        if pnl is None:
            continue
        tr.append(pnl)
        eq = max(0.0, eq + pnl)
        busy_until = day
        if eq <= 0:
            break
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


def main():
    d = sys.argv[1]
    data = load_top20(d)
    fcs = json.load(open(os.path.join(d, "screen_forecasts.json")))
    print(f"Top-20 F&O stocks. VWAP screens, Kronos directs, "
          f"supply/demand stops.")
    print(f"Rs {CAP0:,.0f} capital, {SL:.0%} hard cap, ATM monthly options, "
          f"{len(fcs)} screened forecasts\n")
    med = statistics.median(
        abs((r["p_close"][-1] - r["last_close"]) / r["last_close"]) for r in fcs)
    print(f"median |predicted move| {med*100:.3f}%   "
          f"names screened {len({r['sym'] for r in fcs})}\n")
    print(f"{'thresh':<9}{'RR':>5}{'gate':>6}{'IVx':>6}{'n':>5}{'final Rs':>14}"
          f"{'x':>7}{'PF':>7}{'win%':>7}{'maxDD%':>8}{'shuffled med':>15}{'pct':>6}")
    cells = []
    for thresh, tl in ((0.0, "none"), (med, "median")):
        for rr in (1.5, 2.0, 3.0):
            for gate in (False, True):
                tr, eq = build_and_run(data, fcs, thresh, rr, gate, 1.15)
                s = stats(tr, eq)
                if s is None or s["n"] < 15:
                    print(f"{tl:<9}{rr:>5.1f}{str(gate):>6}{1.15:>6.2f}"
                          f"{(s['n'] if s else 0):>5}   below 15 trades")
                    continue
                sh = []
                for k in range(30):
                    t2, e2 = build_and_run(data, fcs, thresh, rr, gate, 1.15,
                                           shuffle_dirs=7000 + k)
                    if len(t2) >= 10:
                        sh.append(e2)
                sh.sort()
                pct = (100.0 * sum(1 for x in sh if x < s["final"]) / len(sh)
                       if sh else float("nan"))
                cells.append(pct)
                print(f"{tl:<9}{rr:>5.1f}{str(gate):>6}{1.15:>6.2f}{s['n']:>5}"
                      f"{s['final']:>14,.0f}{s['final']/CAP0:>7.2f}{s['pf']:>7.2f}"
                      f"{s['win']:>7.1f}{s['dd']:>8.1f}"
                      f"{statistics.median(sh) if sh else 0:>15,.0f}{pct:>6.0f}",
                      flush=True)
    if cells:
        n = len(cells)
        print(f"\ncells above the 95th percentile of their own "
              f"direction-shuffled control: {sum(1 for p in cells if p>=95)}/{n}")
        print(f"expected best of {n} draws under the null: "
              f"{100.0*n/(n+1):.1f}th percentile; observed best: {max(cells):.0f}")


if __name__ == "__main__":
    main()
