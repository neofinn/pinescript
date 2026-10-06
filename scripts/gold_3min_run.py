"""Gold on 3-minute bars: aggregate from 1m, sweep, and control.

Yahoo serves no 3-minute interval and caps 1-minute history at about a month,
so this is 22 sessions. That is the finding as much as anything else -- see
GOLD_3MIN.md, where the whole timeframe table splits by sample size rather
than by timeframe.
"""
import json, os, sys, statistics, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from inside_bar_short import aggregate
from pivot_ema import run, stats, sessions, atr

SC = os.environ.get("SCRATCH", "/tmp")

def build_m3(m1_path, out_path):
    m1 = json.load(open(m1_path))
    m3 = aggregate(m1, 3, 1)
    json.dump(m3, open(out_path, "w"))
    return m3

def sweep(bars, cost_bps=0.8, min_n=40):
    rows = []
    for opd in (True, False):
        for el in (5, 9):
            for g in ("P", "1", "2", "3"):
                for md in ("bounce", "break"):
                    for em in ("none", "aligned", "counter"):
                        for rr in (2.0, 5.0, 20.0):
                            s = stats(run(bars, group=g, mode=md, ema_mode=em,
                                          ema_len=el, target="rr", rr=rr,
                                          cost_bps=cost_bps, one_per_day=opd))
                            if s["n"] >= min_n:
                                rows.append(dict(opd=opd, el=el, g=g, md=md,
                                                 em=em, rr=rr, **s))
    return rows
