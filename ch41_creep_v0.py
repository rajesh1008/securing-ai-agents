#!/usr/bin/env python3
"""Chapter 41, lab 3c (live, claude-haiku-4-5-20251001): v0 (the unchanged Chapter 14 prompt) run twice again today, because the v0 baseline in lab 3 is Chapter 17's runs from 2026-11-11 and a changed model behind the same alias would
look like prompt creep.  Same library, same four hosts, same code as ch41_creep.py.  Writes results/ch41_creep_v0.json and prints the totals."""
import sys, json
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
import ch41_creep as C
if __name__ == "__main__":
    jobs = [(f"v0t{n}", p, i, C.V0) for n in (1, 2) for p in C.LIB for i in C.DOCS]
    with ThreadPoolExecutor(8) as ex: out = list(ex.map(C.job, jobs))
    R = defaultdict(lambda: defaultdict(int)); un = defaultdict(int)
    for run, pid, i, s in out: R[run][pid] += (s is True); un[run] += (s is None)
    tot = {k: sum(v.values()) for k, v in R.items()}
    print("calls", len(out), "unparsed", dict(un), "totals today:", tot, "(Chapter 17 runs of 2026-11-11: 308, 303)")
    json.dump(dict(runs={k: dict(v) for k, v in R.items()}, totals=tot, unparsed=dict(un)), open(here / "results/ch41_creep_v0.json", "w"), indent=1)
