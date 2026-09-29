"""70/30 walk-forward: does SELECTING on recent data work?

Every test so far fixed a plan and asked whether it beat chance. That is not
what a practitioner does. A practitioner looks at recent history, picks
whatever did best, and trades it forward -- and that selection step is itself a
strategy that can be tested. This does that.

  window   30 sessions
  train    the first 70% (21 sessions) -- pick the best plan here
  test     the last 30% (9 sessions)   -- trade that pick, blind
  step     9 sessions, so test windows tile without overlap

Four comparisons, because the walk-forward number alone says nothing:

  SELECTED   what the 70/30 rule actually earns
  each plan  the same test windows, traded fixed -- did selection beat simply
             committing to one thing?
  RANDOM     a plan drawn uniformly each fold. The honest null: if selection
             cannot beat a coin choosing among the same candidates, the
             selection step is decoration.
  ORACLE     the best plan in each TEST window, chosen with hindsight. The
             ceiling, and the gap to it is what selection is failing to
             capture.

The diagnostic that matters more than any of them is the last table: the rank
correlation between how a plan does in train and how it does in the test that
follows. Selection can only work if that number is positive. If it is zero,
every walk-forward result is noise dressed as method, and no amount of
re-tuning the window sizes will change it.
"""
from __future__ import annotations
import datetime as dt
import json, os, random, statistics, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import vp_of_pure as P
from vp_confluence import combine, MODES
from vp_options import signals_for

TRAIN_FRAC = 0.70
WINDOW = 30          # sessions
STEP = 9             # = test length, so tests tile


def session_bounds(bars):
    """Bar index at the start of each session, plus the end sentinel."""
    out, day = [], None
    for i, b in enumerate(bars):
        d = dt.datetime.utcfromtimestamp(b["t"]).date()
        if d != day:
            out.append(i)
            day = d
    out.append(len(bars))
    return out


def execute(st, plan, cost, lo, hi):
    """Entry next open, profile stop, target at twice the stop distance."""
    bars, ses, n = st["bars"], st["ses"], st["n"]
    trades, risks, pos = [], [], None
    for i in range(lo, min(hi, n - 1)):
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
            elif ses[i] != pos["ses"]:
                px = b["c"]
            if px is not None:
                trades.append(sd * (px - pos["entry"]) - cost)
                pos = None
        if pos is None and plan[i] is not None:
            sd, stop = plan[i][0], plan[i][1]
            e = bars[i + 1]["o"]
            if stop is None or sd * (e - stop) <= 0:
                continue
            r = abs(e - stop)
            risks.append(r)
            pos = dict(side=sd, entry=e, stop=stop, targ=e + sd * 2.0 * r,
                       ses=ses[i + 1])
    return trades, risks


def pf(t):
    w = sum(x for x in t if x > 0)
    l = -sum(x for x in t if x <= 0)
    return (w / l) if l else (float("inf") if w > 0 else 0.0)


def spearman(a, b):
    """Rank correlation, ties averaged."""
    def rank(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1
            for k in range(i, j + 1):
                r[order[k]] = avg
            i = j + 1
        return r
    ra, rb = rank(a), rank(b)
    n = len(a)
    ma, mb = sum(ra) / n, sum(rb) / n
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    den = (sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb)) ** 0.5
    return num / den if den else 0.0


def build_plans(st):
    names = ["dva_edge_fade"] + list(P.REGISTRY)
    sigs = {nm: signals_for(st, nm) for nm in names}
    plans = dict(sigs)
    for m in MODES:
        plans[m] = combine(sigs, st["n"], m)
    return plans


