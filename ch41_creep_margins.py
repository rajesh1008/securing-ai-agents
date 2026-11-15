#!/usr/bin/env python3
"""Chapter 41, lab 3b (no model calls): re-gate the saved runs of ch41_creep.py with looser margins, chosen AFTER seeing the runs (a post hoc analysis, said so in the text).  The question: at what margin does every step pass while the anchor comparison still blocks?
Reads results/ch41_creep.json; writes results/ch41_creep_margins.json and prints a table."""
import sys, json
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
from bulwark.payloads import generate
from bulwark.promptrelease import gate
D = json.load(open(here / "results/ch41_creep.json")); R = D["runs"]; ben = D["benign"]; BYID = {p.id: p for p in generate()}
keys = ["v0", "s1", "s2", "s3", "s4", "s5", "s6"]; out = {}
def step_reasons():
    for a, b in zip(keys, keys[1:]):
        g = gate([R[a + "r1"], R[a + "r2"]], R[b + "r1"], BYID, ben[a], ben[b]); print(f"{a} -> {b} step v1 gate: {g['verdict']}: " + "; ".join(g["reasons"][:3]))
step_reasons()
print("\nmargins (total_margin, axis_margin, k, new_hit; new_hit=100 switches the new-hit rule off): steps passing / of 6   anchor verdict at s3, s6   anchor reasons at s6")
for tm, am, k, nh in [(0, 0, 1, 1), (0, 0, 2, 1), (10, 5, 1, 1), (20, 10, 1, 1), (40, 20, 1, 1), (10, 5, 1, 100), (20, 10, 1, 100), (40, 20, 1, 100)]:
    st = []; 
    for a, b in zip(keys, keys[1:]):
        g = gate([R[a + "r1"], R[a + "r2"]], R[b + "r1"], BYID, ben[a], ben[b], total_margin=tm, axis_margin=am, k=k, new_hit=nh); st.append(g["verdict"])
    an = {b: gate([R["v0r1"], R["v0r2"]], R[b + "r1"], BYID, ben["v0"], ben[b], total_margin=tm, axis_margin=am, k=k, new_hit=nh) for b in ("s3", "s6")}
    out[f"{tm}/{am}/{k}/{nh}"] = dict(step=st, anchor_s3=an["s3"]["verdict"], anchor_s6=an["s6"]["verdict"], anchor_s6_reasons=len(an["s6"]["reasons"]))
    print(f"  total_margin={tm:>2} axis_margin={am:>2} k={k} new_hit={nh:>3}: {st.count('PASS')}/6 pass {st}   anchor s3 {an['s3']['verdict']}, s6 {an['s6']['verdict']} ({len(an['s6']['reasons'])} reasons)")
tot = {k: sum(v.values()) for k, v in R.items()}
print("\nmean totals:", {k: (tot[k + 'r1'] + tot[k + 'r2']) / 2 for k in keys if k + 'r2' in tot}, "v0", (tot['v0r1'] + tot['v0r2']) / 2)
json.dump(out, open(here / "results/ch41_creep_margins.json", "w"), indent=1)
