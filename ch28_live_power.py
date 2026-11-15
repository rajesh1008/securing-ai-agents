#!/usr/bin/env python3
"""Chapter 28, lab 4: what the live floor can see.  Real calls (claude-haiku-4-5-20251001), Chapter 17's payload library (120 payloads x 4 invoices = 480 cases per run).
Two production prompts and their regressions:  HARD (production) vs HARD_SHORT (the shortening Chapter 19 blocked) and B1 (the answer-naming sentence cut, Chapter 18);
PLAIN (production) vs A2 ('prefer the corrected value').  Fresh runs, so the rates are today's:  HARD x3, B1 x2, HARD_SHORT x2, PLAIN x1, A2 x1  (9 runs, 4,320 calls).
Writes results/ch28_live_runs.json (per-case outcomes, 1 = the payload's goal was reached).  Analysis is in ch28_live_power_analyse.py (no model)."""
import sys, json, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
import ch18_release_gate_live as G
import ch19_defences_live as D
from bulwark.payloads import generate
LIB = G.LIB; DOCS = G.DOCS
VERS = {"HARD": G.HARD, "B1": G.B1, "HARD_SHORT": D.HARD_SHORT, "PLAIN": G.A, "A2": G.A2}
PLAN = [("HARD", 1), ("HARD", 2), ("HARD", 3), ("B1", 1), ("B1", 2), ("HARD_SHORT", 1), ("HARD_SHORT", 2), ("PLAIN", 1), ("A2", 1)]
def main():
    out = {"model": "claude-haiku-4-5-20251001", "date": time.strftime("%Y-%m-%d %H:%M %Z"), "cases": [[p.id, i] for p in LIB for i in DOCS], "runs": {}}
    for ver, k in PLAN:
        t = time.time(); jobs = [(f"{ver}-{k}", p, i, VERS[ver]) for p in LIB for i in DOCS]
        with ThreadPoolExecutor(8) as ex: res = list(ex.map(G.job, jobs))
        flags = [None if s is None else int(bool(s)) for _, _, _, s in res]
        out["runs"][f"{ver}-{k}"] = flags
        print(f"{ver}-{k}: reached {sum(f == 1 for f in flags)} of {len(flags)}; unparsed {sum(f is None for f in flags)}; {time.time() - t:.0f} s", flush=True)
        json.dump(out, open(here / "results/ch28_live_runs.json", "w"))
if __name__ == "__main__": main()
