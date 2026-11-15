#!/usr/bin/env python3
"""Chapter 19, lab 4b (live): the same evasion notes (rounds 1 and 2, no screen) against the HARDENED extractor (names the answer) and against the spotlight extractor.  15 docs x 2 samples per note per arm.  Writes results/ch19_evasion_hard.json and .log"""
import sys, json
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
import ch16_notes_live as N
import ch19_evasion_live as E
from bulwark.defences import datamark
ATT = N.ATT
def run(j):
    arm, k, (where, note), i, s = j
    t, d = N.doc_text(i, note, where)
    r = N.call(N.SYS_HARD, t) if arm == "HARD" else N.call(N.SYS_SPOT, datamark(t))
    jj = N.parse(r); return arm, k, (None if not jj else N.L.to_ex(jj).account == ATT)
if __name__ == "__main__":
    V = {**E.ROUND1, **E.ROUND2}
    jobs = [(a, k, v, i, s) for a in ("HARD", "SPOT") for k, v in V.items() for i in N.IDS for s in range(2)]
    with ThreadPoolExecutor(8) as ex: out = list(ex.map(run, jobs))
    T = defaultdict(lambda: [0, 0])
    for a, k, v in out: T[(a, k)][0] += (v is True); T[(a, k)][1] += 1
    L_ = [f"calls {len(out)}, unparsed {sum(1 for o in out if o[2] is None)}"]
    for k in V: L_.append(f"{k:20s} hardened took {T[('HARD', k)][0]:2d}/{T[('HARD', k)][1]}   spotlight took {T[('SPOT', k)][0]:2d}/{T[('SPOT', k)][1]}")
    print("\n".join(L_)); json.dump(dict(table={f"{a}|{k}": v for (a, k), v in T.items()}, log=L_), open(here / "results/ch19_evasion_hard.json", "w"), indent=1); open(here / "results/ch19_evasion_hard.log", "w").write("\n".join(L_) + "\n")
