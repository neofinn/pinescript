"""Indian index bars carry no volume. This builds one that means something.

Every NSE and BSE index -- NIFTY, BANKNIFTY, SENSEX, NIFTY IT, Midcap -- prints
zero volume at every intraday timeframe. Checked, not assumed: 374 five-minute
bars each, volume > 0 on exactly none of them, while every constituent and both
index ETFs carry volume on 98% of bars.

So a volume profile on an Indian index has to be constructed, and the
construction is a modelling choice that should be argued rather than hidden:

  TRADED VALUE, not share count. Summing share volumes across HDFC Bank at
  ~1,000 and Bajaj Finance at ~9,000 adds numbers with different units. The
  economically meaningful figure is rupees transacted, so each constituent
  contributes price x volume. The profile then answers "how much money changed
  hands while the index was at this level", which is the question a volume
  profile is supposed to answer anyway.

  NO WEIGHTING BEYOND THAT. The index is free-float market-cap weighted, but
  weighting traded value again by index weight would double-count: a large
  constituent already contributes more rupees because more of it trades.

The construction is then CHECKED against the index ETF, which has real volume
of its own, by comparing where the two put the POC. That check is in
india_validate.py and its answer is reported rather than presumed.
"""
from __future__ import annotations
import json, os


NIFTY50 = """ADANIENT ADANIPORTS APOLLOHOSP ASIANPAINT AXISBANK BAJAJ-AUTO
BAJFINANCE BAJAJFINSV BEL BHARTIARTL CIPLA COALINDIA DRREDDY EICHERMOT ETERNAL
GRASIM HCLTECH HDFCBANK HDFCLIFE HEROMOTOCO HINDALCO HINDUNILVR ICICIBANK
INDUSINDBK INFY ITC JIOFIN JSWSTEEL KOTAKBANK LT M&M MARUTI NESTLEIND NTPC ONGC
POWERGRID RELIANCE SBILIFE SBIN SHRIRAMFIN SUNPHARMA TATACONSUM TATASTEEL TCS
TECHM TITAN TRENT ULTRACEMCO WIPRO""".split()

BANKNIFTY = """HDFCBANK ICICIBANK SBIN KOTAKBANK AXISBANK INDUSINDBK BANKBARODA
PNB FEDERALBNK IDFCFIRSTB AUBANK CANBK""".split()

BASKET = {"NIFTY": NIFTY50, "BANKNIFTY": BANKNIFTY, "SENSEX": NIFTY50}


def traded_value(d: str, names: list[str]) -> dict[int, float]:
    """Rupees transacted per 5-minute stamp, summed over a basket."""
    out: dict[int, float] = {}
    for nm in names:
        p = os.path.join(d, f"c_{nm}.json")
        if not os.path.exists(p):
            continue
        for b in json.load(open(p)):
            v = b["v"] or 0
            if v > 0:
                out[b["t"]] = out.get(b["t"], 0.0) + b["c"] * v
    return out


def with_volume(d: str, index: str) -> list[dict]:
    """Index price bars carrying synthetic traded-value volume.

    A bar whose basket contributed nothing is dropped rather than kept at zero.
    Keeping it would put a price level in the profile with no volume behind it,
    which is exactly the kind of empty row a low-volume-node rule would then
    treat as a signal.
    """
    bars = json.load(open(os.path.join(d, f"{index}.json")))
    tv = traded_value(d, BASKET[index])
    out = []
    for b in bars:
        v = tv.get(b["t"], 0.0)
        if v > 0:
            out.append(dict(b, v=v))
    return out


def coverage(d: str, index: str) -> dict:
    bars = json.load(open(os.path.join(d, f"{index}.json")))
    tv = traded_value(d, BASKET[index])
    hit = sum(1 for b in bars if tv.get(b["t"], 0) > 0)
    names = BASKET[index]
    have = sum(1 for nm in names
               if os.path.exists(os.path.join(d, f"c_{nm}.json")))
    return dict(index_bars=len(bars), with_volume=hit,
                constituents=len(names), fetched=have)
