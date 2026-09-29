"""Live Kronos forecast on any bar file and timeframe, as a distribution.

Generalises the NIFTY-5m version. Two things it refuses to do quietly:

  * it drops the bar still forming, since a partial candle's high, low and
    close are not yet what they will be;
  * it omits the volume channel entirely when the instrument prints none,
    rather than feeding a column of zeros the model would condition on.

Paths are drawn one at a time. KronosPredictor batches `sample_count` but
returns their MEAN, so batching cannot produce a spread -- and the spread is
the forecast.
"""
from __future__ import annotations
import datetime as dt
import json, os, sys, time, warnings

warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd
import torch

sys.path.insert(0, "/home/user/shiyu-coder/kronos")
from model import Kronos, KronosTokenizer, KronosPredictor

LOOKBACK = 512


def main():
    src, secs, horizon, samples = (sys.argv[1], int(sys.argv[2]),
                                   int(sys.argv[3]), int(sys.argv[4]))
    label = sys.argv[5] if len(sys.argv) > 5 else os.path.basename(src)
    now = int(time.time())
    raw = json.load(open(src))
    bars = [b for b in raw if b["t"] + secs <= now]
    dropped = len(raw) - len(bars)
    last = bars[-1]
    lt = dt.datetime.utcfromtimestamp(last["t"])

    df = pd.DataFrame(bars)
    df["timestamps"] = pd.to_datetime(df["t"], unit="s")
    df = df.rename(columns={"o": "open", "h": "high", "l": "low",
                            "c": "close", "v": "volume"})
    cols = ["open", "high", "low", "close", "volume"]
    novol = (df["volume"] > 0).mean() < 0.5
    if novol:
        cols = ["open", "high", "low", "close"]

    torch.set_num_threads(4)
    tok = KronosTokenizer.from_pretrained("NeoQuasar/Kronos-Tokenizer-base")
    mdl = Kronos.from_pretrained("NeoQuasar/Kronos-small")
    pred = KronosPredictor(mdl, tok, device="cpu", max_context=LOOKBACK)

    x = df.loc[len(df) - LOOKBACK:, cols].reset_index(drop=True)
    xt = df.loc[len(df) - LOOKBACK:, "timestamps"].reset_index(drop=True)
    yt = pd.Series(pd.to_datetime(
        [last["t"] + secs * (k + 1) for k in range(horizon)], unit="s"))

    paths = []
    for _ in range(samples):
        f = pred.predict(df=x, x_timestamp=xt, y_timestamp=yt,
                         pred_len=horizon, T=1.0, top_p=0.9,
                         sample_count=1, verbose=False)
        paths.append([float(v) for v in f["close"].tolist()])
    P = np.array(paths)
    spot = float(last["c"])
    end = P[:, -1]
    q = lambda k: float(np.percentile(end, k))
    ist = lt + dt.timedelta(hours=5, minutes=30)
    print(f"\n=== {label} ===")
    print(f"  last complete bar {lt:%Y-%m-%d %H:%M} UTC / {ist:%H:%M} IST   "
          f"close {spot:,.2f}   ({dropped} forming bar dropped)"
          f"{'   [OHLC only, no volume]' if novol else ''}")
    print(f"  horizon {horizon} bars = {horizon * secs / 3600:.1f}h, "
          f"{samples} sampled paths")
    print(f"  P(up)  {float((end > spot).mean() * 100):.0f}%")
    print(f"  median {np.median(end):,.1f}  ({(np.median(end) / spot - 1) * 100:+.2f}%)")
    print(f"  80% band {q(10):,.1f} .. {q(90):,.1f}  "
          f"({(q(10) / spot - 1) * 100:+.2f}% .. {(q(90) / spot - 1) * 100:+.2f}%)")
    print(f"  extremes {end.min():,.1f} .. {end.max():,.1f}")
    out = dict(label=label, spot=spot, horizon=horizon, secs=secs,
               samples=samples, novol=bool(novol),
               last_bar=int(last["t"]), p_up=float((end > spot).mean() * 100),
               median=float(np.median(end)), p10=q(10), p90=q(90),
               ends=[float(v) for v in end])
    json.dump(out, open(src.replace(".json", "_live.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
