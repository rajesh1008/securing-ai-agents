#!/usr/bin/env python3
"""Chapter 35, lab 3 report (no model): re-scores the stored drafts of ch35_attest.json (or the file named on the command line) with the current bundle.attest_check and prints the table of Chapter 35.6:
clean per arm, issue kinds, open items cited per draft, identifiers per sentence, umbrella sentences (8+ identifiers), and the plain-pattern word counts."""
import sys, json
from pathlib import Path
from collections import Counter
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
import ch35_attest as A
from bulwark.disclosure import Claim
f = Path(sys.argv[1]) if len(sys.argv) > 1 else here / "results/ch35_attest.json"
r = json.load(open(f))
if "16controls" in f.name: import ch35_collect as K, time; A.B = K.build(time.time(), drop=("E22",), skip=("C17",))   # the bundle that run used
print("file", f.name, "| bundle:", len(A.B.controls), "controls,", len(A.B.items), "items")
for a in ("A1", "A2", "A3", "A4"):
    sc = [A.attest_check([Claim(t, tuple(i)) for t, i in d], A.B) for d in r[a]["all_drafts"]]
    kinds = Counter(k for s in sc for k in {k for k, _ in s})
    ids = [len(i) for d in r[a]["all_drafts"] for t, i in d]; wide = sum(1 for d in r[a]["all_drafts"] if any(len(i) >= 8 for t, i in d))
    opn = [sum(1 for o in ("O1", "O2", "O3") if o in {x for t, i in d for x in i}) for d in r[a]["all_drafts"]]
    print(f"{a}: clean {sum(1 for s in sc if not s)}/10 | issue drafts {dict(kinds)} | mean ids/sentence {sum(ids)/len(ids):.1f} | drafts with a 8+ id sentence {wide} | open items cited per draft {opn}")
print("words (plain pattern):", r["words"], "| injected sentence in A3:", r["A3_injected_sentence"])
