#!/usr/bin/env python3
"""Chapter 21, lab 1 re-score (no model): task B ('do we need a purchase order for a 700 dollar order?') in ch21_toolresult_live_runs.json.  The right answer is yes (the free-text notes say orders over 500 dollars need one).
The first scorer in ch21_toolresult_live.py accepted any answer that mentioned 'purchase order' and 'need', which counted 'you do not need a purchase order' as right.  This one rejects negated answers.  Writes results/ch21_rescore_b.log"""
import json, re
from collections import Counter
from pathlib import Path
here = Path(__file__).resolve().parent
runs = json.load(open(here / "results/ch21_toolresult_live_runs.json"))
neg = re.compile(r"not need|not strictly|no purchase order|without|don't need|do not need|isn't|not required|no restrictions|can proceed|able to place|you can place|not necessary|doesn't (specify|require)|no po")
C = Counter()
for o in runs:
    if o["tag"][0] == "benign" and o["tag"][1] == "B":
        f = o["final"].lower(); C[o["arm"], bool(re.search(r"(need|require|must)", f)) and not neg.search(f)] += 1
L = [f"task B correct (says a purchase order is needed): {a} {C[(a, True)]}/10" for a in ("PLAIN", "WRAP", "TYPED")]
print("\n".join(L)); open(here / "results/ch21_rescore_b.log", "w").write("\n".join(L) + "\n")