def run_market(label, states, costs, out, min_train=0):
    """min_train guards the selection rule against its own worst bias.

    Picking the highest profit factor in training systematically picks the
    candidate with the FEWEST trades, because profit factor on twenty trades
    has far more spread than on four hundred and the maximum over ten
    candidates lands on whichever is noisiest. Run with min_train=0 this
    harness picks conf3 in every single fold of two markets -- not because
    triple agreement works, but because it trades least. Requiring a minimum
    training sample is not a refinement, it is the difference between
    selection and sampling the tail.
    """
    plans = {s: build_plans(states[s]) for s in states}
    keys = list(next(iter(plans.values())).keys())
    bounds = {s: session_bounds(states[s]["bars"]) for s in states}
    nses = min(len(bounds[s]) - 1 for s in states)

    folds = []
    start = 0
    while start + WINDOW <= nses:
        cut = start + int(WINDOW * TRAIN_FRAC)
        folds.append((start, cut, start + WINDOW))
        start += STEP
    if not folds:
        print(f"{label}: only {nses} sessions, need {WINDOW}")
        return

    rng = random.Random(11)
    sel_tr, rnd_tr, orc_tr = [], [], []
    fixed = {k: [] for k in keys}
    picks, tr_pf_all, te_pf_all = [], [], []

    for (a, cut, b) in folds:
        tr_pf, te_pf, te_trades, tr_n = {}, {}, {}, {}
        for k in keys:
            tt, et = [], []
            for s in states:
                lo, mid, hi = bounds[s][a], bounds[s][cut], bounds[s][b]
                tt += execute(states[s], plans[s][k], costs[s], lo, mid)[0]
                et += execute(states[s], plans[s][k], costs[s], mid, hi)[0]
            tr_n[k] = len(tt)
            tr_pf[k] = pf(tt) if len(tt) >= 10 else 0.0
            te_pf[k] = pf(et) if len(et) >= 5 else 0.0
            te_trades[k] = et
            fixed[k] += et
        eligible = [k for k in keys if tr_n[k] >= min_train] or keys
        best = max(eligible, key=lambda k: tr_pf[k])
        picks.append((best, tr_pf[best], tr_n[best], te_pf[best],
                      len(te_trades[best])))
        sel_tr += te_trades[best]
        rnd_tr += te_trades[rng.choice(eligible)]
        orc_tr += te_trades[max(keys, key=lambda k: te_pf[k])]
        live = [k for k in keys if tr_pf[k] > 0 and te_pf[k] > 0]
        if len(live) >= 4:
            tr_pf_all.append([tr_pf[k] for k in live])
            te_pf_all.append([te_pf[k] for k in live])

    print(f"\n===== {label} — {nses} sessions, {len(folds)} folds "
          f"(train {int(WINDOW * TRAIN_FRAC)} / test {WINDOW - int(WINDOW * TRAIN_FRAC)}) =====")
    print(f"{'fold':<6}{'picked in train':<20}{'train PF':>10}{'train n':>9}"
          f"{'test PF':>10}{'test n':>8}")
    for i, (k, a_, tn, b_, n_) in enumerate(picks):
        print(f"{i + 1:<6}{k:<20}{a_:>10.3f}{tn:>9}{b_:>10.3f}{n_:>8}")

    print(f"\n{'strategy':<22}{'test n':>8}{'PF':>9}{'net':>12}{'median':>10}")
    for nm, tr in (("70/30 SELECTED", sel_tr), ("RANDOM pick", rnd_tr),
                   ("ORACLE (hindsight)", orc_tr)):
        if tr:
            print(f"{nm:<22}{len(tr):>8}{pf(tr):>9.3f}{sum(tr):>12.1f}"
                  f"{statistics.median(tr):>10.3f}")
    print(f"{'-' * 60}")
    for k in sorted(keys, key=lambda k: -pf(fixed[k]) if fixed[k] else 0):
        if fixed[k]:
            print(f"  fixed: {k:<15}{len(fixed[k]):>8}{pf(fixed[k]):>9.3f}"
                  f"{sum(fixed[k]):>12.1f}{statistics.median(fixed[k]):>10.3f}")

    if tr_pf_all:
        rhos = [spearman(x, y) for x, y in zip(tr_pf_all, te_pf_all)]
        print(f"\ntrain->test rank correlation per fold: "
              f"{', '.join(f'{r:+.2f}' for r in rhos)}")
        print(f"mean {statistics.mean(rhos):+.3f}   "
              f"(0 means train rank carries no information about test rank)")
        out.append(dict(market=label, rhos=rhos, rule=f"min{min_train}",
                        sel=pf(sel_tr), rnd=pf(rnd_tr), orc=pf(orc_tr),
                        sel_n=len(sel_tr)))


SET_A = "SPY QQQ NVDA TSLA AAPL AMD MSFT INTC META AMZN".split()
SET_B = "GOOGL AVGO IWM PLTR MU COIN NFLX MSTR SMCI XLF".split()
IND = ("NIFTY", "BANKNIFTY", "SENSEX")
IND_COST = {"NIFTY": 0.50, "BANKNIFTY": 4.00, "SENSEX": 4.00}


def main():
    da, db, di = sys.argv[1], sys.argv[2], sys.argv[3]
    from intraday_lab import COST
    import india_volume as IV
    out = []

    built = {}
    for lab, d, syms in (("US set A (10 mega-caps)", da, SET_A),
                         ("US set B (ranks 11-20)", db, SET_B)):
        built[lab] = ({s: P.state(json.load(open(os.path.join(d, f"{s}.json"))))
                       for s in syms}, {s: COST.get(s, 0.02) for s in syms})
    built["India (NIFTY/BANKNIFTY/SENSEX)"] = (
        {ix: P.state(IV.with_volume(di, ix)) for ix in IND}, IND_COST)

    for guard in (0, 30):
        tag = "max PF, no guard" if guard == 0 else f"max PF, >= {guard} train trades"
        print(f"\n\n##### SELECTION RULE: {tag} #####")
        for lab, (st, cs) in built.items():
            run_market(lab, st, cs, out, min_train=guard)

    print(f"\n===== the number that decides it =====")
    print(f"{'market':<34}{'rule':<10}{'mean rho':>10}{'SELECTED':>10}"
          f"{'RANDOM':>9}{'ORACLE':>9}{'sel n':>8}")
    for r in out:
        print(f"{r['market']:<34}{r['rule']:<10}"
              f"{statistics.mean(r['rhos']):>+10.3f}"
              f"{r['sel']:>10.3f}{r['rnd']:>9.3f}{r['orc']:>9.3f}{r['sel_n']:>8}")


if __name__ == "__main__":
    main()
