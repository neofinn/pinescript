"""Hourly bars for NIFTY and its constituents, 730 sessions.

The index prints no volume of its own at any timeframe, so the volume surge
gate has to be built from the constituents here exactly as it was on the daily
study. They do carry intraday volume; the index does not.
"""
import urllib.request, json, os, time, datetime

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "intra")
os.makedirs(OUT, exist_ok=True)
H = {"User-Agent": "Mozilla/5.0"}

TICKERS = """
ADANIENT ADANIPORTS APOLLOHOSP ASIANPAINT AXISBANK BAJAJ-AUTO BAJFINANCE BAJAJFINSV
BEL BHARTIARTL CIPLA COALINDIA DRREDDY EICHERMOT ETERNAL GRASIM HCLTECH HDFCBANK
HDFCLIFE HEROMOTOCO HINDALCO HINDUNILVR ICICIBANK INDUSINDBK INFY ITC JIOFIN JSWSTEEL
KOTAKBANK LT M&M MARUTI NESTLEIND NTPC ONGC POWERGRID RELIANCE SBILIFE SBIN SHRIRAMFIN
SUNPHARMA TATACONSUM TATAMOTORS TATASTEEL TCS TECHM TITAN TRENT ULTRACEMCO WIPRO
""".split()

def fetch(sym, tries=4):
    u = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range=730d&interval=1h"
    for a in range(tries):
        try:
            d = json.load(urllib.request.urlopen(urllib.request.Request(u, headers=H), timeout=60))
            r = d["chart"]["result"][0]; ts = r["timestamp"]; q = r["indicators"]["quote"][0]
            return [{"t": t, "o": q["open"][i], "h": q["high"][i], "l": q["low"][i],
                     "c": q["close"][i], "v": q["volume"][i] or 0}
                    for i, t in enumerate(ts) if q["close"][i] is not None]
        except Exception as e:
            if a == tries - 1:
                print(f"  FAIL {sym}: {type(e).__name__}"); return None
            time.sleep(2 ** a)

if __name__ == "__main__":
    jobs = [("NIFTY", "%5ENSEI")] + [(s, s + ".NS") for s in TICKERS]
    got = 0
    for i, (name, sym) in enumerate(jobs):
        p = os.path.join(OUT, f"{name}.json")
        if os.path.exists(p): got += 1; continue
        b = fetch(sym)
        if b:
            json.dump(b, open(p, "w")); got += 1
            print(f"  {i+1:>2}/{len(jobs)} {name:<12} {len(b):>5} bars", flush=True)
        time.sleep(0.35)
    print(f"\n{got}/{len(jobs)} fetched")
