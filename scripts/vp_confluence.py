"""Confluence: trade only where the setups agree.

The overlap has to be measured before agreement can mean anything. Across the
full window, pooled over SPY, QQQ and ES:

    absorption_at_edge fires 482 times and 365 of those -- 76% -- land on the
    same bar and the same side as dva_edge_fade.

That is not two signals agreeing. absorption_at_edge IS dva_edge_fade plus an
imbalance condition, so counting them as a pair inflates "confluence" with a
signal agreeing with itself. The other pairs are far more independent
(delta_breakout with naked_poc_flow 245, dva with cvd 186, lvn with naked 83),
so the redundancy is specific and can be excluded rather than lived with.

Hence four variants, fixed before the run:

  conf2           >= 2 setups fire, all firing setups on the same side
  conf2_majority  >= 2 on one side, disagreement from others tolerated
  conf2_distinct  >= 2 from DIFFERENT families -- the redundancy removed
  conf3           >= 3, unanimous

And the sample cost is the whole question. Pooled over three instruments and
the full window there are 3,667 bars where exactly one setup fires, 837 where
two agree cleanly, and 50 where three do. Confluence is not a filter that
trims the edges; it discards roughly four fifths of the opportunities, and it
has to pay for that out of selectivity.
"""
from __future__ import annotations
import statistics

import vp_of_pure as P

# Setups that restate each other belong to one family. Agreement WITHIN a
# family is not confluence.
FAMILY = {
    "dva_edge_fade": "edge",
    "absorption_at_edge": "edge",
    "delta_breakout": "breakout",
    "lvn_delta_traverse": "node",
    "cvd_divergence": "divergence",
    "naked_poc_flow": "magnet",
}


def combine(sigs: dict, n: int, mode: str, stop_rule: str = "widest"):
    """Merge per-setup plans into one confluence plan.

    stop_rule decides whose stop the combined trade uses. "widest" is the
    pre-registered choice: if two structures disagree about where the idea is
    wrong, it is wrong at the further one. "tightest" is carried as the
    robustness check, not as a knob to turn until something works.
    """
    out = [None] * n
    for i in range(n):
        longs = [(nm, s) for nm, s in sigs.items() if s[i] and s[i][0] > 0]
        shorts = [(nm, s) for nm, s in sigs.items() if s[i] and s[i][0] < 0]
        for side, group, other in ((1, longs, shorts), (-1, shorts, longs)):
            if not group:
                continue
            fams = {FAMILY[nm] for nm, _ in group}
            if mode == "conf2":
                ok = len(group) >= 2 and not other
            elif mode == "conf2_majority":
                ok = len(group) >= 2 and len(group) > len(other)
            elif mode == "conf2_distinct":
                ok = len(fams) >= 2 and not other
            elif mode == "conf3":
                ok = len(group) >= 3 and not other
            else:
                raise ValueError(mode)
            if not ok:
                continue
            stops = [s[i][1] for _, s in group if s[i][1] is not None]
            if not stops:
                continue
            if stop_rule == "widest":
                stop = min(stops) if side > 0 else max(stops)
            elif stop_rule == "tightest":
                stop = max(stops) if side > 0 else min(stops)
            else:
                stop = statistics.median(stops)
            out[i] = (side, stop, None)
            break
    return out


MODES = ("conf2", "conf2_majority", "conf2_distinct", "conf3")
