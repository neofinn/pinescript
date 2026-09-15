"""Daily history for a spread of world indices and liquid ETF proxies.

ETFs are included deliberately: a cash index's "volume" is a synthetic sum,
while an ETF's is real traded shares. Which of those carries information is
tested rather than assumed.
"""
import urllib.request, json, os, time

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "idx")
os.makedirs(OUT, exist_ok=True)
H = {"User-Agent": "Mozilla/5.0"}

SYMS = {
    # India
    "NIFTY": "%5ENSEI", "BANKNIFTY": "%5ENSEBANK", "NIFTYIT": "%5ECNXIT",
    # US cash and ETF proxies
    "SP500": "%5EGSPC", "NASDAQ": "%5EIXIC", "RUSSELL2K": "%5ERUT",
    "SPY": "SPY", "QQQ": "QQQ", "IWM": "IWM",
    # Europe
    "DAX": "%5EGDAXI", "FTSE": "%5EFTSE", "CAC": "%5EFCHI", "STOXX50": "%5ESTOXX50E",
    # Asia / EM
    "NIKKEI": "%5EN225", "HANGSENG": "%5EHSI", "ASX200": "%5EAXJO",
    "KOSPI": "%5EKS11", "EEM": "EEM", "TAIEX": "%5ETWII",
}

def fetch(sym, tries=4):
    # range=max silently downgrades the interval to monthly, so the window is
    # given as explicit epoch bounds instead.
    import calendar, datetime as _dt
    p1 = calendar.timegm(_dt.datetime(1990, 1, 1).timetuple())
    p2 = calendar.timegm(_dt.datetime.now(_dt.UTC).timetuple())
    u = (f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}"
         f"?period1={p1}&period2={p2}&interval=1d")
    for a in range(tries):
        try:
            d = json.load(urllib.request.urlopen(urllib.request.Request(u, headers=H), timeout=60))
            r = d["chart"]["result"][0]; ts = r["timestamp"]; q = r["indicators"]["quote"][0]
            return [{"t": t, "o": q["open"][i], "h": q["high"][i], "l": q["low"][i],
                     "c": q["close"][i], "v": q["volume"][i] or 0}
                    for i, t in enumerate(ts) if q["close"][i] is not None]
        except Exception as e:
            if a == tries - 1: print(f"  FAIL {sym}: {type(e).__name__}"); return None
            time.sleep(2 ** a)

if __name__ == "__main__":
    got = 0
    for name, sym in SYMS.items():
        p = os.path.join(OUT, f"{name}.json")
        if os.path.exists(p): got += 1; continue
        b = fetch(sym)
        if b:
            json.dump(b, open(p, "w")); got += 1
            print(f"  {name:<12} {len(b):>6} bars", flush=True)
        time.sleep(0.3)
    print(f"\n{got}/{len(SYMS)} fetched")
