"""Generate Kronos forecasts over cached 5m bars, strictly causally.

WHY THIS TEST IS DIFFERENT FROM EVERY OTHER ONE IN THIS REPO

Every signal in this project was written by someone who had already seen the
data. That is the bias the random controls, the IS/OOS splits and the universe
swaps exist to fight, and they never fully win.

Kronos's weights were published 2025-06-30 and last modified 2025-09-09. The
bars here are July-September 2026. The parameters were frozen a year before
this data existed, so no amount of looking could have fitted them to it. That
makes this the only genuinely out-of-sample test in the repo, and it is worth
more than the sample size suggests.

CAUSALITY. The context for a forecast at bar i is bars[i-512 : i] -- strictly
before i. The forecast covers bars i .. i+pred_len-1. A trade on it is entered
at bar i's open, which is the first price available after the context closes.

Checkpoints every 20 forecasts so a long run is never lost.
"""
from __future__ import annotations
import json, os, sys, time, warnings

warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd
import torch

sys.path.insert(0, "/home/user/shiyu-coder/kronos")
from model import Kronos, KronosTokenizer, KronosPredictor

LOOKBACK = 512
PRED_LEN = 12          # one hour on 5m bars
STRIDE = 36            # three hours between forecast points
SAMPLES = 5            # probabilistic paths, averaged


def load(path):
    df = pd.DataFrame(json.load(open(path)))
    df["timestamps"] = pd.to_datetime(df["t"], unit="s")
    return df.rename(columns={"o": "open", "h": "high", "l": "low",
                              "c": "close", "v": "volume"})


def main():
    src, out_dir, tag = sys.argv[1], sys.argv[2], sys.argv[3]
    which = sys.argv[4] if len(sys.argv) > 4 else "NeoQuasar/Kronos-small"
    # Forecast TARGETS must post-date the weights, or the model is being asked
    # about bars it may have trained on. Kronos-small was published
    # 2025-06-30 and last modified 2025-09-09; the later date is the safe one.
    # Context bars before the cutoff are allowed -- seeing history as context
    # is not leakage, having memorised what followed it would be.
    after = sys.argv[5] if len(sys.argv) > 5 else "2025-09-09"
    stride = int(sys.argv[6]) if len(sys.argv) > 6 else STRIDE
    torch.set_num_threads(4)
    tok = KronosTokenizer.from_pretrained("NeoQuasar/Kronos-Tokenizer-base")
    mdl = Kronos.from_pretrained(which)
    pred = KronosPredictor(mdl, tok, device="cpu", max_context=LOOKBACK)

    df = load(src)
    n = len(df)
    # An index that prints no volume must have the channel OMITTED, not fed as
    # a column of zeros: a constant zero is a value the model will condition
    # on, and it is not one any real instrument produces.
    cols = ["open", "high", "low", "close", "volume"]
    if (df["volume"] > 0).mean() < 0.5:
        cols = ["open", "high", "low", "close"]
        print(f"{tag}: volume absent on "
              f"{(df['volume'] <= 0).mean() * 100:.0f}% of bars -> OHLC only",
              flush=True)
    out_path = os.path.join(out_dir, f"{tag}.json")
    rows = json.load(open(out_path)) if os.path.exists(out_path) else []
    done = {r["i"] for r in rows}
    cut = pd.Timestamp(after)
    cand = list(range(LOOKBACK, n - PRED_LEN, stride))
    pre = sum(1 for i in cand if df.loc[i, "timestamps"] < cut)
    points = [i for i in cand
              if i not in done and df.loc[i, "timestamps"] >= cut]
    print(f"{tag}: {len(points)} forecasts to make ({len(done)} cached); "
          f"{pre} candidates dropped as pre-{after}", flush=True)

    t0 = time.time()
    for k, i in enumerate(points):
        x = df.loc[i - LOOKBACK:i - 1, cols].reset_index(drop=True)
        xt = df.loc[i - LOOKBACK:i - 1, "timestamps"].reset_index(drop=True)
        yt = df.loc[i:i + PRED_LEN - 1, "timestamps"].reset_index(drop=True)
        try:
            f = pred.predict(df=x, x_timestamp=xt, y_timestamp=yt,
                             pred_len=PRED_LEN, T=1.0, top_p=0.9,
                             sample_count=SAMPLES, verbose=False)
        except Exception as e:
            print(f"  skip {i}: {type(e).__name__} {e}", flush=True)
            continue
        last = float(df.loc[i - 1, "close"])
        rows.append(dict(
            i=int(i), t=int(df.loc[i, "t"]), last_close=last,
            entry_open=float(df.loc[i, "open"]),
            # forecast
            p_close=[float(v) for v in f["close"].tolist()],
            p_high=float(f["high"].max()), p_low=float(f["low"].min()),
            # realised, for scoring only -- never fed back into a forecast
            a_close=[float(v) for v in
                     df.loc[i:i + PRED_LEN - 1, "close"].tolist()],
            a_high=float(df.loc[i:i + PRED_LEN - 1, "high"].max()),
            a_low=float(df.loc[i:i + PRED_LEN - 1, "low"].min()),
        ))
        if (k + 1) % 20 == 0 or k == len(points) - 1:
            json.dump(rows, open(out_path, "w"))
            el = time.time() - t0
            print(f"  {tag} {k + 1}/{len(points)}  {el / (k + 1):.1f}s/fc  "
                  f"eta {(len(points) - k - 1) * el / (k + 1) / 60:.0f}m",
                  flush=True)
    json.dump(rows, open(out_path, "w"))
    print(f"{tag}: done, {len(rows)} forecasts", flush=True)


if __name__ == "__main__":
    main()
