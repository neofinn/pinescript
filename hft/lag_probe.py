"""Measure the lag. Everything in this repo is downstream of an assumption.

`Spec.expected_lag_ms` says NIFTY option quotes trail their underlying by 10ms,
BANKNIFTY by 14, SENSEX by 16. Those numbers were never measured. They were
typed in, the simulator was built to reproduce them, and the strategy was then
shown to capture them -- which proves only that the simulator and the strategy
agree with each other.

This module is the instrument that settles it against a real feed. For each
option it keeps two series: theoretical value recomputed from the underlying on
every underlying tick, and the option's own microprice. If the quote lags, then
changes in theo lead changes in the quote, and the cross-correlation of the two
difference series peaks at a positive shift equal to the lag.

Two outcomes, and the second is the one worth guarding against:

  * a clear peak at tau > 0 with meaningful correlation -- the lag is real, and
    its size is the entire budget the execution path has to fit inside.
  * a flat or noisy correlation curve, or a peak at tau = 0 -- there is no lead
    to trade. The option quote is keeping up, and a strategy premised on it not
    keeping up has nothing to capture. This is the same test applied to volume
    earlier in this project: below a correlation floor the field is void, and no
    amount of parameter tuning recovers it.

The peak correlation matters more than the peak location. A lag of 12ms with a
correlation of 0.05 is not a 12ms opportunity; it is noise with an argmax.
"""
from __future__ import annotations
import math
from .clock import now_ns
from .pricing import bs_call, bs_put


class LagEstimator:
    """Cross-correlates one option's quote against its own fair value.

    Fixed-size ring buffers, sampled on a regular grid. Resampling to a grid
    rather than correlating raw event times is what makes the shift axis mean
    milliseconds instead of "number of ticks ago", which would vary with how
    busy the contract happens to be.
    """

    __slots__ = ("token", "strike", "is_call", "iv", "t_years", "grid_ns",
                 "n", "_theo", "_quote", "_i", "_filled", "_last_grid_ns",
                 "_pending_theo", "_pending_quote")

    def __init__(self, token: int, strike: float, is_call: bool, iv: float,
                 t_years: float, grid_us: int = 1_000, size: int = 4096) -> None:
        self.token = token
        self.strike = strike
        self.is_call = is_call
        self.iv = iv
        self.t_years = t_years
        self.grid_ns = grid_us * 1_000
        self.n = size
        self._theo = [0.0] * size
        self._quote = [0.0] * size
        self._i = 0
        self._filled = 0
        self._last_grid_ns = 0
        self._pending_theo = 0.0
        self._pending_quote = 0.0

    def on_underlying(self, spot: float, ts_ns: int) -> None:
        if spot <= 0.0:
            return
        self._pending_theo = (bs_call(spot, self.strike, self.t_years, self.iv)
                              if self.is_call else
                              bs_put(spot, self.strike, self.t_years, self.iv))
        self._maybe_sample(ts_ns)

    def on_quote(self, micro: float, ts_ns: int) -> None:
        if micro > 0.0:
            self._pending_quote = micro
        self._maybe_sample(ts_ns)

    def _maybe_sample(self, ts_ns: int) -> None:
        """Zero-order hold onto a fixed grid. Both series must sample at the
        same instants or the shift axis is meaningless."""
        if self._last_grid_ns == 0:
            self._last_grid_ns = ts_ns
            return
        while ts_ns - self._last_grid_ns >= self.grid_ns:
            self._last_grid_ns += self.grid_ns
            if self._pending_theo <= 0.0 or self._pending_quote <= 0.0:
                continue
            self._theo[self._i] = self._pending_theo
            self._quote[self._i] = self._pending_quote
            self._i = (self._i + 1) % self.n
            if self._filled < self.n:
                self._filled += 1

    # ── the measurement ────────────────────────────────────────────────────
    def _ordered(self) -> tuple[list[float], list[float]]:
        if self._filled < self.n:
            return self._theo[:self._filled], self._quote[:self._filled]
        i = self._i
        return self._theo[i:] + self._theo[:i], self._quote[i:] + self._quote[:i]

    def correlogram(self, max_shift: int = 60) -> list[tuple[int, float]]:
        """[(shift_in_grid_steps, corr)] for theo LEADING quote by `shift`.

        Differences, not levels. Two random walks driven by the same underlying
        correlate at ~1.0 at every shift; only their increments carry the
        timing, and a correlogram built on levels will happily report a
        confident peak that means nothing.
        """
        theo, quote = self._ordered()
        if len(theo) < max_shift + 30:
            return []
        dt = [theo[k + 1] - theo[k] for k in range(len(theo) - 1)]
        dq = [quote[k + 1] - quote[k] for k in range(len(quote) - 1)]
        out = []
        for s in range(0, max_shift + 1):
            a = dt[:len(dt) - s] if s else dt
            b = dq[s:]
            m = min(len(a), len(b))
            if m < 30:
                break
            out.append((s, _corr(a[:m], b[:m])))
        return out

    def estimate(self, max_shift: int = 60) -> dict:
        cg = self.correlogram(max_shift)
        if not cg:
            return dict(token=self.token, samples=self._filled, ok=False,
                        reason="not enough samples")
        best_s, best_c = max(cg, key=lambda x: x[1])
        zero_c = cg[0][1]
        return dict(
            token=self.token, strike=self.strike, is_call=self.is_call,
            samples=self._filled, ok=True,
            lag_ms=best_s * self.grid_ns / 1e6,
            peak_corr=best_c,
            zero_corr=zero_c,
            lead=best_c - zero_c,        # how much the shift buys over none
            curve=cg,
        )


