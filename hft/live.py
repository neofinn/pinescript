"""Live runner. Paper by default; sending orders takes an explicit flag.

Why this must run on YOUR machine: NSE's option chain endpoint rejects
datacenter and cloud IPs outright (403), which is why it could not be exercised
from the environment this was written in. From a normal connection it responds.

Sizing here is for a specific account, not a template. At 5,00,000 with NIFTY
near 23,200 and a 65 lot, one at-the-money weekly lot is roughly 6,500-9,000 of
premium -- between 1.3% and 1.8% of the account. A 2% risk budget therefore buys
exactly one lot, and max_pos_lots is set to that rather than to a rounder number
that would quietly let the account run at 5% a trade.
"""
from __future__ import annotations
import argparse, asyncio, http.cookiejar, json, sys, urllib.request
from datetime import datetime

from .clock import now_ns
from .engine import Engine
from .risk import RiskGate
from .session import SessionWindow, Phase, IST
from .signals import OptionSignal
from .pricing import implied_vol

NSE_HOME = "https://www.nseindia.com/option-chain"
NSE_CHAIN = "https://www.nseindia.com/api/option-chain-indices?symbol={sym}"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")


class NSEChain:
    """Cookie-primed option chain reader.

    NSE hands out a session cookie on the HTML page and rejects the JSON
    endpoint without it, so the home page is fetched first and the jar reused.
    """

    def __init__(self, symbol: str = "NIFTY") -> None:
        self.symbol = symbol
        self.jar = http.cookiejar.CookieJar()
        self.op = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.jar))
        self.headers = {"User-Agent": UA, "Accept": "application/json",
                        "Accept-Language": "en-US,en;q=0.9", "Referer": NSE_HOME}
        self._primed = False

    def prime(self, timeout: int = 20) -> None:
        self.op.open(urllib.request.Request(NSE_HOME, headers=self.headers),
                     timeout=timeout)
        self._primed = True

    def fetch(self, timeout: int = 20) -> dict:
        if not self._primed:
            self.prime()
        r = self.op.open(urllib.request.Request(
            NSE_CHAIN.format(sym=self.symbol), headers=self.headers), timeout=timeout)
        return json.load(r)


def preflight(sym: str) -> tuple[bool, dict | None, str]:
    """Prove the feed works BEFORE arming anything. Fail loudly, not at 09:15."""
    try:
        ch = NSEChain(sym)
        d = ch.fetch()
        rec = d.get("records") or {}
        spot = rec.get("underlyingValue")
        if not spot:
            return False, None, "chain returned no underlyingValue"
        return True, d, f"OK  {sym} {spot}  expiries={rec['expiryDates'][:2]}"
    except Exception as e:
        return False, None, f"{type(e).__name__}: {str(e)[:200]}"


def build_signals(chain: dict, capital: float, lot: int, tick: float,
                  n_strikes: int, min_edge_ticks: float):
    """ATM-centred strikes, IV solved once per contract from its own quote."""
    rec = chain["records"]
    spot = float(rec["underlyingValue"])
    expiry = rec["expiryDates"][0]
    rows = [r for r in rec["data"] if r.get("expiryDate") == expiry]
    if not rows:
        return spot, expiry, [], 0.0
    strikes = sorted({float(r["strikePrice"]) for r in rows})
    atm = min(strikes, key=lambda k: abs(k - spot))
    i = strikes.index(atm)
    keep = set(strikes[max(0, i - n_strikes): i + n_strikes + 1])

    exp_dt = datetime.strptime(expiry, "%d-%b-%Y").replace(tzinfo=IST)
    t_years = max((exp_dt - datetime.now(IST)).total_seconds(), 60.0) / (365 * 86400)

    out = []
    tok = 1
    for r in rows:
        k = float(r["strikePrice"])
        if k not in keep:
            continue
        for side, is_call in (("CE", True), ("PE", False)):
            leg = r.get(side)
            if not leg:
                continue
            bid, ask = leg.get("bidprice") or 0.0, leg.get("askPrice") or 0.0
            ltp = leg.get("lastPrice") or 0.0
            mid = (bid + ask) / 2 if bid > 0 and ask > 0 else ltp
            if mid <= 0:
                continue
            iv = implied_vol(mid, spot, k, t_years, is_call)
            if iv is None or iv <= 0.01:
                # NSE publishes its own IV; fall back to it rather than guessing
                iv = (leg.get("impliedVolatility") or 0.0) / 100.0
            if iv <= 0.01:
                continue
            tok += 1
            out.append(OptionSignal(tok, k, is_call, iv, lot, tick,
                                    min_edge_ticks=min_edge_ticks))
    return spot, expiry, out, t_years


