"""Approximate delta and imbalance from sub-bars. What this is and is not.

REAL orderflow is trade-by-trade with the aggressor side known: who crossed the
spread, at what price level, against how much resting size. Diagonal imbalance
-- ask volume at price P against bid volume at P minus one tick -- needs
per-level bid/ask volume, and no OHLCV feed carries it. Neither Yahoo nor a
standard TradingView chart has any of it.

What CAN be built from bars is the tick rule applied to sub-bars: split each
sub-bar's volume between buyers and sellers by where it closed within its own
range, then sum. That is what every Pine "footprint" script does under the
hood, via request.security_lower_tf(). It is an approximation of an
approximation and it should be labelled as one:

  * a sub-bar that closes at its high is counted as all buying. It might have
    been one aggressive buy into a thin book, or steady accumulation.
  * the Lee-Ready rule against quote midpoints classifies real trades at around
    85% accuracy. Classifying an AGGREGATE bar by its close is coarser than
    that, and the error grows as the sub-bar gets longer.
  * absorption and exhaustion are inferred from price-versus-volume
    disagreement, not observed.

So the honest question is not "is this real orderflow" -- it is not -- but
"does this approximation carry information the price bars do not". That is
measurable, and it is what the accompanying test measures.
"""
from __future__ import annotations


def classify(bar: dict) -> tuple[float, float]:
    """Split one sub-bar's volume into (buy, sell) by close position in range."""
    rng = bar["h"] - bar["l"]
    v = bar["v"] or 0
    if v <= 0:
        return 0.0, 0.0
    if rng <= 0:
        return v * 0.5, v * 0.5
    up = (bar["c"] - bar["l"]) / rng
    return v * up, v * (1.0 - up)


def aggregate(subs: list[dict], minutes: int, sub_minutes: int) -> list[dict]:
    """Build higher-timeframe bars from sub-bars, carrying flow metrics.

    Bucketing is by wall-clock epoch so a bar's boundary does not drift with
    gaps; a session break must not silently merge two candles into one.
    """
    if not subs:
        return []
    span = minutes * 60
    out, cur, bucket = [], None, None
    for b in subs:
        k = b["t"] - (b["t"] % span)
        if bucket is None or k != bucket:
            if cur is not None:
                out.append(cur)
            bucket = k
            cur = dict(t=k, o=b["o"], h=b["h"], l=b["l"], c=b["c"], v=0.0,
                       buy=0.0, sell=0.0, n=0, runs=0, last_sign=0,
                       max_run=0)
        cur["h"] = max(cur["h"], b["h"])
        cur["l"] = min(cur["l"], b["l"])
        cur["c"] = b["c"]
        cur["v"] += b["v"] or 0
        bv, sv = classify(b)
        cur["buy"] += bv
        cur["sell"] += sv
        cur["n"] += 1
        # stacked imbalance, approximated: consecutive sub-bars whose flow
        # leaned the same way. Real stacking is by PRICE LEVEL, not by time,
        # so this is a weaker cousin of the thing it is named after.
        s = 1 if bv > sv else (-1 if sv > bv else 0)
        if s != 0 and s == cur["last_sign"]:
            cur["runs"] += 1
        elif s != 0:
            cur["runs"] = 1
        cur["last_sign"] = s
        cur["max_run"] = max(cur["max_run"], cur["runs"] * (1 if s > 0 else -1)
                             if s > 0 else cur["max_run"])
        if s < 0:
            cur["max_run"] = min(cur.get("min_run", 0), -cur["runs"])
            cur["min_run"] = cur["max_run"]
    if cur is not None:
        out.append(cur)
    for b in out:
        b["delta"] = b["buy"] - b["sell"]
        # imbalance: how lopsided the flow was, -1 all sellers .. +1 all buyers
        b["imb"] = b["delta"] / b["v"] if b["v"] > 0 else 0.0
        rng = b["h"] - b["l"]
        # absorption: volume that did NOT move price. High means size was
        # being taken without the price going anywhere.
        b["absorb"] = (b["v"] / rng) if rng > 0 else 0.0
        move = b["c"] - b["o"]
        # exhaustion: flow and price disagreeing about direction
        b["exhaust"] = (b["delta"] > 0 and move < 0) or (b["delta"] < 0 and move > 0)
    return out
