import sys, datetime

import importlib.util
import os
HERE=os.path.dirname(os.path.abspath(__file__))
spec=importlib.util.spec_from_file_location("vb", os.path.join(HERE,"volume_breakout.py"))
import io, contextlib
vb=importlib.util.module_from_spec(spec)
with contextlib.redirect_stdout(io.StringIO()):
    spec.loader.exec_module(vb)

gc1h=vb.gc1h; M=60
G=vb.gates()
PICK=["(no volume gate)","rvol > 1.0x mean20","rvol > 1.5x mean20","rvol > 2.0x mean20",
      "vol z-score > 1.0","vol = highest of 20","time-of-day rvol > 1.5x"]

def half(bars, which):
    n=len(bars); mid=n//2
    return bars[:mid] if which==0 else bars[mid:]

print("OUT-OF-SAMPLE SPLIT — does the volume gate hold in both halves?")
print("breakout + EMA trend, stop 3x ATR, no target, 1 pt cost\n")
for tf,secs in (("1h",60),("2h",120),("4h",240)):
    bars=vb.resample(gc1h,secs*M)
    d0=datetime.datetime.fromtimestamp(bars[len(bars)//2]["t"],datetime.UTC).strftime("%Y-%m")
    print(f"=== {tf}   split at {d0}")
    print(f"  {'':<24}{'H1 trds':>9}{'H1 PF':>8}{'H1 netR':>10}   |{'H2 trds':>9}{'H2 PF':>8}{'H2 netR':>10}")
    for name in PICK:
        row=f"  {name:<24}"
        for w in (0,1):
            b=half(bars,w); F=vb.vol_features(b)
            t,_=vb.run(b,F,G[name])
            if len(t)<5: row+=f"{len(t):>9}{'--':>8}{'--':>10}"
            else:
                win=[x for x in t if x>0]; gl=abs(sum(x for x in t if x<=0))
                pf=sum(win)/gl if gl>0 else 99.0
                row+=f"{len(t):>9}{pf:>8.2f}{sum(t):>+9.1f}R"
            if w==0: row+="   |"
        print(row)
    print()
