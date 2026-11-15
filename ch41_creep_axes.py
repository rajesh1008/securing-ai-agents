#!/usr/bin/env python3
"""Chapter 41, lab 3d (no model calls): where the six edits of ch41_creep.py moved the library: mean successes per axis value (two runs each) at v0 and at s6, and payloads that never worked on v0.  Reads results/ch41_creep.json."""
import json, sys
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
from bulwark.payloads import generate
from bulwark.promptrelease import axis_totals
D = json.load(open(here / "results/ch41_creep.json")); R = D["runs"]; B = {p.id: p for p in generate()}
def avg(a, b): return {k: (a.get(k, 0) + b.get(k, 0)) / 2 for k in set(a) | set(b)}
for axis in ("goal", "voice", "frame", "position"):
    a = avg(axis_totals(R["v0r1"], B, axis, 0), axis_totals(R["v0r2"], B, axis, 0)); b = avg(axis_totals(R["s6r1"], B, axis, 0), axis_totals(R["s6r2"], B, axis, 0))
    print(axis, {k: (round(a[k]), round(b[k])) for k in sorted(a)}, "(v0, s6)")
dead0 = [p for p in B if R["v0r1"][p] == 0 and R["v0r2"][p] == 0]; now = [p for p in dead0 if R["s6r1"][p] + R["s6r2"][p] > 0]
print("never worked on v0 (0 of 4 in both runs):", len(dead0), "; worked on s6 at least once in two runs:", len(now))
print("4 of 4 in both runs: v0", sum(R["v0r1"][p] == 4 and R["v0r2"][p] == 4 for p in B), "s6", sum(R["s6r1"][p] == 4 and R["s6r2"][p] == 4 for p in B))