def sizing_report(capital: float, spot: float, lot: int, atm_prem: float) -> str:
    per_lot = atm_prem * lot
    risk2 = capital * 0.02
    lots = int(risk2 // per_lot) if per_lot > 0 else 0
    return (f"  capital            {capital:>12,.0f}\n"
            f"  NIFTY spot         {spot:>12,.1f}\n"
            f"  lot size           {lot:>12}\n"
            f"  ATM premium/lot    {per_lot:>12,.0f}   "
            f"({per_lot / capital * 100:.2f}% of capital)\n"
            f"  2% risk budget     {risk2:>12,.0f}\n"
            f"  -> lots affordable {lots:>12}   "
            f"{'(one lot IS the trade)' if lots <= 1 else ''}")


async def run(args) -> int:
    ok, chain, msg = preflight(args.symbol)
    print(f"PREFLIGHT  {msg}")
    if not ok:
        print("\n  NSE rejects datacenter and cloud IPs. Run this from your own\n"
              "  machine or your colo box; the code is unchanged.", file=sys.stderr)
        return 2

    spot, expiry, sigs, t_years = build_signals(
        chain, args.capital, args.lot, args.tick, args.strikes, args.edge_ticks)
    if not sigs:
        print("no priceable contracts", file=sys.stderr)
        return 2

    atm = min(sigs, key=lambda s: abs(s.strike - spot))
    from .pricing import bs_call, bs_put
    atm_prem = (bs_call if atm.is_call else bs_put)(spot, atm.strike, t_years, atm.iv)
    print(f"\nCHAIN      expiry {expiry}  {len(sigs)} contracts  "
          f"ATM {atm.strike:.0f}  IV {atm.iv*100:.1f}%  T {t_years*365:.2f}d")
    print(f"\nSIZING FOR THIS ACCOUNT\n{sizing_report(args.capital, spot, args.lot, atm_prem)}")

    max_lots = max(1, int((args.capital * 0.02) // (atm_prem * args.lot)))
    risk = RiskGate(max_pos_lots=max_lots,
                    max_net_delta=args.lot * 0.6 * max_lots * 2,
                    max_order_value=atm_prem * args.lot * max_lots * 1.5,
                    max_orders=args.max_orders,
                    max_daily_loss=args.capital * 0.02,
                    orders_per_sec=args.orders_per_sec)
    win = SessionWindow(warmup_s=args.warmup, active_s=args.active, flatten_s=60)
    eng = Engine(1, sigs, risk, None, win, t_years)

    print(f"\nRISK GATE  max_lots={max_lots}  max_delta={risk.max_net_delta:.0f}  "
          f"max_loss={risk.max_daily_loss:,.0f}  orders/s={args.orders_per_sec}")
    print(f"WINDOW     warmup {args.warmup}s, active {args.active}s, then flat")
    print(f"MODE       {'LIVE ORDERS' if args.live else 'PAPER (no orders sent)'}")
    if args.live:
        print("\n  --live is declared but no Gateway is wired. Implement\n"
              "  adapters/base.Gateway for your broker and pass it to Engine.",
              file=sys.stderr)
        return 2
    print("\nPaper mode: this prints what it WOULD send. Poll the chain and feed\n"
          "eng.on_tick(token, bid, ask, bid_qty, ask_qty, ltp, now_ns()).")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Live opening-window options runner")
    p.add_argument("--symbol", default="NIFTY")
    p.add_argument("--capital", type=float, default=500_000.0)
    p.add_argument("--lot", type=int, default=65,
                   help="NIFTY lot; it has changed repeatedly, check bhavcopy")
    p.add_argument("--tick", type=float, default=0.05)
    p.add_argument("--strikes", type=int, default=5)
    p.add_argument("--edge-ticks", type=float, default=3.0)
    p.add_argument("--warmup", type=int, default=20)
    p.add_argument("--active", type=int, default=300)
    p.add_argument("--max-orders", type=int, default=40)
    p.add_argument("--orders-per-sec", type=float, default=5.0)
    p.add_argument("--live", action="store_true",
                   help="send real orders (needs a Gateway; refuses without one)")
    return asyncio.run(run(p.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
