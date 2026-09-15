"""Directional volume breadth, and pullback entries, tested on both sides.

The gate used so far counts constituents trading heavily without asking which
way they are trading. That is a reasonable long confirmation and close to
useless as a short one, so it is split here into an up-volume share and a
down-volume share and each side is tested against its own.
"""
import json, os, glob, datetime, sys
SC = "/home/user/pinescript/scripts"
sys.path.insert(0, SC)
from indices_run import ema, atr, stat

def day(t): return datetime.datetime.fromtimestamp(t, datetime.UTC).date()

def directional_breadth(look=20):
    """{date: (up_surge_share, down_surge_share, plain_surge_share)}"""
    up, dn, tot, cnt = {}, {}, {}, {}
    for p in sorted(glob.glob(os.path.join(SC, "n50", "*.json"))):
        bars = json.load(open(p))
        V = [b["v"] for b in bars]; C = [b["c"] for b in bars]
        for i, b in enumerate(bars):
            if i < look + 1: continue
            d = day(b["t"])
            w = V[i-look:i]; m = sum(w)/len(w) if w else 0
            if m <= 0 or V[i] <= 0: continue
            cnt[d] = cnt.get(d, 0) + 1
            if V[i]/m > 1.5:
                tot[d] = tot.get(d, 0) + 1
                if C[i] > C[i-1]: up[d] = up.get(d, 0) + 1
                elif C[i] < C[i-1]: dn[d] = dn.get(d, 0) + 1
    out = {}
    for d, n in cnt.items():
        if n >= 20:
            out[d] = (up.get(d,0)/n, dn.get(d,0)/n, tot.get(d,0)/n)
    return out

BR = directional_breadth()
print(f"directional breadth computed for {len(BR)} sessions")
vals = sorted(BR.values())
ups = sorted(v[0] for v in BR.values()); dns = sorted(v[1] for v in BR.values())
print(f"  up-surge share   median {ups[len(ups)//2]:.3f}  p90 {ups[int(len(ups)*.9)]:.3f}")
print(f"  down-surge share median {dns[len(dns)//2]:.3f}  p90 {dns[int(len(dns)*.9)]:.3f}")
json.dump({str(k): list(v) for k, v in BR.items()},
          open(os.path.join(SC, "nifty_dir_breadth.json"), "w"))
