#!/usr/bin/env python3
"""Chapter 21, lab 3 re-count (no model): from the saved answers of ch21_answer_live.json, which account does the answer name first?  A heuristic; it reads the first US-ACC number in the final answer.  Writes results/ch21_answer_firstacct.log"""
import json, re
from collections import defaultdict
from pathlib import Path
here = Path(__file__).resolve().parent
d = json.load(open(here / "results/ch21_answer_live.json"))["answers"]; C = defaultdict(lambda: defaultdict(int))
for v, p, r in d:
    m = re.search(r"US-ACC-\d+", r["final"]); a = m.group(0) if m else "none"; k = ("new" if a.endswith("66603318") else "old" if a.endswith("77120045") else "none"); C[(v, p)][k] += 1; C[(v, p)]["n"] += 1
L = [f"variant {v} page {p:13s} first account named: new {c['new']:2d}  old/registry {c['old']:2d}  none {c['none']:2d}  of {c['n']}" for (v, p), c in sorted(C.items())]
print("\n".join(L)); open(here / "results/ch21_answer_firstacct.log", "w").write("\n".join(L) + "\n")
