import urllib.request, json, os, time
OUT = "/tmp/claude-0/-home-user-pinescript/6b4bb2fe-c45d-5f96-b3e4-1392c689d1fc/scratchpad/idx"
H = {"User-Agent": "Mozilla/5.0"}
def get(sym, rng, iv, tries=4):
    u = (f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}"
         f"?range={rng}&interval={iv}")
    for a in range(tries):
        try:
            d = json.load(urllib.request.urlopen(urllib.request.Request(u, headers=H), timeout=60))
            r = d["chart"]["result"][0]; ts = r["timestamp"]; q = r["indicators"]["quote"][0]
            return [{"t": t, "o": q["open"][i], "h": q["high"][i], "l": q["low"][i],
                     "c": q["close"][i], "v": q["volume"][i] or 0}
                    for i, t in enumerate(ts)
                    if None not in (q["open"][i], q["high"][i], q["low"][i], q["close"][i])]
        except Exception as e:
            if a == tries - 1:
                print(f"  FAIL {sym} {iv}: {type(e).__name__} {e}", flush=True); return None
            time.sleep(2 ** a)
JOBS = []
for nm, sym in [("SPX", "%5EGSPC"), ("DJI", "%5EDJI")]:
    JOBS += [(f"{nm}_m1", sym, "7d", "1m"), (f"{nm}_m5", sym, "60d", "5m"),
             (f"{nm}_h1", sym, "730d", "1h"), (f"{nm}_d", sym, "20y", "1d")]
for name, sym, rng, iv in JOBS:
    p = os.path.join(OUT, name + ".json")
    if os.path.exists(p): continue
    b = get(sym, rng, iv)
    if b:
        json.dump(b, open(p, "w"))
        import datetime as dt
        print(f"  {name:<8} {len(b):>7} bars  "
              f"{dt.datetime.utcfromtimestamp(b[0]['t']).date()} -> "
              f"{dt.datetime.utcfromtimestamp(b[-1]['t']).date()}", flush=True)
    time.sleep(0.4)
print("done")
