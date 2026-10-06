"""Kronos forecasts only where the VWAP screener fired.

The screen is what makes this affordable: four names a session instead of
twenty, 684 forecasts instead of twenty thousand bars. It is also the honest
order of operations -- the screen uses only VWAP, which is known at the moment
it runs, so no forecast is spent on a name the strategy would not have looked
at, and no screen decision is informed by a forecast.

Horizon is 5 hourly bars, roughly the rest of the session from the second bar,
because that is the trade being modelled. The 12-bar horizon used in the skill
evaluation would run into the next day.
"""
from __future__ import annotations
import json, os, sys, time, warnings

warnings.filterwarnings("ignore")
import pandas as pd
import torch

sys.path.insert(0, "/home/user/shiyu-coder/kronos")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from model import Kronos, KronosTokenizer, KronosPredictor
from fno_vwap_screen import load_top20

LOOKBACK = 512
PRED_LEN = 5
SAMPLES = 5


def main():
    d = sys.argv[1]
    out_path = os.path.join(d, "screen_forecasts.json")
    hits = json.load(open(os.path.join(d, "fno_screen.json")))
    data = load_top20(d)
    torch.set_num_threads(4)
    tok = KronosTokenizer.from_pretrained("NeoQuasar/Kronos-Tokenizer-base")
    mdl = Kronos.from_pretrained("NeoQuasar/Kronos-small")
    pred = KronosPredictor(mdl, tok, device="cpu", max_context=LOOKBACK)

    rows = json.load(open(out_path)) if os.path.exists(out_path) else []
    done = {(r["sym"], r["i"]) for r in rows}
    todo = [h for h in hits if (h[1], h[2]) not in done and h[2] >= LOOKBACK]
    print(f"{len(todo)} forecasts to make ({len(done)} cached, "
          f"{len(hits) - len(todo) - len(done)} skipped for short history)",
          flush=True)
    t0 = time.time()
    for k, (day, sym, i, side, ext) in enumerate(todo):
        bars = data[sym]
        if i + PRED_LEN >= len(bars):
            continue
        df = pd.DataFrame(bars)
        df["timestamps"] = pd.to_datetime(df["t"], unit="s")
        df = df.rename(columns={"o": "open", "h": "high", "l": "low",
                                "c": "close", "v": "volume"})
        x = df.loc[i - LOOKBACK:i - 1,
                   ["open", "high", "low", "close", "volume"]].reset_index(drop=True)
        xt = df.loc[i - LOOKBACK:i - 1, "timestamps"].reset_index(drop=True)
        yt = df.loc[i:i + PRED_LEN - 1, "timestamps"].reset_index(drop=True)
        try:
            f = pred.predict(df=x, x_timestamp=xt, y_timestamp=yt,
                             pred_len=PRED_LEN, T=1.0, top_p=0.9,
                             sample_count=SAMPLES, verbose=False)
        except Exception as e:
            print(f"  skip {sym}@{i}: {type(e).__name__}", flush=True)
            continue
        rows.append(dict(day=day, sym=sym, i=int(i), side_hint=int(side),
                         ext=float(ext), last_close=float(df.loc[i - 1, "close"]),
                         entry_open=float(df.loc[i, "open"]),
                         p_close=[float(v) for v in f["close"].tolist()],
                         a_close=[float(v) for v in
                                  df.loc[i:i + PRED_LEN - 1, "close"].tolist()]))
        if (k + 1) % 25 == 0 or k == len(todo) - 1:
            json.dump(rows, open(out_path, "w"))
            el = time.time() - t0
            print(f"  {k+1}/{len(todo)}  {el/(k+1):.1f}s/fc  "
                  f"eta {(len(todo)-k-1)*el/(k+1)/60:.0f}m", flush=True)
    json.dump(rows, open(out_path, "w"))
    print(f"done: {len(rows)} forecasts", flush=True)


if __name__ == "__main__":
    main()
