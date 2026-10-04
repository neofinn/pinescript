import json, os, sys, statistics, random, datetime as dt
sys.path.insert(0, "/home/user/pinescript/scripts")
from straddle_sar import run, shuffle_bars
from inside_bar_short import aggregate
SC = "/tmp/claude-0/-home-user-pinescript/6b4bb2fe-c45d-5f96-b3e4-1392c689d1fc/scratchpad"
OZ, SPREAD, COMM, SWAP = 1.0, 0.25, 0.07, -0.10
BPD = {"h1": 24, "h4": 6, "d1": 1}
H1 = json.load(open(os.path.join(SC,"h1","GC.json")))
D1 = json.load(open(os.path.join(SC,"d1","GC.json")))
TF = {"h1": H1, "h4": aggregate(H1,240,60), "d1": D1}

def sim(bars, tf, spread=SPREAD, comm=COMM, swap=SWAP, **kw):
    t,_ = run(bars, cost_bps=0.0, cost_abs=spread/2+comm/2,
              swap_per_bar=swap/BPD[tf], **kw)
    if not t: return None
    p = [x["pnl"]*OZ for x in t]
    eq=pk=dd=0.0
    for x in p:
        eq+=x; pk=max(pk,eq); dd=max(dd,pk-eq)
    w=sum(x for x in p if x>0); l=-sum(x for x in p if x<=0)
    return dict(n=len(t), net=eq, dd=dd, pf=(w/l if l else 99.9),
                gross=sum(x["gross"] for x in t)*OZ,
                fees=sum(x["fees"] for x in t)*OZ)

def hold_dd(bars):
    pk=bars[0]["c"]; dd=0.0
    for b in bars: pk=max(pk,b["h"]); dd=max(dd,pk-b["l"])
    return dd*OZ

print("="*88)
print("2.  THE RIGHT BENCHMARK AT 0.01 LOT: holding also has a drawdown")
print("="*88)
print(f"  {'tf':<5}{'hold net $':>13}{'hold maxDD $':>15}{'hold $/DD':>12}")
for k,v in TF.items():
    h=(v[-1]["c"]-v[0]["c"])*OZ; d=hold_dd(v)
    print(f"  {k:<5}{h:>+13,.0f}{d:>15,.0f}{h/d:>12.2f}")

CAND = [("h1", dict(entry_len=20,entry_pad=0.0,trail="donchian",trail_len=10,trail_delay=0.0,sar=False)),
        ("d1", dict(entry_len=20,entry_pad=0.0,trail="atr",atr_mult=2.0,trail_delay=0.0,sar=False)),
        ("d1", dict(entry_len=20,entry_pad=1.0,trail="atr",atr_mult=2.0,trail_delay=0.0,sar=False)),
        ("d1", dict(entry_len=20,entry_pad=0.5,trail="donchian",trail_len=20,trail_delay=2.0,sar=False))]
print("\n" + "="*88)
print("3.  RETURN PER DOLLAR OF DRAWDOWN -- what matters on a small account")
print("="*88)
print(f"  {'tf':<5}{'pad':>5}{'trail':>11}{'delay':>7}{'n':>6}{'net $':>9}"
      f"{'maxDD $':>10}{'$/DD':>7}{'PF':>7}   vs holding $/DD")
for tf,kw in CAND:
    r=sim(TF[tf],tf,**kw); h=(TF[tf][-1]["c"]-TF[tf][0]["c"])*OZ; hd=hold_dd(TF[tf])
    tn = kw.get("trail")+(f" {kw.get('atr_mult')}" if kw.get("trail")=="atr" else f" {kw.get('trail_len')}")
    print(f"  {tf:<5}{kw['entry_pad']:>5.1f}{tn:>11}{kw['trail_delay']:>7.1f}{r['n']:>6}"
          f"{r['net']:>9,.0f}{r['dd']:>10,.0f}{r['net']/r['dd']:>7.2f}{r['pf']:>7.2f}"
          f"        {h/hd:>6.2f}  {'BETTER' if r['net']/r['dd']>h/hd else 'worse'}")

print("\n" + "="*88)
print("4.  SHUFFLE CONTROL on the candidates (40 shuffles each)")
print("="*88)
rng=random.Random(5)
print(f"  {'tf':<5}{'pad':>5}{'trail':>11}{'real net $':>12}{'shuf med':>10}"
      f"{'shuf 95th':>11}{'shuf best':>11}{'pct':>6}")
for tf,kw in CAND:
    r=sim(TF[tf],tf,**kw)
    dr=[]
    for _ in range(40):
        sb=shuffle_bars(TF[tf],rng)
        q=sim(sb,tf,**kw)
        dr.append(q["net"] if q else 0.0)
    dr.sort()
    pct=100*sum(1 for x in dr if x<r["net"])/len(dr)
    tn = kw.get("trail")+(f" {kw.get('atr_mult')}" if kw.get("trail")=="atr" else f" {kw.get('trail_len')}")
    print(f"  {tf:<5}{kw['entry_pad']:>5.1f}{tn:>11}{r['net']:>12,.0f}"
          f"{dr[20]:>10,.0f}{dr[38]:>11,.0f}{dr[-1]:>11,.0f}{pct:>6.0f}", flush=True)

print("\n" + "="*88)
print("5.  COST SENSITIVITY -- retail spreads vary a lot")
print("="*88)
print(f"  {'tf':<5}{'pad':>5}{'trail':>11}{'spread':>8}{'swap/nt':>9}"
      f"{'n':>6}{'gross $':>10}{'fees $':>9}{'net $':>9}")
for tf,kw in CAND[:3]:
    for sp in (0.15, 0.25, 0.35, 0.50):
        r=sim(TF[tf],tf,spread=sp,**kw)
        tn = kw.get("trail")+(f" {kw.get('atr_mult')}" if kw.get("trail")=="atr" else f" {kw.get('trail_len')}")
        print(f"  {tf:<5}{kw['entry_pad']:>5.1f}{tn:>11}{sp:>8.2f}{SWAP:>9.2f}"
              f"{r['n']:>6}{r['gross']:>10,.0f}{r['fees']:>9,.0f}{r['net']:>9,.0f}")
    for sw in (0.0, -0.20, -0.40):
        r=sim(TF[tf],tf,swap=sw,**kw)
        print(f"  {tf:<5}{kw['entry_pad']:>5.1f}{tn:>11}{SPREAD:>8.2f}{sw:>9.2f}"
              f"{r['n']:>6}{r['gross']:>10,.0f}{r['fees']:>9,.0f}{r['net']:>9,.0f}")
    print()
