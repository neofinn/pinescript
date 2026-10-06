"""Does synthetic constituent volume place the POC where real volume does?

The index ETF trades with volume of its own and tracks the index, so it is an
independent witness. Build the same session two ways -- index price with
constituent traded value, and ETF price with ETF volume -- map the ETF's levels
onto the index's scale, and compare.

If the two disagree, the synthetic profile is measuring the constituents'
trading rather than the index's, and every level built on it is a level in a
different instrument. If they agree, the construction carries real information
and the rest of the study is allowed to proceed.

The ETF is not the ground truth either -- it is thinner and has its own
premium/discount -- so this is a two-witness agreement test, not a calibration
against something known.
"""
from __future__ import annotations
import json, os, statistics, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import volume_profile as vp
import india_volume as IV

PAIR = {"NIFTY": "NIFTYBEES", "BANKNIFTY": "BANKBEES"}


def by_day(bars):
    import datetime as dt
    out = {}
    for b in bars:
        out.setdefault(dt.datetime.utcfromtimestamp(b["t"]).date(), []).append(b)
    return out


def main(d):
    print(f"{'index':<12}{'days':>6}{'POC gap %':>11}{'VAH gap %':>11}"
          f"{'VAL gap %':>11}{'POC gap (pts)':>15}{'ratio sd':>10}")
    for ix, etf in PAIR.items():
        idx = by_day(IV.with_volume(d, ix))
        ef = by_day(json.load(open(os.path.join(d, f"{etf}.json"))))
        gp, gh, gl, pts, ratios = [], [], [], [], []
        for day in sorted(set(idx) & set(ef)):
            a, b = idx[day], [x for x in ef[day] if (x["v"] or 0) > 0]
            if len(a) < 30 or len(b) < 30:
                continue
            # per-session scale factor, from the closes themselves
            common = {x["t"]: x["c"] for x in b}
            rs = [x["c"] / common[x["t"]] for x in a if x["t"] in common]
            if len(rs) < 20:
                continue
            k = statistics.median(rs)
            ratios.append(statistics.pstdev(rs) / k * 100)
            pa = vp.build(a, 60)
            pb = vp.build(b, 60)
            for src, dst in ((pb["poc"] * k, pa["poc"]), ):
                gp.append(abs(src - dst) / dst * 100)
                pts.append(abs(src - dst))
            gh.append(abs(pb["vah"] * k - pa["vah"]) / pa["vah"] * 100)
            gl.append(abs(pb["val"] * k - pa["val"]) / pa["val"] * 100)
        if not gp:
            print(f"{ix:<12}  no overlapping sessions")
            continue
        print(f"{ix:<12}{len(gp):>6}{statistics.median(gp):>11.3f}"
              f"{statistics.median(gh):>11.3f}{statistics.median(gl):>11.3f}"
              f"{statistics.median(pts):>15.1f}{statistics.median(ratios):>10.3f}")
        rng = [(max(x["h"] for x in idx[dd]) - min(x["l"] for x in idx[dd]))
               for dd in sorted(set(idx) & set(ef)) if len(idx[dd]) >= 30]
        med_rng = statistics.median(rng)
        print(f"{'':<12}median session range {med_rng:.0f} pts -> POC gap is "
              f"{statistics.median(pts) / med_rng * 100:.1f}% of the day's range")


if __name__ == "__main__":
    main(sys.argv[1])
