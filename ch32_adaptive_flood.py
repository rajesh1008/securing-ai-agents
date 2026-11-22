#!/usr/bin/env python3
"""Chapter 32, lab 7 (no model, no network): an attacker who has read the monitor, and a detector that watches the age of the review queue.
Setting is the Chapter 29 queue: 40 legitimate review items a day, 93 other legitimate items a day that never reach a person, reviewer capacity 60 a day, arrival-order queue, 30 days, seeds 1-40.
Attackers: 'plain' floods f items a day; 'padded' also sends 2.325 clean-routing items per hostile item so that the share of items going to review stays at the baseline 40/133 (it costs the attacker mail, not review time); 'ramp' adds one more hostile item a day each day up to f.
Detectors: the Chapter 32 CUSUM on 'this item went to review' (p0 = 40/133, p1 = 0.40, h = 8), and an age detector: alarm on the first day the oldest unserved item at the end of the day has been waiting at least T days (an item still unserved at the end of its arrival day has age 1) (T = 1, 2, 3).
Harm = first day a legitimate item is served after waiting at least a day (what a person sees).  Assumptions are mine and are printed.  Writes results/ch32_adaptive_flood.log and .json"""
import sys, json, random, math
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
from bulwark.detect import Cusum, ReviewAge
P0, P1, H, CAP, DAYS = 40 / 133, 0.40, 8.0, 60, 30
def poisson(r, lam):
    L_, k, q = math.exp(-lam), 0, 1.0
    while True:
        q *= r.random()
        if q <= L_: return k
        k += 1
def one_run(mode, f, seed, ts=(1, 2, 3)):
    r = random.Random(seed); c = Cusum(P0, P1, H); alarm_c = None; ages = {t: ReviewAge(t) for t in ts}; age_alarm = {t: None for t in ts}; harm = None; q = []; waits = []; maxq = 0
    for d in range(DAYS):
        fl = f if mode != "ramp" else min(f, d + 1)
        if mode == "none": fl = 0
        nl, nh, no = poisson(r, 40), poisson(r, fl), poisson(r, 93)
        pad = poisson(r, fl * (133 / 40 - 1)) if mode == "padded" else 0
        xs = [1] * (nl + nh) + [0] * (no + pad); r.shuffle(xs)
        for x in xs:
            if c.see(x, d) and alarm_c is None: alarm_c = d
        new = ["L"] * nl + ["H"] * nh; r.shuffle(new); q += [(t, d) for t in new]
        served, q = q[:CAP], q[CAP:]
        for t, a in served:
            if t == "L": waits.append(d - a)
        if harm is None and any(t == "L" and d - a >= 1 for t, a in served): harm = d
        maxq = max(maxq, len(q))
        for t in ts:
            if ages[t].end_of_day(d, [a for _, a in q]): age_alarm[t] = d
    return dict(cusum=alarm_c, age=age_alarm, harm=harm, backlog=len(q), waits=waits)
med = lambda xs: sorted(xs)[len(xs) // 2] if xs else None
L = []; P = L.append; rows = []
P("Setting: 40 legitimate review items/day, 93 other items/day, capacity 60/day, 30 days, 40 seeded months per row. CUSUM p0 = 0.30, p1 = 0.40, h = 8. Age detector alarms when the oldest unserved item has age >= T at the end of a day, where age 1 means carried over from its arrival day.")
P(f"{'attacker':>8s} {'f':>4s} | {'detector':>10s} {'alarmed':>8s} {'median day':>11s} | {'harm months':>11s} {'median harm day':>16s} {'alarm before harm':>18s} {'backlog day 30 (median)':>24s}")
for mode, fs in (("none", (0,)), ("plain", (10, 20, 30, 80)), ("padded", (10, 20, 30, 80)), ("ramp", (20, 30))):
    for f in fs:
        runs = [one_run(mode, f, s) for s in range(1, 41)]
        hm = [x["harm"] for x in runs if x["harm"] is not None]
        for det in ("cusum", "age>=1", "age>=2", "age>=3"):
            al = [x["cusum"] if det == "cusum" else x["age"][int(det[-1])] for x in runs]
            got = [a for a in al if a is not None]
            before = sum(1 for a, x in zip(al, runs) if a is not None and x["harm"] is not None and a < x["harm"])
            rows.append(dict(attacker=mode, flood=f, detector=det, alarmed=len(got), median_alarm=med(got), harm=len(hm), median_harm=med(hm), alarm_before_harm=before, median_backlog=med([x["backlog"] for x in runs])))
            P(f"{mode:>8s} {f:>4d} | {det:>10s} {len(got):>5d}/40 {med(got)!s:>11s} | {len(hm):>8d}/40 {med(hm)!s:>16s} {before:>15d}/40 {med([x['backlog'] for x in runs])!s:>24s}")
json.dump(rows, open(here / "results/ch32_adaptive_flood.json", "w"), indent=1)
open(here / "results/ch32_adaptive_flood.log", "w").write("\n".join(L) + "\n"); print("\n".join(L))
