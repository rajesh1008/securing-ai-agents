#!/usr/bin/env python3
"""Chapter 28, lab 1: what is on each floor before this chapter.  Counts only: test functions per file (pytest collection, parametrised cases counted), lab scripts by whether they call a model,
results files, and which controls (modules of bulwark/) have a test file that imports them.  Excludes this chapter's additions (test_pyramid, test_gaps_ch28, scenarios/, ch28_*).  Writes results/ch28_census.json and .log"""
import json, re, subprocess, sys, glob, os
from pathlib import Path
here = Path(__file__).resolve().parent
out = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q", "tests", "--ignore=tests/test_pyramid.py", "--ignore=tests/test_gaps_ch28.py"], cwd=here, capture_output=True, text=True).stdout
per = {}
for l in out.splitlines():
    if "::" in l: f = l.split("::")[0]; per[f] = per.get(f, 0) + 1
mods = sorted(p.stem for p in (here / "bulwark").glob("*.py") if p.stem not in ("__init__", "pyramid"))
tested = {m: [f for f in per if re.search(rf"bulwark\.{m}\b", open(here / f).read())] for m in mods}
scripts = sorted(p.name for p in here.glob("*.py") if re.match(r"(ch\d\d_|scripts_)", p.name) and not p.name.startswith("ch28_"))
live = [s for s in scripts if re.search(r"anthropic|N\.call|import ch1[0-9]_.*live|ch16_notes_live|ch17_library_live", open(here / s).read())]
res = len([p for p in (here / "results").glob("*.json") if not p.name.startswith("ch28_")])
L = [f"unit tests (pytest, excluding Chapter 28 additions): {sum(per.values())} in {len(per)} files", f"lab scripts: {len(scripts)}; of these call a model directly or through a live lab: {len(live)}; results files (json): {res}",
     f"bulwark modules: {len(mods)}; with at least one test file naming them: {sum(1 for m in mods if tested[m])}; with none: {sorted(m for m in mods if not tested[m])}",
     "tests per file: " + ", ".join(f"{os.path.basename(f)[5:-3]} {n}" for f, n in sorted(per.items(), key=lambda x: -x[1]))]
print("\n".join(L)); json.dump(dict(tests=per, total=sum(per.values()), modules=mods, untested=[m for m in mods if not tested[m]], scripts=len(scripts), live_scripts=len(live), results_json=res), open(here / "results/ch28_census.json", "w"), indent=1)
open(here / "results/ch28_census.log", "w").write("\n".join(L) + "\n")
