import urllib.request, json, os, time, datetime as dt
SC="/tmp/claude-0/-home-user-pinescript/6b4bb2fe-c45d-5f96-b3e4-1392c689d1fc/scratchpad"
H={"User-Agent":"Mozilla/5.0"}
SYMS=[("ES","ES=F"),("NQ","NQ=F"),("GC","GC=F"),("SI","SI=F"),("CL","CL=F"),
      ("SPY","SPY"),("QQQ","QQQ"),("GLD","GLD"),("AAPL","AAPL"),("NVDA","NVDA"),
      ("TSLA","TSLA"),("JPM","JPM"),("BTC","BTC-USD"),("ETH","ETH-USD"),
      ("EURUSD","EURUSD=X")]
def grab(sym, p1, p2, iv):
    u=(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}"
       f"?period1={p1}&period2={p2}&interval={iv}")
    for a in range(4):
        try:
            d=json.load(urllib.request.urlopen(urllib.request.Request(u,headers=H),timeout=60))
            r=d["chart"]["result"][0]
            if "timestamp" not in r: return []
            ts=r["timestamp"];q=r["indicators"]["quote"][0]
            return [{"t":t,"o":q["open"][i],"h":q["high"][i],"l":q["low"][i],
                     "c":q["close"][i],"v":q["volume"][i] or 0} for i,t in enumerate(ts)
                    if None not in (q["open"][i],q["high"][i],q["low"][i],q["close"][i])]
        except Exception as e:
            if a==3: return []
            time.sleep(2**a)
now=int(time.time())
# 1m: Yahoo serves at most 7 days per call and only ~30 days back. Chain it.
for nm,s in SYMS:
    p=os.path.join(SC,"m1",nm+".json")
    if not os.path.exists(p):
        got={}
        for w in range(5):
            p2=now-w*7*86400; p1=p2-7*86400
            for b in grab(s,p1,p2,"1m"): got[b["t"]]=b
            time.sleep(0.4)
        b=[got[t] for t in sorted(got)]
        if len(b)>2000:
            json.dump(b,open(p,"w"))
            print(f"  1m {nm:<8}{len(b):>7} bars  "
                  f"{dt.datetime.utcfromtimestamp(b[0]['t']).date()} -> "
                  f"{dt.datetime.utcfromtimestamp(b[-1]['t']).date()}",flush=True)
        else:
            print(f"  1m {nm:<8} only {len(b)} - skipped",flush=True)
    p=os.path.join(SC,"m5",nm+".json")
    if not os.path.exists(p):
        b=grab(s,now-60*86400,now,"5m")
        if len(b)>2000:
            json.dump(b,open(p,"w"))
            print(f"  5m {nm:<8}{len(b):>7} bars",flush=True)
        time.sleep(0.4)
print("done")
