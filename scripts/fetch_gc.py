"""GC=F bars from Yahoo with explicit epoch bounds.

`range=max` silently downgrades the interval to monthly -- it does not error,
it just hands back different data -- so every request here states period1 and
period2 and the result is checked against what was asked for.
"""
from __future__ import annotations
import json, sys, time, urllib.request

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
URL = ("https://query1.finance.yahoo.com/v8/finance/chart/{sym}"
       "?period1={p1}&period2={p2}&interval={iv}&includePrePost=false")


def fetch(sym: str, iv: str, days: int) -> list[dict]:
    p2 = int(time.time())
    p1 = p2 - days * 86400
    req = urllib.request.Request(URL.format(sym=sym, p1=p1, p2=p2, iv=iv),
                                 headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=45) as r:
        j = json.load(r)
    res = j["chart"]["result"][0]
    meta = res["meta"]
    got = meta.get("dataGranularity")
    if got != iv:
        print(f"  WARNING asked {iv}, got {got}", file=sys.stderr)
    ts = res["timestamp"]
    q = res["indicators"]["quote"][0]
    bars = []
    for i, t in enumerate(ts):
        o, h, l, c = q["open"][i], q["high"][i], q["low"][i], q["close"][i]
        if None in (o, h, l, c):
            continue
        if not (h >= max(o, c) and l <= min(o, c)):
            continue                      # malformed bar, drop it
        bars.append(dict(t=t, o=float(o), h=float(h), l=float(l),
                         c=float(c), v=q["volume"][i] or 0))
    return bars, meta


if __name__ == "__main__":
    sym = sys.argv[1] if len(sys.argv) > 1 else "GC=F"
    for iv, days in (("5m", 59), ("15m", 59), ("1h", 62), ("1d", 62)):
        try:
            bars, meta = fetch(sym, iv, days)
            if not bars:
                print(f"{iv:>4}: no bars"); continue
            import datetime as dt
            a = dt.datetime.utcfromtimestamp(bars[0]["t"]).strftime("%Y-%m-%d %H:%M")
            b = dt.datetime.utcfromtimestamp(bars[-1]["t"]).strftime("%Y-%m-%d %H:%M")
            tick = meta.get("priceHint")
            print(f"{iv:>4}: {len(bars):>6,} bars  {a} -> {b}  "
                  f"granularity={meta.get('dataGranularity')}  "
                  f"last={bars[-1]['c']:.2f}")
            json.dump(bars, open(f"/tmp/claude-0/gc_{iv}.json", "w"))
        except Exception as e:
            print(f"{iv:>4}: FAILED {type(e).__name__} {e}")
