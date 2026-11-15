#!/usr/bin/env python3
"""Chapter 3: Quill's surface map, checked against the files that are supposed to implement each control."""
import json, collections
from pathlib import Path
here = Path(__file__).resolve().parent
S = json.load(open(here / "threatmodel/surfaces.json"))
rows = []
for s in S:
    kinds = [c["kind"] for c in s["controls"]]
    missing = [c["file"] for c in s["controls"] if not (here / c["file"]).exists()]
    best = "deterministic" if "deterministic" in kinds else ("advisory" if "advisory" in kinds else ("prompt" if "prompt" in kinds else ("weak" if "weak" in kinds else "none")))
    rows.append(dict(n=s["n"], surface=s["surface"], best=best, controls=len(kinds), missing_files=missing))
print(f"{'#':>2} {'surface':17} {'strongest control':14} controls")
for r in rows: print(f"{r['n']:>2} {r['surface']:17} {r['best']:14} {r['controls']}  {'MISSING ' + str(r['missing_files']) if r['missing_files'] else ''}")
c = collections.Counter(r["best"] for r in rows); print(dict(c))
(here / "results/ch03_surfaces.json").write_text(json.dumps(rows, indent=1))
