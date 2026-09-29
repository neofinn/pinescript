import urllib.request, json, os, time, sys

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "n50")
os.makedirs(OUT, exist_ok=True)

# NIFTY 50 as currently constituted. Using today's list over 19 years of history
# is survivorship bias -- names that were dropped are missing and names that were
# added appear before they joined. It is noted in the report rather than hidden.
TICKERS = """
ADANIENT ADANIPORTS APOLLOHOSP ASIANPAINT AXISBANK BAJAJ-AUTO BAJFINANCE BAJAJFINSV
BEL BHARTIARTL CIPLA COALINDIA DRREDDY EICHERMOT ETERNAL GRASIM HCLTECH HDFCBANK
HDFCLIFE HEROMOTOCO HINDALCO HINDUNILVR ICICIBANK INDUSINDBK INFY ITC JIOFIN JSWSTEEL
KOTAKBANK LT M&M MARUTI NESTLEIND NTPC ONGC POWERGRID RELIANCE SBILIFE SBIN SHRIRAMFIN
SUNPHARMA TATACONSUM TATAMOTORS TATASTEEL TCS TECHM TITAN TRENT ULTRACEMCO WIPRO
""".split()

def fetch(sym, tries=4):
    u = (f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}.NS"
         f"?range=25y&interval=1d")
    for a in range(tries):
        try:
            r = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
            d = json.load(urllib.request.urlopen(r, timeout=45))
            res = d["chart"]["result"][0]
            ts = res["timestamp"]; q = res["indicators"]["quote"][0]
            bars = [{"t": t, "o": q["open"][i], "h": q["high"][i], "l": q["low"][i],
                     "c": q["close"][i], "v": q["volume"][i] or 0}
                    for i, t in enumerate(ts) if q["close"][i] is not None]
            return bars
        except Exception as e:
            if a == tries - 1:
                print(f"  FAIL {sym}: {type(e).__name__} {e}", flush=True)
                return None
            time.sleep(2 ** a)

got = 0
for i, s in enumerate(TICKERS):
    p = os.path.join(OUT, f"{s}.json")
    if os.path.exists(p):
        got += 1; continue
    b = fetch(s)
    if b:
        json.dump(b, open(p, "w")); got += 1
        print(f"  {i+1:>2}/{len(TICKERS)} {s:<12} {len(b):>5} bars", flush=True)
    time.sleep(0.4)
print(f"\n{got}/{len(TICKERS)} constituents fetched")
