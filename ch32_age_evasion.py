#!/usr/bin/env python3
"""Chapter 32, lab 8 (no model, no network): an attacker who has read the age detector and sizes bursts to stay under it.
Same setting as lab 7: 40 legitimate review items a day (Poisson), 93 other items a day, reviewer capacity 60 a day, arrival-order queue, 30 days, seeds 1-40.
Attacker 'burst B every P days': on days 0, P, 2P, ... sends B hostile items at once (Poisson mean B), and nothing otherwise. Average load B/P a day.
Detectors: ReviewAge with T = 1, 2, 3 (age 1 = still unserved at the end of its arrival day) and the lab-7 CUSUM (p0 = 40/133, p1 = 0.40, h = 8).
Harm = a legitimate item served after waiting at least a day; also the longest legitimate wait in days, and the share of legitimate items that waited.
Assumptions are mine and printed. Writes results/ch32_age_evasion.log and .json"""
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
def one_run(B, P, seed):
    r = random.Random(seed); c = Cusum(P0, P1, H); alarm_c = None; ts = (1, 2, 3)
    ages = {t: ReviewAge(t) for t in ts}; age_alarm = {t: None for t in ts}; harm = None; q = []; waits = []; nleg = 0
    for d in range(DAYS):
        fl = B if (B and d % P == 0) else 0
        nl, nh, no = poisson(r, 40), poisson(r, fl), poisson(r, 93); nleg += nl
        xs = [1] * (nl + nh) + [0] * no; r.shuffle(xs)
        for x in xs:
            if c.see(x, d) and alarm_c is None: alarm_c = d
        new = ["L"] * nl + ["H"] * nh; r.shuffle(new); q += [(t, d) for t, d in [(t, d) for t in new]]
        served, q = q[:CAP], q[CAP:]
        for t, a in served:
            if t == "L": waits.append(d - a)
        if harm is None and any(t == "L" and d - a >= 1 for t, a in served): harm = d
        for t in ts:
            if ages[t].end_of_day(d, [a for _, a in q]): age_alarm[t] = d
    return dict(cusum=alarm_c, age=age_alarm, harm=harm, waits=waits, nleg=nleg)
L = []; Pr = L.append; out = []
Pr("Setting: 40 legitimate review items/day, 93 other items/day, capacity 60/day, 30 days, 40 seeded months per row. Burst = B hostile items every P days (day 0, P, 2P, ...).")
Pr(f"{'B':>4s} {'P':>3s} {'load/day':>9s} | {'harm months':>11s} {'legit waited %':>14s} {'max wait (d)':>12s} | {'CUSUM':>6s} {'age>=1':>7s} {'age>=2':>7s} {'age>=3':>7s}   (alarmed months of 40)")
for B, P in ((0, 1), (20, 5), (30, 5), (40, 5), (60, 5), (60, 10), (80, 10), (100, 10)):
    runs = [one_run(B, P, s) for s in range(1, 41)]
    hm = sum(1 for x in runs if x["harm"] is not None)
    tot = sum(x["nleg"] for x in runs); w = [v for x in runs for v in x["waits"]]
    waited = 100 * sum(1 for v in w if v >= 1) / tot
    mw = max(w) if w else 0
    al = lambda k: sum(1 for x in runs if (x["cusum"] if k == 0 else x["age"][k]) is not None)
    Pr(f"{B:4d} {P:3d} {B/P:9.1f} | {hm:11d} {waited:14.2f} {mw:12d} | {al(0):6d} {al(1):7d} {al(2):7d} {al(3):7d}")
    out.append(dict(B=B, P=P, harm_months=hm, legit_waited_pct=round(waited, 2), max_wait=mw, cusum=al(0), age1=al(1), age2=al(2), age3=al(3)))
(here / "results").mkdir(exist_ok=True)
(here / "results/ch32_age_evasion.log").write_text("\n".join(L) + "\n"); (here / "results/ch32_age_evasion.json").write_text(json.dumps(out, indent=1))
print("\n".join(L))
