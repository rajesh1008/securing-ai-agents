#!/usr/bin/env python3
"""Chapter 29, lab 5 (no model, no network): F3 retested, and whether Chapter 32's monitor would have seen the flood.
Part A: the review-queue flood of Section 29.8 against three policies that cannot see which items are hostile (arrival order, a per-sender-key cap, a registered-sender lane), with an attacker who uses 1, 5, 20 or 100 sender keys.
Part B: the Chapter 32 one-sided CUSUM (bulwark.detect.Cusum) on the stream 'this item went to review'; days from the start of the flood to the alarm, against the day the first legitimate item waited a day.
Assumptions are mine and are printed: 40 legitimate review items a day, 93 other legitimate items a day that never reach a person, capacity 60 a day, 30 days, seeds 1-40 for part B.
Writes results/ch29_detection_check.log and .json"""
import sys, json, random, math
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
from bulwark.redteam import queue_wait_keyed, queue_wait
from bulwark.detect import Cusum, arl0
L = []; P = L.append; out = {}
P("Part A. F3 retest. 40 legitimate items a day from 150 registered sender keys (2% from a first contact), reviewer clears 60 a day, 30 days, seed 29. per-key cap 3 a day; registered lane 12 a day.")
P(f"{'flood/day':>9s} {'policy':>10s} {'keys':>5s} {'median':>7s} {'p90':>4s} {'legit unserved':>15s} {'first-contact median':>21s} {'first-contact unserved':>23s} {'backlog':>8s}")
rowsA = []
for f in (80, 200):
    for pol, K in (("fifo", 1), ("per_key", 1), ("per_key", 5), ("per_key", 20), ("per_key", 100), ("registered", 1), ("registered", 100)):
        r = queue_wait_keyed(40, f, 60, policy=pol, attacker_keys=K); rowsA.append(dict(flood=f, policy=pol, keys=K, **r))
        P(f"{f:>9d} {pol:>10s} {K:>5d} {r['median_wait_days']!s:>7s} {r['p90_wait_days']!s:>4s} {r['legit_unserved']:>15d} {r['new_sender_median']!s:>21s} {r['new_sender_unserved']:>23d} {r['backlog']:>8d}")
out["A"] = rowsA
r0 = queue_wait_keyed(40, 0, 60, policy="registered"); P(f"no flood, registered lane: median {r0['median_wait_days']}, first-contact median {r0['new_sender_median']}, unserved {r0['legit_unserved']}")
P("\nPart B. Would the Chapter 32 monitor have seen it? Stream: 1 when an item goes to review. Baseline share p0 = 40/133 = 0.30; CUSUM for p1 = 0.40; h = 5 and h = 8.")
p0, p1 = 40 / 133, 0.40
for hh in (5.0, 8.0):
    a0 = arl0(p0, p1, hh); P(f"h = {hh:g}: ARL0 (simulated, rate really p0, 2000 runs, cap 5000 items): {a0:.0f} items, about {a0/133:.1f} days of 133 items")
def poisson(r, lam):
    L_, k, q = math.exp(-lam), 0, 1.0
    while True:
        q *= r.random()
        if q <= L_: return k
        k += 1
def one_run(f, seed, hh, days=30, cap=60):
    """Arrival-order queue and the CUSUM on the same stream.  Returns (alarm day, first day a legitimate item is served after waiting at least a day)."""
    r = random.Random(seed); c = Cusum(p0, p1, hh); alarm = None; harm = None; q = []
    for d in range(days):
        nl, nh, no = poisson(r, 40), poisson(r, f), poisson(r, 93)
        xs = [1] * (nl + nh) + [0] * no; r.shuffle(xs)
        for x in xs:
            if c.see(x, d) and alarm is None: alarm = d
        new = ["L"] * nl + ["H"] * nh; r.shuffle(new); q += [(t, d) for t in new]
        served, q = q[:cap], q[cap:]
        if harm is None and any(t == "L" and d - a >= 1 for t, a in served): harm = d
    return alarm, harm
P(f"{'flood/day':>9s} {'alarmed':>8s} {'median alarm day':>17s} {'latest':>7s} {'harm seen':>10s} {'median harm day':>16s} {'alarm before harm':>18s}")
rowsB = []
med = lambda xs: sorted(xs)[len(xs) // 2] if xs else None
for hh in (5.0, 8.0):
  P(f"h = {hh:g}")
  for f in (0, 10, 20, 40, 80, 200):
      runs = [one_run(f, s, hh) for s in range(1, 41)]
      al = [a for a, _ in runs if a is not None]; hm = [b for _, b in runs if b is not None]
      before = sum(1 for a, b in runs if b is not None and a is not None and a < b)
      rowsB.append(dict(h=hh, flood=f, alarmed=len(al), median_alarm=med(al), latest_alarm=max(al) if al else None, harm=len(hm), median_harm=med(hm), alarm_before_harm=before))
      P(f"{f:>9d} {len(al):>5d}/40 {med(al)!s:>17s} {(max(al) if al else None)!s:>7s} {len(hm):>7d}/40 {med(hm)!s:>16s} {before:>15d}/40")
out["B"] = rowsB
P("\nPart C. The Monitor as shipped in Chapter 32 (amount, account, reverse shadow, run) on 30 days of flood at 80 a day, every hostile item routed REVIEW with a varied vendor name and amount, next to 40 legitimate review items a day.")
from bulwark.detect import Monitor, Obs
r = random.Random(7); m = Monitor(); n = 0; alerts = 0
for d in range(30):
    for i in range(poisson(r, 80) + poisson(r, 40)):
        n += 1; o = Obs(id=f"c{n}", day=d, vendor=f"vendor{r.randrange(400)}", amount=r.randrange(5000, 400000), dest=f"acct{r.randrange(400)}", route="REVIEW")
        alerts += m.see(o) is not None
P(f"items seen {n}, alerts {alerts}")
out["C"] = dict(items=n, alerts=alerts)
json.dump(out, open(here / "results/ch29_detection_check.json", "w"), indent=1)
open(here / "results/ch29_detection_check.log", "w").write("\n".join(L) + "\n"); print("\n".join(L))
