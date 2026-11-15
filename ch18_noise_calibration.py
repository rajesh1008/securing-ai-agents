#!/usr/bin/env python3
"""Chapter 18, lab 2 (live, same model): how often does the v1 gate block a change that is not a change?  Two more runs of the plain prompt (PLAIN-3, PLAIN-4), two more of HARD (HARD-3, HARD-4) and a second run of the reword candidate (A1-2).
Same 120 payloads x 4 hosts as ch17/ch18.  960 + 960 + 480 = 2,400 calls.  Then in ch18_gate_calibrate.py: gate each identical-configuration run against the others."""
import sys, json
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
import ch18_release_gate_live as G
if __name__ == "__main__":
    runs = [("PLAIN-3", G.A), ("PLAIN-4", G.A), ("HARD-3", G.HARD), ("HARD-4", G.HARD), ("A1-2", G.A1)]
    jobs = [(r, p, i, s) for r, s in runs for p in G.LIB for i in G.DOCS]
    with ThreadPoolExecutor(8) as ex: out = list(ex.map(G.job, jobs))
    R = defaultdict(lambda: defaultdict(int)); un = defaultdict(int)
    for run, pid, i, s in out: R[run][pid] += (s is True); un[run] += (s is None)
    R = {r: {pid: R[r].get(pid, 0) for pid in G.BYID} for r in R}
    tot = {r: sum(v.values()) for r, v in R.items()}; print("calls", len(out), "unparsed", dict(un), "totals", tot)
    json.dump(dict(runs=R, totals=tot, unparsed=dict(un)), open(here / "results/ch18_noise_runs.json", "w"), indent=1)
