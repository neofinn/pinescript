"""VWAP as an instrument SCREENER across the top 20 NIFTY-50 F&O names.

This is a different use of VWAP from the one that failed earlier. There it was a
per-trade filter on a single instrument, and it was provably redundant -- the
winning signal already fired only above VWAP, 449 times out of 449. Here VWAP
does not filter trades at all. It CHOOSES WHICH INSTRUMENT to look at, which is
information the single-instrument test could not contain.

The screen runs once per session, at the second hourly bar, so VWAP has data
behind it and the choice is made early enough to trade the rest of the day. It
ranks the 20 names by (close - VWAP) / VWAP and takes the most extended in each
direction. Kronos is then asked only about those, which is also what makes the
compute possible: four forecasts a session instead of twenty.

CONTRACT SPECS ARE DERIVED, NOT LOOKED UP. NSE sets stock F&O lot sizes so a
contract is worth roughly Rs 7.5 lakh, so lot = round(750000 / price) and the
strike ladder is about 2.5% of price. Real lot sizes are revised periodically
and differ from this; every rupee below inherits that approximation.
"""
from __future__ import annotations
import datetime as dt
import json, os, statistics, sys


def session_vwap(bars):
    out = [None] * len(bars)
    cpv = cv = 0.0
    day = None
    for i, b in enumerate(bars):
        d = dt.datetime.utcfromtimestamp(b["t"]).date()
        if d != day:
            cpv = cv = 0.0
            day = d
        v = b["v"] or 0
        cpv += (b["h"] + b["l"] + b["c"]) / 3.0 * v
        cv += v
        out[i] = cpv / cv if cv > 0 else None
    return out


def sessions_idx(bars):
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


def lot_for(price, target=750_000.0):
    return max(1, round(target / price))


def strike_step(price):
    """NSE's ladder is coarse and price-banded; 2.5% rounded to a clean number."""
    raw = price * 0.025
    for s in (1, 2.5, 5, 10, 20, 25, 50, 100, 200, 250, 500):
        if raw <= s:
            return float(s)
    return 1000.0


def screen(data, bar_in_session=1, pick=2, year=2026):
    """-> list of (date, symbol, bar index in that symbol, side_hint, ext)

    side_hint is only which end of the ranking the name came from. It is NOT a
    trade direction -- Kronos supplies that, and it is allowed to disagree.
    """
    vw = {s: session_vwap(b) for s, b in data.items()}
    ses = {s: sessions_idx(b) for s, b in data.items()}
    by_day = {}
    for s, sl in ses.items():
        for day, idxs in sl:
            if day.year != year or len(idxs) <= bar_in_session:
                continue
            i = idxs[bar_in_session]
            v = vw[s][i]
            if v is None or v <= 0:
                continue
            by_day.setdefault(day, []).append(
                (s, i, (data[s][i]["c"] - v) / v))
    out = []
    for day in sorted(by_day):
        row = sorted(by_day[day], key=lambda x: x[2])
        for s, i, e in row[-pick:]:
            out.append((day, s, i, +1, e))
        for s, i, e in row[:pick]:
            out.append((day, s, i, -1, e))
    return out


# absolute, because this is imported from other working directories
_INTRA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "scripts", "intra")


def load_top20(d, src=None):
    src = src or _INTRA
    syms = json.load(open(os.path.join(d, "top20.json")))
    data = {}
    for s in syms:
        p = os.path.join(src, f"{s}.json")
        if os.path.exists(p):
            data[s] = json.load(open(p))
    return data


if __name__ == "__main__":
    d = sys.argv[1]
    data = load_top20(d)
    hits = screen(data)
    print(f"{len(data)} names loaded")
    days = sorted({h[0] for h in hits})
    print(f"screen fires {len(hits)} times over {len(days)} sessions "
          f"({days[0]} .. {days[-1]})")
    from collections import Counter
    c = Counter(h[1] for h in hits)
    print("most-screened names:", ", ".join(f"{k} {v}" for k, v in c.most_common(6)))
    ext = [abs(h[4]) for h in hits]
    print(f"median |extension from VWAP| when picked: {statistics.median(ext)*100:.2f}%")
    json.dump([[str(a), b, c_, s, e] for a, b, c_, s, e in hits],
              open(os.path.join(d, "fno_screen.json"), "w"))
