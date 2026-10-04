import urllib.request, json, os, time, datetime as dt
OUT = "/tmp/claude-0/-home-user-pinescript/6b4bb2fe-c45d-5f96-b3e4-1392c689d1fc/scratchpad/gold2"
H = {"User-Agent": "Mozilla/5.0"}
JOBS = [("GC_m15","GC=F","60d","15m"), ("GC_m30","GC=F","60d","30m"),
        ("GC_h1","GC=F","730d","1h"), ("GC_h4","GC=F","730d","1h"),
        ("GC_d","GC=F","20y","1d"),
        ("GLD_m30","GLD","60d","30m"), ("GLD_h1","GLD","730d","1h"), ("GLD_d","GLD","20y","1d"),
        ("IAU_m30","IAU","60d","30m"), ("IAU_h1","IAU","730d","1h"),
        ("GDX_m30","GDX","60d","30m"), ("GDX_h1","GDX","730d","1h"),
        ("GDXJ_h1","GDXJ","730d","1h"),
        ("SI_m30","SI=F","60d","30m"), ("SI_h1","SI=F","730d","1h"), ("SI_d","SI=F","20y","1d"),
        ("PL_m30","PL=F","60d","30m"), ("PL_h1","PL=F","730d","1h")]
def get(sym, rng, iv, tries=4):
    u = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range={rng}&interval={iv}"
    for a in range(tries):
        try:
            d = json.load(urllib.request.urlopen(urllib.request.Request(u, headers=H), timeout=60))
            r = d["chart"]["result"][0]; ts = r["timestamp"]; q = r["indicators"]["quote"][0]
            return [{"t": t, "o": q["open"][i], "h": q["high"][i], "l": q["low"][i],
                     "c": q["close"][i], "v": q["volume"][i] or 0} for i, t in enumerate(ts)
                    if None not in (q["open"][i], q["high"][i], q["low"][i], q["close"][i])]
        except Exception as e:
            if a == tries-1:
                print(f"  FAIL {sym} {iv}: {type(e).__name__}", flush=True); return None
            time.sleep(2**a)
for nm, sym, rng, iv in JOBS:
    p = os.path.join(OUT, nm + ".json")
    if os.path.exists(p): continue
    b = get(sym, rng, iv)
    if b and len(b) > 200:
        json.dump(b, open(p, "w"))
        print(f"  {nm:<10} {len(b):>6} bars  {dt.datetime.utcfromtimestamp(b[0]['t']).date()}"
              f" -> {dt.datetime.utcfromtimestamp(b[-1]['t']).date()}", flush=True)
    time.sleep(0.3)
print("done")
