"""Previous-day high / low breaks: every combination, measured.

The state space of a session relative to yesterday's range is small and
finite, so it can be enumerated rather than sampled:

    NONE   neither level broken -- an inside day
    H      only the previous day's HIGH broke
    L      only the previous day's LOW broke
    HL     the high broke first, then the low  (failed breakout)
    LH     the low broke first, then the high  (failed breakdown)

One causality rule governs everything here and it is easy to get wrong:

    at the moment PDH breaks you know whether PDL ALREADY broke today.
    you do NOT know whether it will break later.

So "first break" and "second break" are tradeable conditions, while "only one
side broke all day" is a classification that needs the end of the session and
can never be a filter. The H and L states are reported as base rates only; no
strategy below is allowed to condition on them.

That leaves eight causal combinations -- first/second break, high/low side,
follow/fade -- and each is run at several stops and targets.

Fills: the break level, or the bar's OPEN if the bar gapped through it. A bar
touching both stop and target is scored a loss. Costs in basis points.
"""
from __future__ import annotations
import datetime as dt


def sessions(bars):
    """[(date, [indices])] in order."""
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


def day_states(bars, min_bars=4):
    """Per session: the levels, the break sequence, and the end state."""
    ses = sessions(bars)
    out = []
    for k in range(1, len(ses)):
        pday, pidx = ses[k - 1]
        day, idx = ses[k]
        if len(pidx) < min_bars or len(idx) < min_bars:
            continue
        pdh = max(bars[i]["h"] for i in pidx)
        pdl = min(bars[i]["l"] for i in pidx)
        if pdh <= pdl:
            continue
        first = second = None
        for i in idx:
            b = bars[i]
            hit_h = b["h"] >= pdh
            hit_l = b["l"] <= pdl
            if first is None:
                # a bar that takes both: the close says which one held
                if hit_h and hit_l:
                    first = ("H", i) if b["c"] >= b["o"] else ("L", i)
                    second = ("L", i) if first[0] == "H" else ("H", i)
                    break
                if hit_h:
                    first = ("H", i)
                elif hit_l:
                    first = ("L", i)
            elif second is None:
                if first[0] == "H" and hit_l:
                    second = ("L", i); break
                if first[0] == "L" and hit_h:
                    second = ("H", i); break
        state = ("NONE" if first is None else
                 first[0] if second is None else first[0] + second[0])
        out.append(dict(day=day, idx=idx, pdh=pdh, pdl=pdl,
                        first=first, second=second, state=state))
    return out


def atr(bars, n=14):
    out = [None] * len(bars)
    trs = []
    for i, b in enumerate(bars):
        p = bars[i - 1]["c"] if i else b["o"]
        trs.append(max(b["h"] - b["l"], abs(b["h"] - p), abs(b["l"] - p)))
        if i >= n:
            out[i] = sum(trs[i - n + 1:i + 1]) / n
    return out


def trade(bars, idx, i_entry, side, level, stop, rr, cost_bps, exit_eod=True):
    """One position from the break to its stop, target, or the session close."""
    b = bars[i_entry]
    sgn = 1 if side == "long" else -1
    entry = max(level, b["o"]) if sgn > 0 else min(level, b["o"])
    r = (entry - stop) * sgn
    if r <= 0:
        return None
    targ = entry + sgn * rr * r if rr else None
    rest = [j for j in idx if j >= i_entry]
    for j in rest:
        x = bars[j]
        hit_s = x["l"] <= stop if sgn > 0 else x["h"] >= stop
        hit_t = (targ is not None and
                 (x["h"] >= targ if sgn > 0 else x["l"] <= targ))
        if hit_s:                       # the loss wins an ambiguous bar
            px = stop; break
        if hit_t:
            px = targ; break
    else:
        if not exit_eod:
            return None
        px = bars[rest[-1]]["c"]
    gross = (px - entry) * sgn
    net = gross - entry * cost_bps / 10_000.0
    return dict(r=net / r, side=side, i_in=i_entry)


COMBOS = {
    # name:            (which break, side taken)
    "1st PDH break -> LONG  (follow)":  ("first_H", "long"),
    "1st PDH break -> SHORT (fade)":    ("first_H", "short"),
    "1st PDL break -> SHORT (follow)":  ("first_L", "short"),
    "1st PDL break -> LONG  (fade)":    ("first_L", "long"),
    "2nd PDH after PDL -> LONG":        ("second_H", "long"),
    "2nd PDH after PDL -> SHORT":       ("second_H", "short"),
    "2nd PDL after PDH -> SHORT":       ("second_L", "short"),
    "2nd PDL after PDH -> LONG":        ("second_L", "long"),
}


def run(bars, combo, rr=2.0, stop_mode="atr", atr_mult=1.0, cost_bps=1.0,
        states=None, atr_list=None):
    """stop_mode:
         'atr'       level -/+ atr_mult x ATR. The only mode valid for every
                     combination, so it is the default and the one used for
                     any comparison ACROSS combinations.
         'opposite'  the other previous-day level. Valid only when the trade
                     runs AWAY from that level -- i.e. the follow trades. For
                     a fade the opposite level is the TARGET, and using it as
                     a stop puts the stop at the entry price, which makes
                     every fade lose exactly 1R. That is a modelling error,
                     not a result, so it is refused here.
         'extreme'   the session's opposite extreme so far. Known at entry.
                     On a fade this is the break bar's own extreme, which is
                     very tight; reported but not used for comparison.
    """
    which, side = COMBOS[combo]
    follow = ((which[-1] == "H" and side == "long") or
              (which[-1] == "L" and side == "short"))
    if stop_mode == "opposite" and not follow:
        raise ValueError(f"{combo!r}: 'opposite' puts the stop at the entry "
                         f"price for a fade -- use 'atr'")
    st = states if states is not None else day_states(bars)
    a = atr_list if atr_list is not None else atr(bars)
    out = []
    for d in st:
        ev = d["first"] if which.startswith("first") else d["second"]
        if ev is None or ev[0] != which[-1]:
            continue
        i = ev[1]
        level = d["pdh"] if ev[0] == "H" else d["pdl"]
        pre = [j for j in d["idx"] if j <= i]
        if stop_mode == "opposite":
            stop = d["pdl"] if side == "long" else d["pdh"]
        elif stop_mode == "extreme":
            stop = (min(bars[j]["l"] for j in pre) if side == "long"
                    else max(bars[j]["h"] for j in pre))
        else:
            av = a[i] or (level * 0.005)
            stop = level - atr_mult * av if side == "long" else level + atr_mult * av
        t = trade(bars, d["idx"], i, side, level, stop, rr, cost_bps)
        if t:
            out.append(t)
    return out


def stats(trades):
    if not trades:
        return dict(n=0, tot_r=0.0, avg_r=0.0, pf=0.0, win=0.0)
    rs = [t["r"] for t in trades]
    w = sum(r for r in rs if r > 0); l = -sum(r for r in rs if r <= 0)
    return dict(n=len(rs), tot_r=sum(rs), avg_r=sum(rs) / len(rs),
                pf=(w / l if l else 99.9),
                win=100.0 * sum(1 for r in rs if r > 0) / len(rs))
