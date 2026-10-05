"""Daily PCR for NIFTY and BANKNIFTY, rebuilt from NSE's own F&O bhavcopy.

PCR is not published as a history anywhere free, but it is derivable: the
settlement file carries open interest and volume for every option contract, so

    PCR-OI  = sum(put open interest) / sum(call open interest)
    PCR-vol = sum(put volume)        / sum(call volume)

Both are computed here for the near expiry and for all expiries, because the
two readings differ and which one a strategy means is usually left vague.

Each zip is processed and deleted, so the whole history costs a few hundred
kilobytes on disk rather than half a gigabyte.
"""
import urllib.request, zipfile, io, json, os, sys, datetime as dt, time
SC = "/tmp/claude-0/-home-user-pinescript/6b4bb2fe-c45d-5f96-b3e4-1392c689d1fc/scratchpad"
OUT = os.path.join(SC, "pcr.json")
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
     "Accept-Language": "en-US,en;q=0.9"}
SYMS = ("NIFTY", "BANKNIFTY")

def day(d):
    u = (f"https://nsearchives.nseindia.com/content/fo/"
         f"BhavCopy_NSE_FO_0_0_0_{d:%Y%m%d}_F_0000.csv.zip")
    try:
        raw = urllib.request.urlopen(urllib.request.Request(u, headers=H), timeout=45).read()
    except Exception:
        return None
    try:
        z = zipfile.ZipFile(io.BytesIO(raw))
        txt = z.read(z.namelist()[0]).decode("utf-8", errors="replace")
    except Exception:
        return None
    lines = txt.splitlines()
    hdr = lines[0].split(",")
    ix = {k: i for i, k in enumerate(hdr)}
    need = ("TckrSymb","OptnTp","OpnIntrst","TtlTradgVol","XpryDt","FinInstrmTp","UndrlygPric")
    if any(k not in ix for k in need):
        return None
    acc = {s: {} for s in SYMS}
    exps = {s: set() for s in SYMS}
    spot = {}
    for ln in lines[1:]:
        f = ln.split(",")
        if len(f) <= ix["UndrlygPric"]:
            continue
        s = f[ix["TckrSymb"]]
        if s not in SYMS or f[ix["FinInstrmTp"]] != "IDO":
            continue
        ot = f[ix["OptnTp"]]
        if ot not in ("CE","PE"):
            continue
        xp = f[ix["XpryDt"]]
        exps[s].add(xp)
        try:
            oi = float(f[ix["OpnIntrst"]] or 0); vol = float(f[ix["TtlTradgVol"]] or 0)
            spot[s] = float(f[ix["UndrlygPric"]] or 0) or spot.get(s, 0)
        except ValueError:
            continue
        a = acc[s].setdefault(xp, dict(ce_oi=0.0, pe_oi=0.0, ce_v=0.0, pe_v=0.0))
        if ot == "CE":
            a["ce_oi"] += oi; a["ce_v"] += vol
        else:
            a["pe_oi"] += oi; a["pe_v"] += vol
    out = {}
    for s in SYMS:
        if not acc[s]:
            continue
        near = min(exps[s])
        n = acc[s][near]
        tot = dict(ce_oi=0.0, pe_oi=0.0, ce_v=0.0, pe_v=0.0)
        for v in acc[s].values():
            for k in tot: tot[k] += v[k]
        out[s] = dict(
            spot=spot.get(s, 0.0),
            pcr_oi_near=(n["pe_oi"]/n["ce_oi"] if n["ce_oi"] else None),
            pcr_oi_all=(tot["pe_oi"]/tot["ce_oi"] if tot["ce_oi"] else None),
            pcr_v_near=(n["pe_v"]/n["ce_v"] if n["ce_v"] else None),
            pcr_v_all=(tot["pe_v"]/tot["ce_v"] if tot["ce_v"] else None))
    return out or None

data = json.load(open(OUT)) if os.path.exists(OUT) else {}
start = dt.date(2024, 7, 8)          # new bhavcopy naming begins here
end = dt.date.today()
d = start
got = miss = 0
while d <= end:
    k = d.isoformat()
    if d.weekday() < 5 and k not in data:
        r = day(d)
        if r:
            data[k] = r; got += 1
            if got % 25 == 0:
                json.dump(data, open(OUT, "w"))
                print(f"  {k}  {got} days  NIFTY PCR-OI "
                      f"{r.get('NIFTY',{}).get('pcr_oi_all',0):.3f}", flush=True)
        else:
            miss += 1
    d += dt.timedelta(days=1)
json.dump(data, open(OUT, "w"))
print(f"done: {len(data)} trading days, {miss} dates with no file (holidays)")
