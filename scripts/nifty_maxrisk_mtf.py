"""Maximum risk, across m5 / m15 / m45 / h1. What leverage actually does.

Risk here COMPOUNDS off live equity, which is what a real account does and
what a fixed-fraction-of-opening-balance backtest hides. At 1% the difference
is cosmetic. At 50% it is the whole result, because position size after a loss
is smaller and the account cannot recover the same way it fell.

The number that matters at high risk is not the average outcome, it is the
spread of outcomes across ORDERINGS of the same trades. The trades are a set;
the sequence they arrive in is arbitrary. At low risk order barely matters. At
high risk the identical set of trades either multiplies the account or ends it
depending only on which losses land first -- so the order is bootstrapped and
the ruin frequency reported.

Ruin is defined as equity falling below 20% of the start: an account that has
lost four fifths cannot trade the same size and, for the strategies here,
is not coming back.
"""
from __future__ import annotations
import datetime as dt
import json, os, random, statistics, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import vp_of_pure as P
from india_options import SPEC, expiry_dates, sessions, YEAR, RF, CLOSE_UTC
from nifty_sept_atm import price, atm_strike, month_window
from tf_aggregate import aggregate
from vp_confluence import combine, MODES
from vp_options import signals_for

START = 500_000.0
RUIN = 0.20


