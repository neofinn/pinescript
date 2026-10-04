import urllib.request, json, os, time
OUT = "/tmp/claude-0/-home-user-pinescript/6b4bb2fe-c45d-5f96-b3e4-1392c689d1fc/scratchpad/h1"
H = {"User-Agent": "Mozilla/5.0"}
SYMS = [
    ("ES","ES=F"),("NQ","NQ=F"),("YM","YM=F"),("RTY","RTY=F"),
    ("GC","GC=F"),("SI","SI=F"),("CL","CL=F"),("NG","NG=F"),
    ("SPX","%5EGSPC"),("DJI","%5EDJI"),("NDX","%5ENDX"),("RUT","%5ERUT"),
    ("NIFTY","%5ENSEI"),("SENSEX","%5EBSESN"),("BANKNIFTY","%5ENSEBANK"),
    ("FTSE","%5EFTSE"),("DAX","%5EGDAXI"),("N225","%5EN225"),
    ("SPY","SPY"),("QQQ","QQQ"),("GLD","GLD"),("TLT","TLT"),
    ("AAPL","AAPL"),("NVDA","NVDA"),("TSLA","TSLA"),("JPM","JPM"),
    ("EURUSD","EURUSD=X"),("JPY","JPY=X"),("BTC","BTC-USD"),("ETH","ETH-USD"),
]
def get(sym, tries=4):
    u = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range=730d&interval=1h"
    for a in range(tries):
        try:
            d = json.load(urllib.request.urlopen(urllib.request.Request(u, headers=H), timeout=60))
            r = d["chart"]["result"][0]; ts = r["timestamp"]; q = r["indicators"]["quote"][0]
            return [{"t": t, "o": q["open"][i], "h": q["high"][i], "l": q["low"][i],
                     "c": q["close"][i], "v": q["volume"][i] or 0}
                    for i, t in enumerate(ts)
                    if None not in (q["open"][i], q["high"][i], q["low"][i], q["close"][i])]
        except Exception as e:
            if a == tries-1:
                print(f"  FAIL {sym}: {type(e).__name__}", flush=True); return None
            time.sleep(2**a)
ok = 0
for nm, sym in SYMS:
    p = os.path.join(OUT, nm + ".json")
    if os.path.exists(p): ok += 1; continue
    b = get(sym)
    if b and len(b) > 500:
        json.dump(b, open(p, "w")); ok += 1
        print(f"  {nm:<10} {len(b):>6} bars", flush=True)
    time.sleep(0.3)
print(f"{ok}/{len(SYMS)} ready")
