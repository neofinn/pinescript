"""Pre-registered volume-profile signals, fixed before any of them was run.

Six, not sixty. Every extra variant is another draw against the same data, and
a set this size already needs its results read against a control -- which is
what the harness does. They divide into the two things a profile is claimed to
do:

  ACCEPTANCE    price inside value rotates; price leaving value keeps going.
                -> pva_breakout, lvn_break
  REJECTION     price probing outside value gets pushed back to the POC.
                -> pva_edge_fade, dva_edge_fade, ppoc_reversion,
                   naked_poc_magnet

They contradict each other on purpose. A level either holds or it does not, and
running both directions is the only way the data gets to answer rather than the
author.

Causality: each signal reads bar i and earlier. Prior-session levels are fixed
at the open; developing levels are as of bar i; naked POCs are cleared the
moment a bar trades through them, walking forward.
"""
from __future__ import annotations


def _blank(n): return [0] * n


def pva_edge_fade(x):
    """Probe outside yesterday's value area, close back inside. Rejection."""
    n, c, h, l = x["n"], x["c"], x["h"], x["l"]
    vah, val = x["pvah"], x["pval"]
    s = _blank(n)
    for i in range(n):
        if vah[i] is None: continue
        if h[i] > vah[i] and c[i] < vah[i]: s[i] = -1
        elif l[i] < val[i] and c[i] > val[i]: s[i] = 1
    return s


def dva_edge_fade(x):
    """Same, against the value area TODAY has built so far."""
    n, c, h, l = x["n"], x["c"], x["h"], x["l"]
    vah, val = x["dvah"], x["dval"]
    s = _blank(n)
    for i in range(n):
        if vah[i] is None: continue
        if h[i] > vah[i] and c[i] < vah[i]: s[i] = -1
        elif l[i] < val[i] and c[i] > val[i]: s[i] = 1
    return s


def pva_breakout(x):
    """First close outside yesterday's value area. Acceptance."""
    n, c = x["n"], x["c"]
    vah, val = x["pvah"], x["pval"]
    s = _blank(n)
    for i in range(1, n):
        if vah[i] is None or vah[i - 1] is None: continue
        if c[i] > vah[i] and c[i - 1] <= vah[i - 1]: s[i] = 1
        elif c[i] < val[i] and c[i - 1] >= val[i - 1]: s[i] = -1
    return s


def ppoc_reversion(x, k=1.0):
    """Stretched k*ATR beyond yesterday's value. Trade back toward its POC."""
    n, c, atr = x["n"], x["c"], x["atr"]
    vah, val = x["pvah"], x["pval"]
    s = _blank(n)
    for i in range(n):
        if vah[i] is None or not atr[i]: continue
        if c[i] > vah[i] + k * atr[i]: s[i] = -1
        elif c[i] < val[i] - k * atr[i]: s[i] = 1
    return s


def naked_poc_magnet(x, k=2.0, min_k=0.25):
    """Nearest untouched POC from an earlier session, within k*ATR.

    min_k keeps out the case where the level is already inside the noise of the
    current bar, where 'trade toward it' has no direction worth the spread.
    """
    n, c, atr, nk = x["n"], x["c"], x["atr"], x["npoc"]
    s = _blank(n)
    for i in range(n):
        if not atr[i] or not nk[i]: continue
        p = min(nk[i], key=lambda q: abs(q - c[i]))
        d = (p - c[i]) / atr[i]
        if min_k <= abs(d) <= k: s[i] = 1 if d > 0 else -1
    return s


def lvn_break(x):
    """Close through a thin price from yesterday's profile. Continuation.

    The premise is mechanical rather than behavioural: little volume traded
    there, so there is little resting interest to slow price down.
    """
    n, c, lv = x["n"], x["c"], x["plvn"]
    s = _blank(n)
    for i in range(1, n):
        if not lv[i]: continue
        for p in lv[i]:
            if c[i - 1] <= p < c[i]: s[i] = 1; break
            if c[i - 1] >= p > c[i]: s[i] = -1; break
    return s


REGISTRY = {
    "pva_edge_fade": pva_edge_fade,
    "dva_edge_fade": dva_edge_fade,
    "pva_breakout": pva_breakout,
    "ppoc_reversion": ppoc_reversion,
    "naked_poc_magnet": naked_poc_magnet,
    "lvn_break": lvn_break,
}


# ── orderflow gates ───────────────────────────────────────────────────────
# Applied on top of a signal, never as a signal of their own. Each one is a
# different claim about WHY the level should work, and they are mutually
# exclusive by construction, so at most one can be right for a given signal.

def gate_agree(sig, imb, thresh=0.0):
    """Flow pushing the same way the trade is going. Momentum reading."""
    return [s if (s != 0 and imb[i] is not None and s * imb[i] > thresh) else 0
            for i, s in enumerate(sig)]


def gate_absorb(sig, imb, thresh=0.0):
    """Flow pushing AGAINST the trade while the level holds. Absorption --
    the orderflow reason a fade is supposed to work at all: size is being
    taken and price is not going anywhere."""
    return [s if (s != 0 and imb[i] is not None and s * imb[i] < -thresh) else 0
            for i, s in enumerate(sig)]


def gate_strong(sig, imb, thresh=0.25):
    return gate_agree(sig, imb, thresh)


GATES = {"none": lambda s, imb: s,
         "agree": gate_agree,
         "absorb": gate_absorb,
         "strong": gate_strong}
