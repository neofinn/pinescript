"""Does the SPX/DJI "overlap" on an overlaid chart mark the bottom in SPX?

The claim: put the S&P 500 and the Dow on one chart at 1-second resolution and
the two lines always interact and overlap; where they overlap is the bottom.

Three things have to be separated before any of that can be tested:

  1. On a SHARED price axis the lines never touch. SPX is near 6,800 and DJI
     near 47,000. An overlay only produces a crossing because the charting
     package gives each symbol its OWN auto-scaled axis.
  2. An auto-scaled axis maps the VISIBLE window's [min, max] onto the pane.
     So the crossing point is a function of how much history is on screen.
     Change the zoom and the crossings move. That is tested directly below by
     recomputing them at several window lengths and measuring the overlap
     between the resulting sets.
  3. The only scale-free version of the idea is the SPX/DJI RATIO, which is a
     real quantity and is tested on its own terms.

Everything is scored against a random-time baseline drawn from the same bars,
so "it marked a bottom" has to beat "any moment marks a bottom".
"""
from __future__ import annotations
import json, os, random, statistics


def norm_window(xs, i, w):
    """What an auto-scaled axis shows: position within the visible window."""
    lo_i = max(0, i - w + 1)
    seg = xs[lo_i:i + 1]
    lo, hi = min(seg), max(seg)
    return 0.5 if hi == lo else (xs[i] - lo) / (hi - lo)


def crossings(a, b, w):
    """Bars where the two auto-scaled lines swap places, for window w."""
    na = [norm_window(a, i, w) for i in range(len(a))]
    nb = [norm_window(b, i, w) for i in range(len(b))]
    d = [x - y for x, y in zip(na, nb)]
    return {i for i in range(1, len(d)) if d[i - 1] * d[i] < 0}


def is_bottom(xs, i, k):
    """SPX at a local minimum over +/- k bars (needs the future; diagnostic only)."""
    lo = max(0, i - k)
    hi = min(len(xs), i + k + 1)
    return xs[i] == min(xs[lo:hi])


def fwd(xs, i, k):
    j = min(len(xs) - 1, i + k)
    return (xs[j] - xs[i]) / xs[i] * 10_000.0      # bps


def evaluate(spx, dji, w, k, rng, label=""):
    cr = sorted(crossings(spx, dji, w))
    cr = [i for i in cr if k <= i < len(spx) - k]
    if len(cr) < 10:
        return None
    n = len(cr)
    pool = [i for i in range(k, len(spx) - k)]
    hit = sum(1 for i in cr if is_bottom(spx, i, k)) / n
    fwdm = statistics.mean(fwd(spx, i, k) for i in cr)
    base_hit, base_fwd = [], []
    for _ in range(400):
        s = rng.sample(pool, n)
        base_hit.append(sum(1 for i in s if is_bottom(spx, i, k)) / n)
        base_fwd.append(statistics.mean(fwd(spx, i, k) for i in s))
    base_hit.sort(); base_fwd.sort()
    pct_h = 100.0 * sum(1 for x in base_hit if x < hit) / len(base_hit)
    pct_f = 100.0 * sum(1 for x in base_fwd if x < fwdm) / len(base_fwd)
    return dict(w=w, n=n, hit=hit, base_hit=base_hit[len(base_hit)//2],
                pct_h=pct_h, fwd=fwdm, base_fwd=base_fwd[len(base_fwd)//2],
                pct_f=pct_f, label=label, idx=cr)
