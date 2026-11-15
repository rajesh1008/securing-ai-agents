#!/usr/bin/env python3
"""Chapter 36, lab 5 (no model): a dependency that flaps, and how many times the mode flips.
An 8-hour working day, one request a minute (480 requests).  The dependency alternates between up and down periods drawn from an exponential distribution (mean up 3 min, mean down 2 min; seed fixed; 200 seeds).
Policy A (no hysteresis): the mode is DEGRADED when the last call failed, NORMAL otherwise.
Policy B (Breaker k=3 failures in 10 min, cooldown 5 min, 3 consecutive probe successes to close): requests are not sent while OPEN; HALF sends probes.
Per policy: mode flips, requests served NORMAL, requests handled DEGRADED, calls made to the dependency, requests whose call failed while the mode was NORMAL (they are handled by the table, but each is a user-visible failure), minutes in DEGRADED.
Then the drill grid: dependencies x fault kinds, and which cells the Chapter 36 labs exercised.  Writes results/ch36_flap.json and .log."""
import sys, json, random, statistics as st
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
from bulwark.degrade import *
def timeline(seed, n=480):
    r = random.Random(seed); up = []; state = True
    while len(up) < n:
        k = max(1, round(r.expovariate(1 / (3.0 if state else 2.0)))); up += [state] * k; state = not state
    return up[:n]
def run_a(up):
    mode = "NORMAL"; flips = served = degraded = calls = fail_normal = deg_min = 0
    for ok in up:
        calls += 1
        if mode == "NORMAL":
            if ok: served += 1
            else: fail_normal += 1; degraded += 1; mode = "DEGRADED"; flips += 1; deg_min += 1; continue
        else:
            degraded += 1; deg_min += 1
            if ok: mode = "NORMAL"; flips += 1
    return flips, served, degraded, calls, fail_normal, deg_min
def run_b(up):
    b = Breaker(k=3, window=10, cooldown=5, need=3); flips = served = degraded = calls = fail_normal = deg_min = 0; prev = "NORMAL"
    for t, ok in enumerate(up):
        if b.allow(t):
            calls += 1; was = b.state; b.record(ok, t)
            if was == "CLOSED":
                if ok: served += 1
                else: fail_normal += 1; degraded += 1
            else: degraded += 1
        else: degraded += 1
        mode = "NORMAL" if b.state == "CLOSED" else "DEGRADED"; deg_min += mode == "DEGRADED"
        if mode != prev: flips += 1; prev = mode
    return flips, served, degraded, calls, fail_normal, deg_min
names = ("flips", "served_normal", "degraded", "calls", "failed_in_normal", "minutes_degraded")
A = [run_a(timeline(s)) for s in range(200)]; B = [run_b(timeline(s)) for s in range(200)]
L = ["200 seeds x 480 requests; mean up 3 min, mean down 2 min (dependency up %.0f%% of minutes)" % (100 * st.mean(sum(timeline(s)) / 480 for s in range(200)))]
L.append(f"{'policy':26s} " + " ".join(f"{n:>17s}" for n in names))
for lab, R in (("A last-call, no hysteresis", A), ("B breaker k3 cool5 need3", B)): L.append(f"{lab:26s} " + " ".join(f"{st.mean(r[i] for r in R):>17.1f}" for i in range(6)))
L.append("   median flips A %d, B %d; max flips A %d, B %d" % (st.median(r[0] for r in A), st.median(r[0] for r in B), max(r[0] for r in A), max(r[0] for r in B)))
DEPS = {"extractor": Dependency("extractor", Role.PROVIDE, "eng-lead"), "gateway": Dependency("gateway", Role.PROVIDE, "sam"), "verifier": Dependency("verifier", Role.PREVENT, "ian"), "sender_route": Dependency("sender_route", Role.PREVENT, "ian"),
        "money_gate": Dependency("money_gate", Role.PREVENT, "ian"), "egress": Dependency("egress", Role.PREVENT, "ian"), "monitor": Dependency("monitor", Role.DETECT, "mei", 40, 1440), "approvals": Dependency("approvals", Role.APPROVE, "ian"), "chain": Dependency("chain", Role.RECORD, "mei")}
drilled = {(d, f) for d in ("extractor", "verifier", "sender_route") for f in FAULTS}
und = untested(DEPS, drilled)
L.append(f"\nDrill grid: {len(DEPS)} dependencies x {len(FAULTS)} fault kinds = {len(cells(DEPS))} cells; exercised by ch36_faults.py: {len(drilled)}; untested {len(und)}")
for d in DEPS:
    miss = [f for f in FAULTS if (d, f) in und]
    if miss: L.append(f"   {d:13s} ({DEPS[d].role.value}): untested {', '.join(miss)}")
(here / "results/ch36_flap.json").write_text(json.dumps(dict(A=A, B=B, untested=und), indent=0)); (here / "results/ch36_flap.log").write_text("\n".join(L) + "\n"); print("\n".join(L))
