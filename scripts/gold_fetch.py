import urllib.request, json, os, time
OUT = "/tmp/claude-0/-home-user-pinescript/6b4bb2fe-c45d-5f96-b3e4-1392c689d1fc/scratchpad/gold"
H = {"User-Agent": "Mozilla/5.0"}
JOBS = [
    # the requested chart
    ("GC_m30",  "GC=F",     "60d",  "30m"),
    ("GC_m15",  "GC=F",     "60d",  "15m"),
    ("GC_h1",   "GC=F",     "730d", "1h"),
    ("GC_d",    "GC=F",     "max",  "1d"),
    # the rest of the gold complex, so one window does not decide it
    ("GLD_m30", "GLD",      "60d",  "30m"),
    ("GLD_h1",  "GLD",      "730d", "1h"),
    ("IAU_m30", "IAU",      "60d",  "30m"),
    ("XAU_m30", "XAUUSD=X", "60d",  "30m"),
    ("SI_m30",  "SI=F",     "60d",  "30m"),
    ("SI_h1",   "SI=F",     "730d", "1h"),
    ("GDX_m30", "GDX",      "60d",  "30m"),
    ("GDXJ_m30","GDXJ",     "60d",  "30m"),
    ("PL_m30",  "PL=F",     "60d",  "30m"),
]
def fetch(sym, rng, iv, tries=4):
    u = (f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}"
         f"?range={rng}&interval={iv}")
    for a in range(tries):
        try:
            d = json.load(urllib.request.urlopen(urllib.request.Request(u, headers=H), timeout=60))
            r = d["chart"]["result"][0]; ts = r["timestamp"]; q = r["indicators"]["quote"][0]
            return [{"t": t, "o": q["open"][i], "h": q["high"][i], "l": q["low"][i],
                     "c": q["close"][i], "v": q["volume"][i] or 0}
                    for i, t in enumerate(ts)
                    if q["close"][i] is not None and q["high"][i] is not None
                    and q["low"][i] is not None and q["open"][i] is not None]
        except Exception as e:
            if a == tries - 1:
                print(f"  FAIL {sym} {iv}: {type(e).__name__}", flush=True); return None
            time.sleep(2 ** a)
for name, sym, rng, iv in JOBS:
    p = os.path.join(OUT, name + ".json")
    if os.path.exists(p):
        continue
    b = fetch(sym, rng, iv)
    if b:
        json.dump(b, open(p, "w"))
        print(f"  {name:<10} {sym:<9} {len(b):>6} bars", flush=True)
    time.sleep(0.3)
print("done")
