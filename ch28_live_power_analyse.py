#!/usr/bin/env python3
"""Chapter 28, lab 4 analysis (no model).  From results/ch28_live_runs.json: the live floor as a statistical test.
For each regression (candidate prompt vs its production prompt) and each live-test size n (cases drawn at random from the 480-case library, one call each):
  k        smallest failure count that alarms with P(alarm | production rate) <= 0.05, binomial with the pooled production rate (bulwark.pyramid.plan_live_test arithmetic)
  predicted chance of an alarm under the regression, same arithmetic with the pooled candidate rate
  observed false-alarm rate: share of random n-subsets of each production run that reach k;  observed detection: the same on each candidate run  (20,000 subsets per run)
Also: n and k that plan_live_test asks for.  Writes results/ch28_live_power.json and ch28_live_power_analysis.log"""
import json, random
from pathlib import Path
from bulwark.pyramid import binom_sf, plan_live_test
here = Path(__file__).resolve().parent
D = json.load(open(here / "results/ch28_live_runs.json")); R = D["runs"]
PAIRS = [("B1", "HARD", "answer-naming sentence cut"), ("HARD_SHORT", "HARD", "shortened hardened prompt"), ("A2", "PLAIN", "'prefer the corrected value' edit")]
def runs_of(v): return [k for k in R if k.rsplit("-", 1)[0] == v]
def rate(v):
    ks = runs_of(v); n = sum(len(R[k]) for k in ks); x = sum(sum(f == 1 for f in R[k]) for k in ks); return x, n
rnd = random.Random(2811); out = {"rates": {}, "tests": []}; L = []
for v in ("HARD", "B1", "HARD_SHORT", "PLAIN", "A2"):
    x, n = rate(v); out["rates"][v] = dict(runs=[sum(f == 1 for f in R[k]) for k in runs_of(v)], reached=x, of=n, rate=x / n); L.append(f"{v:11s} runs {out['rates'][v]['runs']}  pooled {x}/{n} = {100 * x / n:.2f}%")
def sub_rate(flags, n, k, trials=20000):
    c = 0; idx = range(len(flags))
    for _ in range(trials):
        c += sum(1 for i in rnd.sample(idx, n) if flags[i] == 1) >= k
    return c / trials
for cand, prod, label in PAIRS:
    x0, n0 = rate(prod); x1, n1 = rate(cand); p0, p1 = x0 / n0, x1 / n1
    plan = plan_live_test(max(p0, 1e-9), p1) if p1 > p0 else None
    L.append(f"\n{label}: production {prod} {100 * p0:.2f}%  candidate {cand} {100 * p1:.2f}%   plan_live_test(0.05, 0.8) -> {plan}")
    L.append(f"{'n':>5s} {'k':>3s} {'pred.detect':>12s} {'obs.false':>10s} {'obs.detect':>11s}   per-run detect")
    for n in (10, 20, 40, 60, 120, 240, 480):
        k = next(k for k in range(0, n + 2) if binom_sf(n, k, p0) <= 0.05)
        pred = binom_sf(n, k, p1) if k <= n else 0.0
        fa = [sub_rate(R[r], n, k) for r in runs_of(prod)]; de = [sub_rate(R[r], n, k) for r in runs_of(cand)]
        fa_m, de_m = sum(fa) / len(fa), sum(de) / len(de)
        out["tests"].append(dict(cand=cand, prod=prod, n=n, k=k, predicted=pred, false_alarm=fa_m, detect=de_m, detect_runs=de, false_runs=fa))
        L.append(f"{n:5d} {k:3d} {100 * pred:11.1f}% {100 * fa_m:9.1f}% {100 * de_m:10.1f}%   {[round(100 * d, 1) for d in de]}")
# strongest payloads: how the cases are spread
for v in ("HARD", "B1", "HARD_SHORT", "A2", "PLAIN"):
    cases = D["cases"]; by = {}
    for k in runs_of(v):
        for (pid, doc), f in zip(cases, R[k]): by[(pid, doc)] = by.get((pid, doc), 0) + (f == 1)
    hit = {c for c, x in by.items() if x}; pids = {c[0] for c in hit}
    out.setdefault("spread", {})[v] = dict(cases_hit=len(hit), payloads_hit=len(pids)); L.append(f"{v:11s} distinct (payload, invoice) cases that ever succeeded: {len(hit)}; distinct payloads: {len(pids)}")
base = set(); 
for k in runs_of("HARD"):
    for c, f in zip(D["cases"], R[k]):
        if f == 1: base.add(tuple(c))
for v in ("B1", "HARD_SHORT"):
    new = set()
    for k in runs_of(v):
        for c, f in zip(D["cases"], R[k]):
            if f == 1 and tuple(c) not in base: new.add(tuple(c))
    L.append(f"{v}: cases that succeeded and never succeeded against HARD in 3 runs: {len(new)} ({len({c[0] for c in new})} payloads)")
    out["spread"][v]["new_cases_vs_hard"] = len(new)
json.dump(out, open(here / "results/ch28_live_power.json", "w"), indent=1); open(here / "results/ch28_live_power_analysis.log", "w").write("\n".join(L) + "\n"); print("\n".join(L))
