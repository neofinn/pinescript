"""Does the VOLUME in the volume profile do any work?

dva_edge_fade fires when a bar pokes above the developing value-area high and
closes back below it. Early in a session that edge sits very close to the
session high, so the signal could be nothing but "new session extreme,
rejected" -- a price pattern that would survive with the volume column
deleted.

Three ablations, each removing one ingredient and changing nothing else:

  volume-blind   every bar's volume set to 1. The profile becomes a TIME
                 profile: the same bins, weighted by how long price spent
                 there instead of how much traded there. If the result holds,
                 the volume column is decoration.
  shuffled       each session keeps its own volumes but in a random order
                 across its bars. Destroys the price-volume pairing while
                 preserving the session's volume distribution exactly.
  extreme-only   the level replaced by the running session high/low. If this
                 matches, the value area is a slow-moving proxy for the
                 extreme and adds nothing.

An effect that survives all three is a volume effect. One that dies on the
first was never one.
"""
from __future__ import annotations
import json, os, random, statistics, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import volume_profile as vp
import vp_signals as S
from intraday_lab import context, run, score, COST
from vp_test import enrich, random_pool, pooled_control, pct_rank, SYMS, NBINS


def flat_volume(bars):
    return [dict(b, v=1) for b in bars]


def shuffled_volume(bars, seed=7):
    rng = random.Random(seed)
    out = [dict(b) for b in bars]
    for idxs in vp.sessions_of(bars):
        vols = [out[i]["v"] for i in idxs]
        rng.shuffle(vols)
        for i, v in zip(idxs, vols):
            out[i]["v"] = v
    return out


def running_extreme(bars, min_bars=6):
    """Session high/low THROUGH BAR i-1.

    Through bar i it is unusable, and that is the point: a bar's high can
    never exceed an extreme that already contains it, so the comparison would
    silently fire zero times. The developing value area does not have that
    problem -- bar i can pierce a value-area edge that bar i helped compute --
    which is itself a difference between the two levels, not just an
    implementation detail.
    """
    n = len(bars)
    hi = [None] * n; lo = [None] * n
    for idxs in vp.sessions_of(bars):
        h = l = None
        for k, i in enumerate(idxs):
            if k + 1 >= min_bars and h is not None:
                hi[i], lo[i] = h, l
            h = bars[i]["h"] if h is None else max(h, bars[i]["h"])
            l = bars[i]["l"] if l is None else min(l, bars[i]["l"])
    return hi, lo


def lag1(vah, val):
    """The developing edges as they stood at the PREVIOUS bar's close.

    The strict test. If the edge only works when it contains the piercing bar
    itself, the signal is partly a restatement of that bar's own range.
    """
    return [None] + list(vah[:-1]), [None] + list(val[:-1])


def levels_only(bars, mode):
    """Rebuild just the developing edges under one ablation."""
    if mode == "real":
        src = bars
    elif mode == "volume-blind":
        src = flat_volume(bars)
    elif mode == "shuffled":
        src = shuffled_volume(bars)
    else:
        raise ValueError(mode)
    _, vah, val = vp.developing(src, NBINS)
    return vah, val


def main():
    data = sys.argv[1]
    print(f"{'variant':<16}{'win':<4}{'n':>6}{'PF':>8}{'win%':>7}{'ctl95':>8}"
          f"{'ratio':>8}{'pct':>7}{'med':>9}{'top5%':>8}")
    ctx, raw = {}, {}
    for s in SYMS:
        raw[s] = json.load(open(os.path.join(data, f"{s}.json")))
        ctx[s] = enrich(raw[s])
    split = {s: ctx[s]["n"] // 2 for s in SYMS}
    win = {"IS": {s: (0, split[s]) for s in SYMS},
           "OOS": {s: (split[s], ctx[s]["n"]) for s in SYMS}}
    pools = {}
    for tag in ("IS", "OOS"):
        for s in SYMS:
            a, b = win[tag][s]
            pools[(tag, s)] = random_pool(ctx[s], COST.get(s, 0.02), a, b,
                                          seed=abs(hash((tag, s))) % 10**6)

    variants = {}
    for mode in ("real", "volume-blind", "shuffled"):
        sigs = {}
        for s in SYMS:
            vah, val = levels_only(raw[s], mode)
            x = dict(ctx[s]); x["dvah"], x["dval"] = vah, val
            sigs[s] = S.dva_edge_fade(x)
        variants[mode] = sigs
    sigs = {}
    for s in SYMS:
        vah, val = levels_only(raw[s], "real")
        a, b = lag1(vah, val)
        x = dict(ctx[s]); x["dvah"], x["dval"] = a, b
        sigs[s] = S.dva_edge_fade(x)
    variants["real-lag1"] = sigs
    sigs = {}
    for s in SYMS:
        hi, lo = running_extreme(raw[s])
        x = dict(ctx[s]); x["dvah"], x["dval"] = hi, lo
        sigs[s] = S.dva_edge_fade(x)
    variants["extreme-only"] = sigs

    rows = []
    for mode, sigs in variants.items():
        for tag in ("IS", "OOS"):
            pooled, targets = [], {}
            for s in SYMS:
                a, b = win[tag][s]
                tr, _ = run(ctx[s], sigs[s], stop_atr=2.0, rr=1.5,
                            cost_abs=COST.get(s, 0.02), max_hold=36, lo=a, hi=b)
                pooled += tr; targets[s] = len(tr)
            sc = score(pooled)
            c = pooled_control({s: pools[(tag, s)] for s in SYMS}, targets)
            if c is None:
                print(f"{mode:<16}{tag:<4}{sc['n']:>6}   no matched control"
                      f" (n too small or zero)", flush=True)
                continue
            c50, c95, reach, dist = c
            top = sorted(pooled, reverse=True)[:5]
            # top-5 share of net. Above 100% means the whole result IS those
            # five trades and the other 700-odd lose money together.
            net = sum(pooled)
            share = sum(top) / net * 100 if net > 0 else float("nan")
            rows.append(dict(mode=mode, win=tag, n=sc["n"], pf=sc["pf"],
                             c95=c95, pct=pct_rank(sc["pf"], dist),
                             med=sc["med"], top5=share))
            print(f"{mode:<16}{tag:<4}{sc['n']:>6}{sc['pf']:>8.3f}"
                  f"{sc['win']:>7.1f}{c95:>8.3f}{sc['pf']/c95:>8.3f}"
                  f"{sc['pct'] if False else pct_rank(sc['pf'], dist):>7.1f}"
                  f"{sc['med']:>9.4f}{share:>8.1f}", flush=True)
    json.dump(rows, open(os.path.join(data, "vp_ablate.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
