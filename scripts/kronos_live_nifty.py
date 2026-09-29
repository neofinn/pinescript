"""A live Kronos forecast for the rest of today's NIFTY session.

Two details that decide whether the number means anything:

INCOMPLETE BARS. The most recent 5-minute bar is still forming. Feeding it as
context conditions the forecast on a partial candle whose high, low and close
are not yet what they will be -- a small leak in the wrong direction, and the
easiest way to make a live forecast look sharper than it is. Only bars whose
five minutes have fully elapsed are used.

VOLUME. NIFTY prints none. Kronos accepts OHLC alone, and it also accepts the
synthetic constituent traded-value series this repo built and cross-checked
against the index ETFs. Both are run, because a disagreement between them is
information about how much the volume channel is doing.

The forecast is probabilistic: many sampled paths, reported as a distribution
rather than a line. A single averaged path hides the only thing worth knowing,
which is how wide the model's own uncertainty is.
"""
from __future__ import annotations
import json, os, sys, time, warnings

warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd
import torch

sys.path.insert(0, "/home/user/shiyu-coder/kronos")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from model import Kronos, KronosTokenizer, KronosPredictor
import india_volume as IV

BAR = 300
SESSION_LAST_UTC = 9 * 3600 + 55 * 60      # 15:25 IST, the last 5m bar's start
LOOKBACK = 512


def complete_bars(bars, now):
    """Drop any bar still forming."""
    return [b for b in bars if b["t"] + BAR <= now]


def synth_volume(d, bars):
    tv = IV.traded_value(d, IV.NIFTY50)
    return [dict(b, v=tv.get(b["t"], 0.0)) for b in bars]


def to_df(bars):
    df = pd.DataFrame(bars)
    df["timestamps"] = pd.to_datetime(df["t"], unit="s")
    return df.rename(columns={"o": "open", "h": "high", "l": "low",
                              "c": "close", "v": "volume"})


def future_stamps(last_t, n):
    return pd.to_datetime([last_t + BAR * (k + 1) for k in range(n)], unit="s")


def run(pred, df, cols, pred_len, samples, chunk=1):
    """Sampled paths, batched.

    KronosPredictor batches `sample_count` inside one forward pass, which is
    cheaper per path -- but it returns their MEAN, not the paths. So batching
    does not give a distribution: asking for 30 in one call yields one
    averaged line, and asking for 30 in chunks of ten yields three. Since the
    spread IS the forecast here, chunk defaults to 1 and each path costs its
    own call. The batching is left reachable (chunk > 1) only for the case
    where a smoothed central path is what is wanted, and it should not be
    used to speed up a percentile.
    """
    x = df.loc[len(df) - LOOKBACK:, cols].reset_index(drop=True)
    xt = df.loc[len(df) - LOOKBACK:, "timestamps"].reset_index(drop=True)
    yt = pd.Series(future_stamps(int(df["t"].iloc[-1]), pred_len))
    paths = []
    left = samples
    while left > 0:
        k = min(chunk, left)
        f = pred.predict(df=x, x_timestamp=xt, y_timestamp=yt,
                         pred_len=pred_len, T=1.0, top_p=0.9,
                         sample_count=k, verbose=False)
        paths.append([float(v) for v in f["close"].tolist()])
        left -= k
    return np.array(paths)


def report(name, paths, spot, horizon_label):
    end = paths[:, -1]
    pct = lambda q: float(np.percentile(end, q))
    up = float((end > spot).mean() * 100)
    print(f"\n  {name} — {horizon_label}")
    print(f"    P(close above {spot:,.1f}) = {up:.0f}%")
    print(f"    median {np.median(end):>9,.1f}   "
          f"({(np.median(end) / spot - 1) * 100:+.2f}%)")
    print(f"    80% band  {pct(10):,.1f} .. {pct(90):,.1f}   "
          f"({(pct(10) / spot - 1) * 100:+.2f}% .. {(pct(90) / spot - 1) * 100:+.2f}%)")
    print(f"    full range {end.min():,.1f} .. {end.max():,.1f}")
    return dict(p_up=up, median=float(np.median(end)), p10=pct(10),
                p90=pct(90), lo=float(end.min()), hi=float(end.max()))


def main():
    d = sys.argv[1]
    samples = int(sys.argv[2]) if len(sys.argv) > 2 else 30
    now = int(time.time())
    raw = json.load(open(os.path.join(d, "NIFTY.json")))
    bars = complete_bars(raw, now)
    dropped = len(raw) - len(bars)
    last = bars[-1]
    import datetime as dt
    lt = dt.datetime.utcfromtimestamp(last["t"])
    ist = lt + dt.timedelta(hours=5, minutes=30)
    left = max(0, (SESSION_LAST_UTC - (last["t"] % 86400)) // BAR)
    print(f"NIFTY 50 — live Kronos forecast")
    print(f"  last COMPLETE bar {lt:%Y-%m-%d %H:%M} UTC / {ist:%H:%M} IST  "
          f"close {last['c']:,.2f}   ({dropped} forming bar dropped)")
    print(f"  bars left in session: {left}")

    torch.set_num_threads(4)
    tok = KronosTokenizer.from_pretrained("NeoQuasar/Kronos-Tokenizer-base")
    mdl = Kronos.from_pretrained("NeoQuasar/Kronos-small")
    pred = KronosPredictor(mdl, tok, device="cpu", max_context=LOOKBACK)

    spot = float(last["c"])
    out = {}
    variants = [("OHLC only", to_df(bars), ["open", "high", "low", "close"])]
    sv = synth_volume(d, bars)
    if sum(1 for b in sv if b["v"] > 0) > len(sv) * 0.8:
        variants.append(("OHLC + synthetic volume", to_df(sv),
                         ["open", "high", "low", "close", "volume"]))
    else:
        print("  (synthetic volume too sparse on this window — skipped)")

    for horizon, hl in ((12, "1 hour ahead"), (left, "rest of session")):
        if horizon < 1:
            continue
        for name, df, cols in variants:
            t0 = time.time()
            paths = run(pred, df, cols, horizon, samples)
            out[f"{name}|{hl}"] = report(name, paths, spot, hl)
            out[f"{name}|{hl}"]["secs"] = round(time.time() - t0, 1)
            out[f"{name}|{hl}"]["paths_end"] = [float(v) for v in paths[:, -1]]
    out["_meta"] = dict(spot=spot, last_bar_utc=int(last["t"]),
                        bars_left=int(left), samples=samples)
    json.dump(out, open(os.path.join(d, "nifty_forecast.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
