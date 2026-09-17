"""Backtest of wickless_candle.pine, replicated block-for-block in Python.

This is a REPLICATION, not the Pine script running. TradingView is the only
Pine compiler and there is none here, so the only way to get a number is to
re-implement the same logic and be explicit about the mapping. Every block
below is in the same order as the .pine file, because Pine executes top to
bottom per bar and the ordering is load-bearing: a level is set before it is
tested for invalidation, and invalidation runs before triggers, so a bar that
closes back through a level kills it rather than triggering on it.

Where the two could differ, and the choice made here:
  * entry is at the NEXT bar's open (Pine "Market next open", the default)
  * if a bar's range contains both the stop and the target, the STOP is taken.
    Intrabar order is unknowable from OHLC and the optimistic reading is how
    backtests flatter themselves. The optimistic figure is reported alongside
    so the size of that assumption is visible.
  * costs are charged in price points, both sides
"""
from __future__ import annotations
import argparse, json, math, statistics


def wilder_atr(bars, n):
    trs, atr = [], [None] * len(bars)
    for i, b in enumerate(bars):
        if i == 0:
            tr = b["h"] - b["l"]
        else:
            pc = bars[i - 1]["c"]
            tr = max(b["h"] - b["l"], abs(b["h"] - pc), abs(b["l"] - pc))
        trs.append(tr)
        if i == n - 1:
            atr[i] = sum(trs[:n]) / n
        elif i >= n:
            atr[i] = (atr[i - 1] * (n - 1) + tr) / n
    return atr


def ema(bars, n):
    out, k = [None] * len(bars), 2.0 / (n + 1)
    for i, b in enumerate(bars):
        out[i] = b["c"] if i == 0 else b["c"] * k + out[i - 1] * (1 - k)
    return out


