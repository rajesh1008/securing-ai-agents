#!/usr/bin/env python3
"""Chapter 28, lab 4 (no model): are the cases a regression breaks the same from run to run?  For each version, the number of (payload, invoice) cases that succeeded in every run, and in any run.
Reads results/ch28_live_runs.json.  Writes results/ch28_live_overlap.log"""
import json
from pathlib import Path
here = Path(__file__).resolve().parent; D = json.load(open(here / "results/ch28_live_runs.json")); R = D["runs"]; L = []
for v in ("HARD", "B1", "HARD_SHORT", "PLAIN", "A2"):
    ks = [k for k in R if k.rsplit("-", 1)[0] == v]; sets = [{i for i, f in enumerate(R[k]) if f == 1} for k in ks]
    L.append(f"{v:11s} runs {len(ks)}: per run {[len(s) for s in sets]}; succeeded in every run {len(set.intersection(*sets))}; in any run {len(set.union(*sets))}")
print("\n".join(L)); open(here / "results/ch28_live_overlap.log", "w").write("\n".join(L) + "\n")
