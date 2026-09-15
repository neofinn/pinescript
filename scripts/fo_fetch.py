"""NSE F&O bhavcopy: fetch, cache, and normalise the two archive formats."""
import urllib.request, urllib.error, zipfile, io, os, json, time, datetime

SC = os.path.dirname(os.path.abspath(__file__))
CACHE_NOTE = "bhavcopy files cache to scripts/fo/ (gitignored); first run refetches"
CACHE = os.path.join(SC, "fo")
os.makedirs(CACHE, exist_ok=True)
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
     "Accept": "*/*", "Referer": "https://www.nseindia.com/"}
MON = "JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split()

def urls(d):
    """UDiFF first (2024-07 onward), then the legacy path."""
    return [f"https://nsearchives.nseindia.com/content/fo/BhavCopy_NSE_FO_0_0_0_{d:%Y%m%d}_F_0000.csv.zip",
            f"https://nsearchives.nseindia.com/content/historical/DERIVATIVES/"
            f"{d.year}/{MON[d.month-1]}/fo{d:%d}{MON[d.month-1]}{d.year}bhav.csv.zip"]

def raw(d, tries=6):
    """Cached text of the day's bhavcopy, or None if NSE has no file (holiday)."""
    p = os.path.join(CACHE, f"{d:%Y%m%d}.csv")
    if os.path.exists(p):
        t = open(p, encoding="utf-8", errors="replace").read()
        return t or None
    last = None
    for u in urls(d):
        for a in range(tries):
            try:
                b = urllib.request.urlopen(urllib.request.Request(u, headers=H), timeout=45).read()
                z = zipfile.ZipFile(io.BytesIO(b))
                t = z.read(z.namelist()[0]).decode("utf-8", "replace")
                open(p, "w").write(t)
                return t
            except urllib.error.HTTPError as e:
                last = e.code
                if e.code == 404: break           # genuinely absent, try next url
                time.sleep(3.0 * (a + 1))         # 403 is often throttling
            except Exception as e:
                last = type(e).__name__; time.sleep(1.5 * (a + 1))
    if last == 404:
        open(p, "w").write("")                    # remember the holiday
        return None
    raise RuntimeError(f"{d} unavailable: {last}")

def parse(d):
    """-> list of dicts, each flagged `traded`. A settlement price on an
    untraded contract is not a price anyone could have got, so callers that
    fall back to it must say how often they did."""
    t = raw(d)
    if not t: return []
    lines = t.splitlines()
    if not lines: return []
    hdr = [c.strip() for c in lines[0].split(",")]
    out = []
    if "TradDt" in hdr:                                        # UDiFF
        ix = {c: i for i, c in enumerate(hdr)}
        for L in lines[1:]:
            f = L.split(",")
            if len(f) < len(hdr) - 4: continue
            tp = f[ix["FinInstrmTp"]]
            if tp not in ("IDO", "STO"): continue              # index / stock OPTION
            try: vol = float(f[ix["TtlTradgVol"]] or 0)
            except ValueError: vol = 0
            try:
                out.append(dict(sym=f[ix["TckrSymb"]], kind="IDO" if tp == "IDO" else "STO",
                    exp=datetime.date.fromisoformat(f[ix["XpryDt"]]),
                    strike=float(f[ix["StrkPric"]]), ot=f[ix["OptnTp"]],
                    close=float(f[ix["ClsPric"]] or 0), settle=float(f[ix["SttlmPric"]] or 0),
                    vol=vol, traded=vol > 0, oi=float(f[ix["OpnIntrst"]] or 0)))
            except (ValueError, KeyError): continue
    else:                                                      # legacy
        ix = {c: i for i, c in enumerate(hdr)}
        for L in lines[1:]:
            f = L.split(",")
            if len(f) < 13: continue
            inst = f[ix["INSTRUMENT"]]
            if inst not in ("OPTIDX", "OPTSTK"): continue
            try: con = float(f[ix["CONTRACTS"]] or 0)
            except ValueError: con = 0
            try:
                dt = f[ix["EXPIRY_DT"]]                         # 31-Jul-2014
                dd, mm, yy = dt.split("-")
                out.append(dict(sym=f[ix["SYMBOL"]], kind="IDO" if inst == "OPTIDX" else "STO",
                    exp=datetime.date(int(yy), MON.index(mm.upper()) + 1, int(dd)),
                    strike=float(f[ix["STRIKE_PR"]]), ot=f[ix["OPTION_TYP"]],
                    close=float(f[ix["CLOSE"]] or 0), settle=float(f[ix["SETTLE_PR"]] or 0),
                    vol=con, traded=con > 0, oi=float(f[ix["OPEN_INT"]] or 0)))
            except (ValueError, KeyError): continue
    return out

_MEM = {}
def parse_cached(d):
    if d not in _MEM: _MEM[d] = parse(d)
    return _MEM[d]

def monthly_expiries(d, sym):
    """The last expiry in each calendar month -- the only tenor that exists
    across the whole 2008-2026 range, since weeklies only start in 2019."""
    exps = sorted({r["exp"] for r in parse_cached(d) if r["sym"] == sym})
    last = {}
    for e in exps: last[(e.year, e.month)] = max(last.get((e.year, e.month), e), e)
    return sorted(last.values())

def chain(d, sym, ot, exp=None):
    return [r for r in parse_cached(d) if r["sym"] == sym and r["ot"] == ot
            and (exp is None or r["exp"] == exp)]
