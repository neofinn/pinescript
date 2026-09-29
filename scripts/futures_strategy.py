"""Kronos + supply/demand on ES and NQ futures. Same rules, no option layer.

Direction from Kronos's predicted return, stop at the nearest live opposing
supply/demand zone, target at RR x the stop distance, one position at a time per
instrument, equity compounding, a hard cap of 5% of live equity per trade.

What changed from the options version, and it is not small: profit is now
(exit - entry) x multiplier x contracts. No strike, no implied vol, no
Black-Scholes, no expiry. The assumptions left are the spread and the
commission, both published. The option runs' single largest error source is
simply absent.

Sizing uses MICROS by default. One ES with a twenty-point stop risks about
$1,000, so a $25,000 account risking 2% cannot hold even one; MES is a tenth of
that and makes the risk budget expressible. This is also what allows a real-money
stage that risks tens of dollars rather than hundreds.
"""
from __future__ import annotations
import datetime as dt
import json, os, random, statistics, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import zones as Z
from futures_engine import CONTRACT, size_for_risk


def sessions_of(bars):
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


def run(bars, fc, sym, start, rr=1.5, thresh=None, use_gate=False,
        sl_frac=0.05, spread_ticks=1.0, max_hold=24, shuffle=None,
        min_stop_frac=0.0015):
    zn = Z.find_zones(bars)
    ses = sessions_of(bars)
    ses_of, day_of = {}, {}
    for k, (day, idxs) in enumerate(ses):
        for i in idxs:
            ses_of[i] = k
            day_of[i] = day
    idx = {f["i"]: f for f in fc}
    preds = [(f["p_close"][-1] - f["last_close"]) / f["last_close"] for f in fc]
    if shuffle is not None:
        rng = random.Random(shuffle)
        rng.shuffle(preds)
    pred_of = {f["i"]: p for f, p in zip(fc, preds)}
    if thresh is None:
        thresh = statistics.median(abs(p) for p in preds)

    c = CONTRACT[sym]
    eq = start
    pos, trades = None, []
    for i in range(min(idx), len(bars) - 1):
        b = bars[i]
        if pos is not None:
            sd = pos["side"]
            hit_s = b["l"] <= pos["stop"] if sd > 0 else b["h"] >= pos["stop"]
            hit_t = b["h"] >= pos["targ"] if sd > 0 else b["l"] <= pos["targ"]
            px = None
            if hit_s:
                px = pos["stop"]
            elif hit_t:
                px = pos["targ"]
            elif i - pos["i"] >= max_hold:
                px = b["c"]
            if px is not None:
                gross = sd * (px - pos["entry"]) * c["mult"] * pos["n"]
                cost = pos["n"] * (c["comm"] + spread_ticks * c["tick"] * c["mult"])
                p = gross - cost
                # the hard cap is honoured against the SAME quantity the trade
                # was sized with, costs included, as the options version should
                # have been from the start
                p = max(p, -pos["limit"])
                trades.append((day_of[i], p))
                eq = max(0.0, eq + p)
                pos = None
        if pos is None and eq > 0 and i in pred_of:
            pr = pred_of[i]
            if abs(pr) < thresh:
                continue
            sd = 1 if pr > 0 else -1
            close = b["c"]
            edge = (Z.support_below(zn, i, close) if sd > 0
                    else Z.overhead_supply(zn, i, close))
            if edge is None or edge < close * min_stop_frac:
                continue
            if use_gate:
                room = Z.room(zn, i, close, sd)
                if room is not None and room < edge * rr:
                    continue
            entry = bars[i + 1]["o"]
            stop = close - sd * edge
            if sd * (entry - stop) <= 0:
                continue
            stop_pts = abs(entry - stop)
            limit = sl_frac * eq
            n = size_for_risk(sym, limit, stop_pts, spread_ticks)
            if n < 1:
                continue
            pos = dict(side=sd, entry=entry, stop=stop,
                       targ=entry + sd * rr * stop_pts, n=n, i=i + 1,
                       limit=limit)
    return trades, eq


def stats(trades, start):
    if not trades:
        return None
    eq = peak = start
    dd = 0.0
    for _, p in trades:
        eq += p
        peak = max(peak, eq)
        dd = max(dd, (peak - eq) / peak)
    w = sum(p for _, p in trades if p > 0)
    l = -sum(p for _, p in trades if p <= 0)
    return dict(n=len(trades), final=eq, pf=(w / l) if l else float("inf"),
                dd=dd * 100,
                win=100.0 * sum(1 for _, p in trades if p > 0) / len(trades))