def backtest(bars, *, tol_mode="pct", tol_pct=5.0, tol_atr=0.05, tol_ticks=0,
             tick=0.10, marubozu=False, min_body=50.0, min_range=0.5,
             atr_len=14, entry_mode="both", level_life=20, retest_tol=0.10,
             stop_buf=0.25, rr=2.0, use_be=False, allow_long=True,
             allow_short=True, use_trend=False, ema_len=50,
             cost_points=0.45, optimistic=False):
    atr = wilder_atr(bars, atr_len)
    em = ema(bars, ema_len)
    n = len(bars)

    bull_lvl = bull_top = bull_bar = None
    bear_lvl = bear_bot = bear_bar = None
    n_bull = n_bear = rej_body = rej_size = 0

    pos = None            # dict(side, entry, stop, targ, bar)
    pending = None        # dict(side, lvl)
    trades = []
    want_re = entry_mode in ("retest", "both")
    want_bk = entry_mode in ("breakout", "both")

    for i in range(n):
        b = bars[i]
        a = atr[i]

        # ── A. a pending entry fills at THIS bar's open ───────────────────
        if pending is not None and pos is None:
            side = pending["side"]
            entry = b["o"]
            raw = (pending["lvl"] - (a or 0) * stop_buf if side > 0
                   else pending["lvl"] + (a or 0) * stop_buf)
            # a stop on the wrong side of the actual fill is an instant loss
            # that looks like the strategy failing; clamp it
            stop = (min(raw, entry - tick) if side > 0
                    else max(raw, entry + tick))
            risk = abs(entry - stop)
            targ = entry + side * risk * rr
            pos = dict(side=side, entry=entry, stop=stop, targ=targ, bar=i,
                       risk=risk, be=False)
            pending = None

        # ── B. exits, intrabar on this bar ────────────────────────────────
        if pos is not None:
            s = pos["side"]
            hit_stop = (b["l"] <= pos["stop"]) if s > 0 else (b["h"] >= pos["stop"])
            hit_targ = (b["h"] >= pos["targ"]) if s > 0 else (b["l"] <= pos["targ"])
            if use_be and not pos["be"]:
                r1 = pos["entry"] + s * pos["risk"]
                reached = (b["h"] >= r1) if s > 0 else (b["l"] <= r1)
                if reached and not hit_stop:
                    pos["stop"] = pos["entry"]
                    pos["be"] = True
            px = None
            if hit_stop and hit_targ:
                px = pos["targ"] if optimistic else pos["stop"]
            elif hit_stop:
                px = pos["stop"]
            elif hit_targ:
                px = pos["targ"]
            if px is not None:
                gross = s * (px - pos["entry"])
                trades.append(dict(side=s, entry=pos["entry"], exit=px,
                                   gross=gross, net=gross - cost_points,
                                   bars=i - pos["bar"], r=gross / pos["risk"]
                                   if pos["risk"] else 0.0))
                pos = None

        if a is None:
            continue

        # ── C. detection ──────────────────────────────────────────────────
        rng = b["h"] - b["l"]
        body = abs(b["c"] - b["o"])
        lo_w = min(b["o"], b["c"]) - b["l"]
        up_w = b["h"] - max(b["o"], b["c"])
        tol = (rng * tol_pct / 100.0 if tol_mode == "pct"
               else a * tol_atr if tol_mode == "atr"
               else tick * tol_ticks)
        body_ok = rng > 0 and body >= rng * min_body / 100.0
        size_ok = rng >= a * min_range

        bull_raw = b["c"] > b["o"] and lo_w <= tol and (not marubozu or up_w <= tol)
        bear_raw = b["c"] < b["o"] and up_w <= tol and (not marubozu or lo_w <= tol)
        if bull_raw or bear_raw:
            if not body_ok:
                rej_body += 1
            elif not size_ok:
                rej_size += 1

        bull_sig = (bull_raw and body_ok and size_ok and allow_long
                    and (not use_trend or b["c"] > em[i]))
        bear_sig = (bear_raw and body_ok and size_ok and allow_short
                    and (not use_trend or b["c"] < em[i]))

        # ── D. level state, then invalidation (this order matters) ────────
        if bull_sig:
            bull_lvl, bull_top, bull_bar = b["l"], b["h"], i
            n_bull += 1
        if bear_sig:
            bear_lvl, bear_bot, bear_bar = b["h"], b["l"], i
            n_bear += 1

        if bull_lvl is not None and (b["c"] < bull_lvl or i - bull_bar > level_life):
            bull_lvl = bull_top = bull_bar = None
        if bear_lvl is not None and (b["c"] > bear_lvl or i - bear_bar > level_life):
            bear_lvl = bear_bot = bear_bar = None

        # ── E. triggers ───────────────────────────────────────────────────
        zone = a * retest_tol
        bull_re = (want_re and bull_lvl is not None and i > bull_bar
                   and b["l"] <= bull_lvl + zone and b["c"] > bull_lvl)
        bull_bk = (want_bk and bull_top is not None and i > bull_bar
                   and b["c"] > bull_top)
        bear_re = (want_re and bear_lvl is not None and i > bear_bar
                   and b["h"] >= bear_lvl - zone and b["c"] < bear_lvl)
        bear_bk = (want_bk and bear_bot is not None and i > bear_bar
                   and b["c"] < bear_bot)

        if pos is None and pending is None:
            if bull_re or bull_bk:
                pending = dict(side=1, lvl=bull_lvl)
            elif bear_re or bear_bk:
                pending = dict(side=-1, lvl=bear_lvl)

    return dict(trades=trades, n_bull=n_bull, n_bear=n_bear,
                rej_body=rej_body, rej_size=rej_size, bars=n)


def stats(res):
    t = res["trades"]
    if not t:
        return dict(n=0, win=0.0, pf=0.0, net=0.0, exp=0.0, dd=0.0, avg_r=0.0)
    wins = [x["net"] for x in t if x["net"] > 0]
    loss = [-x["net"] for x in t if x["net"] <= 0]
    eq, peak, dd = 0.0, 0.0, 0.0
    for x in t:
        eq += x["net"]
        peak = max(peak, eq)
        dd = max(dd, peak - eq)
    return dict(n=len(t), win=len(wins) / len(t) * 100.0,
                pf=(sum(wins) / sum(loss)) if loss else float("inf"),
                net=sum(x["net"] for x in t),
                exp=sum(x["net"] for x in t) / len(t),
                dd=dd, avg_r=statistics.mean(x["r"] for x in t),
                bars=statistics.mean(x["bars"] for x in t))
