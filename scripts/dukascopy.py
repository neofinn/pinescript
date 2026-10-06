"""Deep intraday history from Dukascopy's public tick feed.

Why this exists: every fast-timeframe study in this repo has been limited by
Yahoo, which serves 1-minute data for about a month and 30-minute for 60 days.
That is why the 3-minute gold run had 22 sessions, and why its numbers sat in
the same inflated band as every other thin sample.

TradingView has no official data API and its terms prohibit automated
extraction, so it is not the answer. Dukascopy publishes an open historical
feed instead: one LZMA-compressed file per instrument per hour, back to roughly
2003, carrying every tick with BOTH SIDES OF THE BOOK.

That second part matters as much as the depth. Every cost figure used in this
repo so far has been an assumption -- $0.25 of spread on gold, 1 basis point on
futures. These files carry the real bid and the real ask, so the spread can be
measured per bar and charged as it actually was, including its widening
overnight and around news.

File layout, 20 bytes per tick, big-endian:
    uint32  milliseconds since the start of the hour
    uint32  ask, in points
    uint32  bid, in points
    float32 ask volume
    float32 bid volume
An empty file means the market was closed for that hour, which is how weekends
and holidays appear.
"""
from __future__ import annotations
import datetime as dt
import json, lzma, os, struct, time, urllib.error, urllib.request

FEED = "https://datafeed.dukascopy.com/datafeed"
UA = {"User-Agent": "Mozilla/5.0"}

# instrument -> points per unit of price
SCALE = {"XAUUSD": 1e-3, "XAGUSD": 1e-3, "EURUSD": 1e-5, "USDJPY": 1e-3,
         "GBPUSD": 1e-5, "USA500IDXUSD": 1e-3, "USATECHIDXUSD": 1e-3,
         "LIGHTCMDUSD": 1e-3, "BRENTCMDUSD": 1e-3}


def hour_ticks(sym, when, tries=3, timeout=45):
    """[(epoch_seconds_float, bid, ask)] for one hour. [] when closed."""
    u = (f"{FEED}/{sym}/{when.year}/{when.month - 1:02d}/{when.day:02d}/"
         f"{when.hour:02d}h_ticks.bi5")
    for a in range(tries):
        try:
            raw = urllib.request.urlopen(
                urllib.request.Request(u, headers=UA), timeout=timeout).read()
            break
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return []                      # no file: closed, not an error
            if a == tries - 1:
                return None
            time.sleep(1.5 ** a)
        except Exception:
            if a == tries - 1:
                return None
            time.sleep(1.5 ** a)
    else:
        return None
    if not raw:
        return []
    try:
        d = lzma.decompress(raw, format=lzma.FORMAT_AUTO)
    except Exception:
        return None
    s = SCALE.get(sym, 1e-5)
    base = when.replace(tzinfo=dt.timezone.utc).timestamp()
    out = []
    for i in range(len(d) // 20):
        ms, ask, bid, _, _ = struct.unpack(">IIIff", d[i * 20:(i + 1) * 20])
        out.append((base + ms / 1000.0, bid * s, ask * s))
    return out


def bars_from_ticks(ticks, minutes):
    """OHLC from the MID, plus the mean and max spread inside each bar.

    Mid rather than bid or ask, so the bars are side-neutral and the spread is
    charged explicitly at execution instead of being baked into the prices.
    """
    step = minutes * 60
    out, cur, key = [], None, None
    for t, bid, ask in ticks:
        k = int(t // step) * step
        mid = (bid + ask) / 2.0
        sp = ask - bid
        if k != key:
            if cur:
                out.append(cur)
            cur = dict(t=k, o=mid, h=mid, l=mid, c=mid, v=0,
                       sp_sum=0.0, sp_max=0.0, n=0)
            key = k
        cur["h"] = max(cur["h"], mid)
        cur["l"] = min(cur["l"], mid)
        cur["c"] = mid
        cur["n"] += 1
        cur["sp_sum"] += sp
        cur["sp_max"] = max(cur["sp_max"], sp)
    if cur:
        out.append(cur)
    for b in out:
        b["spread"] = b["sp_sum"] / b["n"] if b["n"] else 0.0
        b["v"] = b["n"]
        del b["sp_sum"], b["n"]
    return out


def fetch_range(sym, start, end, out_path, minutes=1, workers=32,
                log_every=400):
    """Fetch the range with a thread pool, keeping only aggregated bars.

    Each hourly file is an independent request and this is latency-bound, not
    bandwidth-bound -- about 15 seconds per round trip through the proxy.
    Serially that is 38 hours for a year of gold; with a pool it is under two.
    Resumable: hours already covered by the output file are skipped.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    bars = {}
    if os.path.exists(out_path):
        for b in json.load(open(out_path)):
            bars[b["t"]] = b
    covered = {int(t // 3600) * 3600 for t in bars}
    hours, h = [], start
    while h < end:
        if int(h.replace(tzinfo=dt.timezone.utc).timestamp()) not in covered:
            hours.append(h)
        h += dt.timedelta(hours=1)
    print(f"  {len(hours):,} hours to fetch, {len(bars):,} bars already held",
          flush=True)
    n_ok = n_empty = n_fail = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(hour_ticks, sym, w): w for w in hours}
        for i, f in enumerate(as_completed(futs), 1):
            try:
                tk = f.result()
            except Exception:
                tk = None
            if tk is None:
                n_fail += 1
            elif not tk:
                n_empty += 1
            else:
                n_ok += 1
                for b in bars_from_ticks(tk, minutes):
                    bars[b["t"]] = b
            if i % log_every == 0:
                json.dump(sorted(bars.values(), key=lambda x: x["t"]),
                          open(out_path, "w"))
                print(f"  {i:,}/{len(hours):,}  {len(bars):,} bars  "
                      f"ok {n_ok} closed {n_empty} failed {n_fail}", flush=True)
    srt = sorted(bars.values(), key=lambda x: x["t"])
    json.dump(srt, open(out_path, "w"))
    print(f"  complete: {len(srt):,} bars, ok {n_ok} closed {n_empty} "
          f"failed {n_fail}", flush=True)
    return srt
