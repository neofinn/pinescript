"""A broker that fills nothing and costs nothing, for watching the state machine.

It serves real historical bars from Yahoo and reports a flat position, so the
bot's logging shows exactly which orders it would rest, at what prices, and how
the trail moves -- without an account existing anywhere.
"""
from __future__ import annotations
import json, urllib.request

RANGE = {"1d": "2y", "1h": "60d", "30m": "60d", "15m": "60d", "5m": "30d"}


class PaperBroker:
    def __init__(self, symbol: str, timeframe: str = "1d"):
        self.symbol, self.tf = symbol, timeframe
        self._orders: dict[str, dict] = {}
        self._bars: list[dict] = []

    def bars(self, symbol, timeframe, n):
        if not self._bars:
            u = (f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
                 f"?range={RANGE.get(timeframe,'2y')}&interval={timeframe}")
            r = json.load(urllib.request.urlopen(
                urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}),
                timeout=60))["chart"]["result"][0]
            q = r["indicators"]["quote"][0]
            self._bars = [{"t": t, "o": q["open"][i], "h": q["high"][i],
                           "l": q["low"][i], "c": q["close"][i]}
                          for i, t in enumerate(r["timestamp"])
                          if None not in (q["open"][i], q["high"][i],
                                          q["low"][i], q["close"][i])]
        return self._bars[-n:]

    def position(self, symbol):          return 0.0
    def open_orders(self, symbol):       return list(self._orders.values())
    def last_price(self, symbol):        return self._bars[-1]["c"] if self._bars else 0.0

    def place_stop(self, symbol, side, qty, stop, client_id, reduce_only=False):
        o = dict(client_id=client_id, side=side, qty=qty, stop=stop,
                 reduce_only=reduce_only)
        self._orders[client_id] = o
        print(f"  PAPER place {side:<4} {qty:>12.4f} stop {stop:>12.4f}  [{client_id}]")
        return o

    def cancel(self, symbol, client_id):
        if client_id in self._orders:
            print(f"  PAPER cancel [{client_id}]")
            del self._orders[client_id]
        return True
