import sys, json, http.cookiejar, urllib.request, time
sys.path.insert(0,'/home/user/pinescript')
UA=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")

def try_nse(sym):
    jar=http.cookiejar.CookieJar()
    op=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    h={"User-Agent":UA,"Accept":"application/json","Accept-Language":"en-US,en;q=0.9",
       "Referer":"https://www.nseindia.com/option-chain"}
    try:
        op.open(urllib.request.Request("https://www.nseindia.com/option-chain",headers=h),timeout=15)
        r=op.open(urllib.request.Request(
            f"https://www.nseindia.com/api/option-chain-indices?symbol={sym}",headers=h),timeout=15)
        d=json.load(r); rec=d["records"]
        return True, f"spot {rec['underlyingValue']}  {len(rec['data'])} rows"
    except Exception as e:
        return False, f"{type(e).__name__} {str(e)[:70]}"

def try_bse():
    h={"User-Agent":UA,"Accept":"application/json","Referer":"https://www.bseindia.com/"}
    url=("https://api.bseindia.com/BseIndiaAPI/api/DerivOptionChain/w"
         "?Scripcode=1&Expiry=&Type=IO")
    try:
        r=urllib.request.urlopen(urllib.request.Request(url,headers=h),timeout=15)
        d=json.load(r)
        return True, f"{len(d) if isinstance(d,list) else 'payload'} received"
    except Exception as e:
        return False, f"{type(e).__name__} {str(e)[:70]}"

print("LIVE FEED PREFLIGHT")
for sym in ("NIFTY","BANKNIFTY"):
    ok,msg = try_nse(sym)
    print(f"  {'OK ' if ok else 'BLOCKED'}  NSE  {sym:<11} {msg}")
    time.sleep(1)
ok,msg = try_bse()
print(f"  {'OK ' if ok else 'BLOCKED'}  BSE  {'SENSEX':<11} {msg}")
