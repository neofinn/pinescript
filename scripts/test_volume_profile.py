"""Assertions for the profile builder. Run: python3 scripts/test_volume_profile.py

These are the properties the backtest silently assumed. A profile that fails
any of them makes every number downstream of it meaningless, and three of
these were wrong at some point while this was being written.
"""
import sys, os, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import volume_profile as vp

fails = []


def check(name, cond):
    if cond:
        print(f"  ok   {name}")
    else:
        print(f"  FAIL {name}")
        fails.append(name)


def bar(t, o, h, l, c, v):
    return dict(t=t, o=o, h=h, l=l, c=c, v=v)


print("volume distribution")
hist = [0.0] * 10
vp.add_bar(hist, 0.0, 1.0, bar(0, 0, 10, 0, 5, 100))
check("uniform spread conserves volume", abs(sum(hist) - 100) < 1e-9)
check("uniform spread is uniform", max(hist) - min(hist) < 1e-9)

hist = [0.0] * 10
vp.add_bar(hist, 0.0, 1.0, bar(0, 3, 3, 3, 3, 50))
check("zero-range bar lands in one row", hist[3] == 50 and sum(hist) == 50)

hist = [0.0] * 10
vp.add_bar(hist, 0.0, 1.0, bar(0, 0, 2.5, 1.5, 2, 100))
check("partial row gets its proportion", abs(hist[1] - 50) < 1e-9
      and abs(hist[2] - 50) < 1e-9)

hist = [0.0] * 10
vp.add_bar(hist, 0.0, 1.0, bar(0, 0, 99, -99, 5, 100))
check("out-of-grid bar is clamped, not dropped", abs(sum(hist) - 100) < 1e-9)

print("\nvalue area")
h = [1, 1, 1, 10, 1, 1, 1]
poc, lo, hi = vp.value_area(h, 0.70)
check("POC is the heaviest row", poc == 3)
check("value area holds at least the target share",
      sum(h[lo:hi + 1]) >= sum(h) * 0.70 - 1e-9)
check("value area contains the POC", lo <= poc <= hi)

h = [5, 5, 5, 5, 5, 5, 5, 5]
poc, lo, hi = vp.value_area(h, 0.70)
check("flat profile still returns a valid area",
      lo <= poc <= hi and sum(h[lo:hi + 1]) >= sum(h) * 0.70 - 1e-9)

# a one-sided profile must push the area to the heavy side, not stay centred
h = [0, 0, 0, 0, 1, 3, 9, 20]
poc, lo, hi = vp.value_area(h, 0.70)
check("value area expands toward volume", lo >= 4)

print("\ncausality")
random.seed(3)
bars = []
px = 100.0
for i in range(240):                      # two sessions of 120 bars
    day = 0 if i < 120 else 1
    px += random.uniform(-0.3, 0.3)
    bars.append(bar(day * 86400 + (i % 120) * 300, px, px + 0.4, px - 0.4,
                    px + random.uniform(-0.2, 0.2), random.randint(1, 1000)))

ppoc, pvah, pval = vp.prior_levels(bars, 40)
check("first session has no prior levels", all(x is None for x in ppoc[:120]))
check("second session has them from bar one", ppoc[120] is not None)
check("prior levels are constant through the session",
      len(set(ppoc[120:240])) == 1)

dpoc, dvah, dval = vp.developing(bars, 40)
check("developing is suppressed before min_bars", dpoc[0] is None)
check("developing resets at the session boundary", dpoc[120] is None)
check("developing value area brackets its POC",
      all(dval[i] <= dpoc[i] <= dvah[i]
          for i in range(len(bars)) if dpoc[i] is not None))

# the real causality test: truncating the series must not change past values
half = vp.developing(bars[:180], 40)[0]
full = vp.developing(bars, 40)[0]
check("a bar's developing POC does not change when later bars arrive",
      all(a == b for a, b in zip(half[:180], full[:180])))

nk = vp.naked_pocs(bars, 40)
check("no naked POC exists in the first session", nk[0] == [] and nk[119] == [])
touched = [i for i in range(120, 240)
           if nk[i] and any(bars[i]["l"] <= p <= bars[i]["h"] for p in nk[i])]
check("a POC inside the bar's range is cleared, not carried", not touched)

print("\nempty and degenerate input")
check("no bars returns empty", vp.build([]) == {})
flat = vp.build([bar(0, 5, 5, 5, 5, 10)] * 5, 20)
check("all-identical bars still produce a POC", flat["poc"] is not None)
zero = vp.build([bar(0, 5, 6, 4, 5, 0)] * 5, 20)
check("zero-volume bars do not crash", zero["volume"] == 0)

print(f"\n{len(fails)} failed" if fails else "\nall passed")
sys.exit(1 if fails else 0)