def run_compounding(st, plan, vixmap, spec, rr, max_hold, expiry_only,
                    lo, hi, risk_frac, max_prem, bar_secs):
    """Same engine, but equity compounds and sizing is off LIVE equity."""
    bars, ses, n = st["bars"], st["ses"], st["n"]
    ss = sessions(bars)
    exp = expiry_dates([d for d, _ in ss], spec)
    day_of = {i: d for d, idxs in ss for i in idxs}
    rt = spec["cost"].round_trip_frac()
    lot, spread = spec["lot"], spec["spread"]
    eq = START
    trades, pos = [], None
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
            elif ses[i] != pos["ses"] or i - pos["i"] >= max_hold:
                spot = b["c"]
            if spot is not None:
                t = max(0.0, (pos["expiry"] - b["t"]) / YEAR)
                px = price(pos["call"], spot, pos["k"], t, pos["iv"])
                gross = (px - pos["prem"]) * lot * pos["qty"]
                avg = (pos["prem"] + px) * 0.5 * lot * pos["qty"]
                pnl = gross - rt * avg - spread * lot * pos["qty"]
                trades.append(pnl / pos["eq"])        # return per unit equity
                eq = max(0.0, eq + pnl)
                pos = None
        if pos is None and eq > 0 and plan[i] is not None:
            sd, stop = plan[i][0], plan[i][1]
            e = bars[i + 1]["o"]
            if stop is None or sd * (e - stop) <= 0:
                continue
            d = day_of[i + 1]
            xd = exp.get(d)
            if xd is None or (expiry_only and xd != d):
                continue
            expiry = int(dt.datetime(xd.year, xd.month, xd.day).timestamp()) + CLOSE_UTC
            t0 = (expiry - bars[i + 1]["t"]) / YEAR
            if t0 <= 0:
                continue
            iv = vixmap.get(str(d), 14.0) / 100.0 * spec["iv_k"]
            call = sd > 0
            k = atm_strike(e, spec["step"])
            prem = price(call, e, k, t0, iv)
            if prem <= spread:
                continue
            r = abs(e - stop)
            t_then = max(0.0, t0 - 45 * 60 / YEAR)
            loss = ((prem - price(call, stop, k, t_then, iv)) * lot
                    + rt * prem * lot + spread * lot)
            if loss <= 0:
                continue
            qty = min(int(eq * risk_frac // loss),
                      int(eq * max_prem // (prem * lot)))
            if qty < 1:
                continue
            pos = dict(side=sd, stop=stop, targ=e + sd * rr * r, k=k, iv=iv,
                       call=call, prem=prem, qty=qty, expiry=expiry,
                       ses=ses[i + 1], i=i + 1, eq=eq)
    return trades, eq


def bootstrap_order(rets, draws=4000, seed=5):
    """Same trades, different sequence.

    TERMINAL EQUITY DOES NOT MOVE. Under fixed-fractional compounding the final
    balance is START x prod(1 + r_i), and multiplication commutes, so every
    ordering ends in the same place. The first version of this reported median
    and percentile columns that were identical to the historical figure in
    every row -- not a bug in the shuffling, a property of the arithmetic.

    What DOES depend on order is the PATH: whether the account passes through
    a level it cannot come back from. So the shuffle measures ruin frequency
    and worst drawdown, which are order-dependent, and terminal equity is
    reported once as the single number it is.
    """
    if not rets:
        return None
    rng = random.Random(seed)
    dds, ruined = [], 0
    for _ in range(draws):
        order = rets[:]
        rng.shuffle(order)
        eq = peak = START
        low = eq
        dd = 0.0
        for r in order:
            eq = max(0.0, eq * (1 + r))
            peak = max(peak, eq)
            low = min(low, eq)
            dd = max(dd, (peak - eq) / peak)
            if eq <= 0:
                break
        dds.append(dd * 100)
        if low <= START * RUIN:
            ruined += 1
    dds.sort()
    return dict(ruin=100.0 * ruined / draws, dd_med=dds[len(dds) // 2],
                dd_worst=dds[-1])


TFS = ((5, "m5"), (15, "m15"), (45, "m45"), (60, "h1"))
RISKS = ((0.01, "1%"), (0.05, "5%"), (0.10, "10%"), (0.25, "25%"),
         (0.50, "50%"), (1.00, "100%"))
# September's best cell, held FIXED across timeframes so the comparison is the
# bar size and not another search.
CFG = dict(plan="conf2_distinct", rr=3.0, hold=24, expiry_only=True)


def main():
    d = sys.argv[1]
    base = json.load(open(os.path.join(d, "NIFTY_wv.json")))
    vix = {}
    for b in json.load(open(os.path.join(d, "INDIAVIX.json"))):
        k = str(dt.datetime.utcfromtimestamp(b["t"]).date())
        if k not in vix:
            vix[k] = b["c"]
    spec = SPEC["NIFTY"]

    print(f"NIFTY 50 ATM options, September 2026, Rs {START:,.0f} start")
    print(f"fixed rule across timeframes: {CFG['plan']}, expiry-day, "
          f"RR {CFG['rr']}, {CFG['hold']}-bar cap")
    print(f"risk compounds off LIVE equity; premium cap raised with risk\n")

    store = {}
    for mins, tf in TFS:
        bars = aggregate(base, mins)
        st = P.state(bars)
        names = ["dva_edge_fade"] + list(P.REGISTRY)
        sigs = {nm: signals_for(st, nm) for nm in names}
        plans = dict(sigs)
        for m in MODES:
            plans[m] = combine(sigs, st["n"], m)
        lo, hi = month_window(st["bars"], 2026, 9)
        if lo is None:
            continue
        store[tf] = (st, plans, lo, hi, mins)

    print(f"{'tf':<5}{'expiry':<8}{'risk':<6}{'n':>4}{'final Rs':>12}"
          f"{'x start':>9}{'medDD%':>8}{'worstDD%':>10}{'RUIN%':>8}")
    rows = []
    for mins, tf in TFS:
        if tf not in store:
            continue
        st, plans, lo, hi, _ = store[tf]
        for eo, elab in ((True, "expiry"), (False, "weekly")):
            for rf, rl in RISKS:
                cap = min(1.0, max(0.25, rf * 2))
                rets, eq = run_compounding(st, plans[CFG["plan"]], vix, spec,
                                           CFG["rr"], CFG["hold"], eo,
                                           lo, hi, rf, cap, mins * 60)
                if len(rets) < 3:
                    print(f"{tf:<5}{elab:<8}{rl:<6}{len(rets):>4}"
                          f"   too few trades to size")
                    continue
                b = bootstrap_order(rets)
                rows.append(dict(tf=tf, expiry=elab, risk=rl, n=len(rets),
                                 final=eq, **b))
                print(f"{tf:<5}{elab:<8}{rl:<6}{len(rets):>4}{eq:>12,.0f}"
                      f"{eq / START:>9.2f}{b['dd_med']:>8.1f}"
                      f"{b['dd_worst']:>10.1f}{b['ruin']:>8.1f}", flush=True)
    json.dump(rows, open(os.path.join(d, "maxrisk_mtf.json"), "w"), indent=1)

    print(f"\nTerminal equity is identical for every ordering -- compounded "
          f"returns commute.\nDrawdown and ruin are not: they are what the "
          f"4,000 reshuffles measure.\nRUIN% = share of orderings that ever "
          f"fell below {RUIN:.0%} of the start.")


if __name__ == "__main__":
    main()
