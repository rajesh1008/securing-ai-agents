#!/usr/bin/env python3
"""Chapter 17, lab 3 (no model, no new runs): the control-layer coverage matrix. Reads results/ch15_ablation.json (16 attacks x 32 combinations) and results/ch17_control_layer.json (5 forced-compliance goals x 32 combinations) and asks, for each control of Part II,
which payloads' results depend on it: (a) removal view: the payload goes through when this control alone is removed; (b) in how many minimal sets of removed controls it appears; (c) unit view (forced goals only): with only this control on, the payload is stopped."""
import json
from pathlib import Path
here = Path(__file__).resolve().parent
A = json.load(open(here / "results/ch15_ablation.json"))["matrix"]; B = json.load(open(here / "results/ch17_control_layer.json"))
CTL = ["V", "G", "R", "D", "T"]; rows = []
alone = {c: [] for c in CTL}; inset = {c: [] for c in CTL}
for n, m in A.items():
    if 'residual' in n: continue     # A16 goes through with everything on: it is evidence about no control
    for c in CTL:
        if m["single"][c]: alone[c].append(n.split(" ")[0])
        if any(c in s for s in (m["minimal_sets"] or [])) : inset[c].append(n.split(" ")[0])
for g, m in B.items():
    for c in CTL:
        if any(c in s.split("+") for s in m["minimal_sets"]): inset[c].append("F:" + g)
unit = {c: [g for g, m in B.items() if m["alone_sufficient"][c]] for c in CTL}
L = ["control | removal view (payload goes through when only this control is removed) | appears in a smallest set | unit view (stops a forced goal with the other four off)"]
for c in CTL: L.append(f"{c} | {alone[c] or 'none'} | {len(inset[c])}: {inset[c]} | {unit[c] or 'none'}")
print("\n".join(L)); json.dump(dict(alone=alone, in_minimal_set=inset, unit=unit), open(here / "results/ch17_coverage.json", "w"), indent=1); open(here / "results/ch17_coverage.log", "w").write("\n".join(L) + "\n")
