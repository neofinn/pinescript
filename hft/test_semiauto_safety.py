"""The safety rules are the part that must not be wrong. Test them directly."""
import sys; sys.path.insert(0,"/home/user/pinescript")
from hft.intent import IntentBook, Side, Reject, IState
from hft.execution import Executor, Act
from hft.orders import OrdType

ok=lambda c,m: print(f"  {'PASS' if c else 'FAIL'}  {m}")

print("1. Nothing executes before arming")
ib=IntentBook()
ok(ib.submit(Side.LONG,5,net_position=0) is Reject.NOT_ARMED, "unarmed -> NOT_ARMED")
ib.arm()
ok(ib.submit(Side.LONG,5,net_position=0) is Reject.OK, "armed -> accepted")

print("\n2. A kill is one-way and cancels the working intent")
ib.kill()
ok(ib.current.state is IState.CANCELLED, "working intent cancelled")
ok(ib.submit(Side.LONG,5,net_position=0) is Reject.KILLED, "further calls refused")
ok(ib.submit(Side.SHORT,5,net_position=0) is Reject.KILLED, "even the other side")
ib.re_arm()
ok(ib.submit(Side.LONG,3,net_position=0) is Reject.OK, "only an explicit re-arm clears it")

print("\n3. A reversal must go through flat, and is rate-limited")
ib2=IntentBook(flip_cooldown_s=10.0); ib2.arm()
ib2.submit(Side.LONG,5,net_position=0)
r=ib2.submit(Side.SHORT,5,net_position=+5)
ok(r is Reject.OK and ib2.current.state is IState.REDUCING,
   "flip while long -> REDUCING, not a naked short")
r2=ib2.submit(Side.LONG,5,net_position=-5)
ok(r2 is Reject.FLIP_COOLDOWN, "second flip inside the cooldown is REFUSED")
ok(ib2.current.side is Side.SHORT, "and the refused flip did not overwrite the live one")

print("\n4. Same-side duplicates are refused (fat finger on the same call)")
ib3=IntentBook(); ib3.arm(); ib3.submit(Side.LONG,5,net_position=0)
ok(ib3.submit(Side.LONG,5,net_position=0) is Reject.SAME_SIDE_ACTIVE,
   "repeat of a working call -> SAME_SIDE_ACTIVE")

print("\n5. Bad size is refused")
ib4=IntentBook(); ib4.arm()
ok(ib4.submit(Side.LONG,0,net_position=0) is Reject.BAD_SIZE, "zero lots refused")
ok(ib4.submit(Side.LONG,-3,net_position=0) is Reject.BAD_SIZE, "negative lots refused")

print("\n6. No-chase: the algo STOPS rather than following price")
ex=Executor(tick=0.05, max_slip_ticks=8.0, cross_at=0.0)   # always aggressive
ib5=IntentBook(); ib5.arm(); ib5.submit(Side.LONG,10,urgency=1.0,ttl_s=60,
                                        arrival_px=100.00, net_position=0)
it=ib5.working()
p=ex.plan(it, bid=100.00, ask=100.05, bid_lots=50, ask_lots=50,
          recent_lots=200, resting_age_ms=None, position=0)
ok(p.act is Act.CROSS, "at arrival, crosses normally")
p2=ex.plan(it, bid=100.45, ask=100.50, bid_lots=50, ask_lots=50,
           recent_lots=200, resting_age_ms=None, position=0)
ok(p2.act is Act.STOP, "9 ticks above arrival -> STOP, not a chase")
p3=ex.plan(it, bid=100.30, ask=100.35, bid_lots=50, ask_lots=50,
           recent_lots=200, resting_age_ms=None, position=0)
ok(p3.act is Act.CROSS and p3.price <= 100.40,
   f"inside the band it crosses, capped at {p3.price:.2f} <= 100.40")

print("\n7. Participation cap limits the clip to a share of the tape")
ex2=Executor(tick=0.05, max_clip=50, pov=0.10, cross_at=0.0)
p4=ex2.plan(it, 100.00, 100.05, 50, 50, recent_lots=30,
            resting_age_ms=None, position=0)
ok(p4.lots <= 3, f"10% of 30 lots of tape -> clip {p4.lots} <= 3")

print("\n8. An expired call stops adding")
import time
ib6=IntentBook(); ib6.arm()
ib6.submit(Side.LONG,10,ttl_s=0.05,arrival_px=100.0,net_position=0)
time.sleep(0.12); ib6.tick()
ok(ib6.working() is None, "expired intent is no longer working")
ok(ib6.current.state is IState.EXPIRED, "and is marked EXPIRED, not silently dropped")

print("\n9. The flip drains the existing side first")
ex3=Executor(tick=0.05, cross_at=0.0)
ib7=IntentBook(flip_cooldown_s=0); ib7.arm()
ib7.submit(Side.LONG,5,net_position=0); ib7.submit(Side.SHORT,5,net_position=+5,
                                                   arrival_px=100.0)
p5=ex3.plan(ib7.working(), 100.0, 100.05, 50, 50, 200, None, position=+5)
ok(p5.side == -1 and "reducing" in p5.why, f"plan is {p5.why}, side {p5.side:+d}")
ok(p5.lots <= 5, "reduces no more than the position it holds")