def _corr(a: list[float], b: list[float]) -> float:
    n = len(a)
    if n < 2:
        return 0.0
    ma = sum(a) / n
    mb = sum(b) / n
    sa = sb = sab = 0.0
    for k in range(n):
        da = a[k] - ma
        db = b[k] - mb
        sa += da * da
        sb += db * db
        sab += da * db
    if sa <= 0.0 or sb <= 0.0:
        return 0.0
    return sab / math.sqrt(sa * sb)


class LagProbe:
    """One estimator per option, fed from the same handler as the engine."""

    def __init__(self, u_token: int, contracts: list[dict], iv: float,
                 t_years: float, grid_us: int = 1_000, size: int = 4096) -> None:
        self.u_token = u_token
        self.spot = 0.0
        self.est = {c["token"]: LagEstimator(c["token"], c["strike"],
                                             c["is_call"], iv, t_years,
                                             grid_us, size)
                    for c in contracts}

    def on_tick(self, token: int, bid: float, ask: float, bid_qty: int,
                ask_qty: int, last: float, ts_ns: int) -> None:
        if token == self.u_token:
            tot = bid_qty + ask_qty
            self.spot = ((bid * ask_qty + ask * bid_qty) / tot if tot > 0
                         else (bid + ask) * 0.5)
            for e in self.est.values():
                e.on_underlying(self.spot, ts_ns)
            return
        e = self.est.get(token)
        if e is None:
            return
        tot = bid_qty + ask_qty
        micro = ((bid * ask_qty + ask * bid_qty) / tot if tot > 0
                 else (bid + ask) * 0.5)
        e.on_quote(micro, ts_ns)

    def report(self, max_shift: int = 60, min_lead: float = 0.05) -> str:
        rows = [e.estimate(max_shift) for e in self.est.values()]
        good = [r for r in rows if r.get("ok")]
        if not good:
            return "  no contract collected enough samples to estimate"
        good.sort(key=lambda r: -r["lead"])
        out = [f"  {'strike':>9} {'C/P':>4} {'samples':>8} {'lag_ms':>8} "
               f"{'peak_corr':>10} {'corr@0':>8} {'lead':>8}"]
        for r in good[:12]:
            out.append(f"  {r['strike']:>9,.0f} {'C' if r['is_call'] else 'P':>4} "
                       f"{r['samples']:>8,} {r['lag_ms']:>8.1f} "
                       f"{r['peak_corr']:>10.3f} {r['zero_corr']:>8.3f} "
                       f"{r['lead']:>8.3f}")
        n_real = sum(1 for r in good if r["lead"] >= min_lead and r["lag_ms"] > 0)
        med = sorted(r["lag_ms"] for r in good)[len(good) // 2]
        out.append("")
        out.append(f"  {len(good)} contracts estimated, median lag "
                   f"{med:.1f}ms")
        out.append(f"  {n_real} of {len(good)} show a lead of at least "
                   f"{min_lead:.2f} over zero shift")
        if n_real < len(good) * 0.3:
            out.append("  VERDICT: no exploitable lead. The quote is keeping up.")
            out.append("  A strategy premised on it not keeping up has nothing")
            out.append("  to capture here, and no parameter recovers that.")
        else:
            out.append(f"  VERDICT: lead is present. {med:.1f}ms is the ENTIRE")
            out.append("  budget your feed-to-order round trip has to fit in.")
        return "\n".join(out)
