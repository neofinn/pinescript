"""September 2026 only: E-mini S&P futures against NIFTY options, same rules.

The point of running these side by side is that ONE OF THEM HAS ALMOST NO
MODELLING IN IT. ES profit is (exit - entry) x $50 x contracts, with a published
commission and a one-tick spread. The NIFTY sleeve needs a Black-Scholes price
off India VIX with no smile, a lot size, a strike ladder and an expiry rule.
Where the two disagree, the futures number is the more trustworthy one, and the
size of the disagreement is itself the measurement.

SAMPLE, STATED UP FRONT. One month is small and the two markets are not equally
small. ES trades roughly 23 hours a day and NSE 6.25, so September gives 149
non-overlapping 15-minute forecasts on ES and 39 on NIFTY -- a four-to-one
difference that has nothing to do with either strategy. A NIFTY result from 39
forecasts cannot be held to the same standard as an ES result from 149, and the
matched control is what keeps that honest: each is scored against what shuffling
ITS OWN predicted directions produces at ITS OWN trade count.

Capital is $25,000 a sleeve, with the NIFTY sleeve converted at the spot rate
recorded in fx.json rather than a round number.
"""
from __future__ import annotations
import datetime as dt
import json, os, statistics, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import kronos_zone_strategy as KZ
import zones as Z
from futures_strategy import run as fut_run, stats as fut_stats
from india_options import SPEC

USD = 25_000.0


def sept_only(fc):
    out = []
    for f in fc:
        d = dt.datetime.utcfromtimestamp(f["t"])
        if d.year == 2026 and d.month == 9:
            out.append(f)
    return out


def es_sleeve(d, start, shuffle=None, rr=1.5, gate=False, contract="MES"):
    bars = json.load(open(os.path.join(d, "htf", "ES_m15.json")))
    fc = sept_only(json.load(open(os.path.join(d, "htf_fc", "ES_m15.json"))))
    if len(fc) < 10:
        return None
    return fut_run(bars, fc, contract, start, rr=rr, use_gate=gate,
                   shuffle=shuffle, max_hold=16) + (len(fc),)


def nifty_sleeve(d, start_inr, shuffle=None, rr=1.5, gate=False):
    bars = json.load(open(os.path.join(d, "htf", "NIFTY_m15.json")))
    fc = sept_only(json.load(open(os.path.join(d, "htf_fc", "NIFTY_m15.json"))))
    if len(fc) < 10:
        return None
    if shuffle is not None:
        fc = KZ.shuffled_forecasts(fc, shuffle)
    vix = {}
    for b in json.load(open(os.path.join(d, "live", "INDIAVIX.json"))):
        k = str(dt.datetime.utcfromtimestamp(b["t"]).date())
        if k not in vix:
            vix[k] = b["c"]
    zn = Z.find_zones(bars)
    med = statistics.median(
        abs((f["p_close"][-1] - f["last_close"]) / f["last_close"]) for f in fc)
    plan = KZ.build_plan(bars, fc, zn, med, rr, gate)
    lo = min(f["i"] for f in fc)
    KZ.CAP0 = start_inr
    tr, eq, dated = KZ.run(bars, plan, vix, SPEC["NIFTY"], rr, lo, len(bars))
    return tr, eq, dated, len(fc)


def main():
    d = sys.argv[1]
    fx = json.load(open(os.path.join(d, "fx.json")))["usdinr"]
    inr = USD * fx
    print(f"SEPTEMBER 2026 ONLY — E-mini S&P futures vs NIFTY options")
    print(f"${USD:,.0f} per sleeve (NIFTY = Rs {inr:,.0f} at {fx:.2f}), "
          f"15-minute bars, 5% cap, compounding\n")

    e = es_sleeve(d, USD)
    n = nifty_sleeve(d, inr)
    rows = []
    print(f"{'sleeve':<22}{'fc':>5}{'n':>5}{'final':>16}{'x':>7}{'PF':>7}"
          f"{'win%':>7}{'maxDD%':>9}")
    if e:
        tr, eq, nfc = e
        s = fut_stats(tr, USD)
        if s:
            rows.append(("ES futures (MES)", s, eq, USD, nfc, "$"))
            print(f"{'ES futures (MES)':<22}{nfc:>5}{s['n']:>5}"
                  f"{'$' + format(eq, ',.0f'):>16}{eq/USD:>7.2f}{s['pf']:>7.2f}"
                  f"{s['win']:>7.1f}{s['dd']:>9.1f}")
    if n:
        tr, eq, dated, nfc = n
        from portfolio_split import curve
        _, dd, _ = curve(dated, inr)
        # dated rows are (date, pnl, equity_at_entry); only pnl is wanted here
        pnls = [x[1] for x in dated]
        w = sum(p for p in pnls if p > 0)
        l = -sum(p for p in pnls if p <= 0)
        pf = (w / l) if l else float("inf")
        win = 100.0 * sum(1 for p in pnls if p > 0) / len(pnls)
        print(f"{'NIFTY options':<22}{nfc:>5}{len(dated):>5}"
              f"{'Rs ' + format(eq, ',.0f'):>16}{eq/inr:>7.2f}{pf:>7.2f}"
              f"{win:>7.1f}{dd:>9.1f}")
        rows.append(("NIFTY options", dict(n=len(dated), pf=pf, dd=dd), eq, inr,
                     nfc, "Rs"))

    print(f"\ndirection-shuffled controls, matched to each sleeve's own count:")
    for label, fn, base in (("ES futures", es_sleeve, USD),
                            ("NIFTY options", nifty_sleeve, inr)):
        sh = []
        for k in range(200):
            r = fn(d, base, shuffle=41000 + k)
            if r:
                sh.append(r[1])
        if len(sh) < 20:
            print(f"  {label}: control unavailable")
            continue
        sh.sort()
        real = (e[1] if label.startswith("ES") else n[1])
        pct = 100.0 * sum(1 for x in sh if x < real) / len(sh)
        unit = "$" if label.startswith("ES") else "Rs "
        print(f"  {label:<16}{len(sh):>4} draws   median {unit}"
              f"{statistics.median(sh):,.0f}   real at the {pct:.0f}th percentile")


if __name__ == "__main__":
    main()
