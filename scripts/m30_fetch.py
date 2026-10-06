import urllib.request, json, os, time, datetime as dt
OUT="/tmp/claude-0/-home-user-pinescript/6b4bb2fe-c45d-5f96-b3e4-1392c689d1fc/scratchpad/m30"
H={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
SYMS=[("NQ","NQ=F"),("QQQ","QQQ"),("NDX","%5ENDX"),("IXIC","%5EIXIC"),
      ("ES","ES=F"),("SPY","SPY"),("SPX","%5EGSPC"),("YM","YM=F"),("RTY","RTY=F"),
      ("GC","GC=F"),("CL","CL=F"),("DAX","%5EGDAXI"),("FTSE","%5EFTSE"),
      ("NIFTY","%5ENSEI"),("BANKNIFTY","%5ENSEBANK"),
      ("AAPL","AAPL"),("NVDA","NVDA"),("TSLA","TSLA"),("MSFT","MSFT"),("AMZN","AMZN")]
def get(s):
    u=f"https://query1.finance.yahoo.com/v8/finance/chart/{s}?range=60d&interval=30m"
    for a in range(4):
        try:
            r=json.load(urllib.request.urlopen(urllib.request.Request(u,headers=H),timeout=60))["chart"]["result"][0]
            q=r["indicators"]["quote"][0]
            return [{"t":t,"o":q["open"][i],"h":q["high"][i],"l":q["low"][i],
                     "c":q["close"][i],"v":q["volume"][i] or 0}
                    for i,t in enumerate(r["timestamp"])
                    if None not in (q["open"][i],q["high"][i],q["low"][i],q["close"][i])]
        except Exception:
            if a==3: return None
            time.sleep(2**a)
for nm,s in SYMS:
    p=os.path.join(OUT,nm+".json")
    if os.path.exists(p): continue
    b=get(s)
    if b and len(b)>300:
        json.dump(b,open(p,"w"))
        print(f"  {nm:<10}{len(b):>6} bars  {dt.datetime.utcfromtimestamp(b[0]['t']).date()}"
              f" -> {dt.datetime.utcfromtimestamp(b[-1]['t']).date()}",flush=True)
    time.sleep(0.3)
print("done")
