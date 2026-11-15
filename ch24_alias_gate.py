#!/usr/bin/env python3
"""Chapter 24, lab 5 (no model): the gateway's alias-move decision, run on the Chapter 23 results.  For each ordered pair of the three models, risk cells = the 32 goal x framing cells of Lab 1 (PLAIN) plus the 12 goal x variant cells of Lab 2 (H1-H3, plus H4 for the split);
legitimate cells = the eight tasks of Lab 3 (PLAIN).  alias_move() gives PASS / REVIEW / BLOCK and the cells that moved.  Second part: silent failover exposure, the number of risk cells that rise if a request meant for model A is served by model B.
Writes results/ch24_alias_gate.json and .log"""
import json, sys
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
from bulwark.gateway import alias_move
R = lambda f: json.load(open(here / "results" / f)); M = ["haiku45", "sonnet46", "haiku55"]
def risk(m):
    d = {}
    for o in R(f"ch23_refusal_{m}.json"):
        if o["arm"] == "PLAIN": c = d.setdefault(("L1", o["goal"], o["framing"]), [0, 0]); c[1] += 1; c[0] += o["outcome"] == "IMPROPER"
    for o in R(f"ch23_intent_{m}.json"):
        c = d.setdefault(("L2", o["goal"], o["variant"]), [0, 0]); c[1] += 1; c[0] += o["outcome"] == "IMPROPER"
    return {k: tuple(v) for k, v in d.items()}
def ok(m):
    d = {}
    for o in R(f"ch23_overrefusal_{m}.json"):
        if o["arm"] == "PLAIN": c = d.setdefault(o["task"], [0, 0]); c[1] += 1; c[0] += o["outcome"] == "DONE"
    return {k: tuple(v) for k, v in d.items()}
RK = {m: risk(m) for m in M}; OK = {m: ok(m) for m in M}; L = [f"risk cells {len(RK['haiku45'])}, legitimate cells {len(OK['haiku45'])}"]; out = {}
for a in M:
    for b in M:
        if a == b: continue
        v, mv = alias_move(RK[a], RK[b], OK[a], OK[b]); up = [x for x in mv if x[1] == "UP"]; dn = [x for x in mv if x[1] == "DOWN"]; bd = [x for x in mv if x[1] == "BENIGN_DOWN"]
        L.append(f"{a} -> {b}: {v}; risk cells up {len(up)}, down {len(dn)}; legitimate cells down {len(bd)}")
        for x in up: L.append(f"    UP {x[0][1]}/{x[0][2]} ({x[0][0]}) {x[2]} -> {x[3]}")
        out[f"{a}->{b}"] = dict(verdict=v, moved=[list(map(str, x)) for x in mv])
json.dump(out, open(here / "results/ch24_alias_gate.json", "w"), indent=1); open(here / "results/ch24_alias_gate.log", "w").write("\n".join(L) + "\n"); print("\n".join(L))
