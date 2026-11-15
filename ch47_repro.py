#!/usr/bin/env python3
"""Chapter 47, lab 4 (no model): does a lab reproduce?  Each no-model lab is run under two different string-hash seeds; every results file it writes is compared by content
(time-like keys removed, ms timings rounded away).  A lab whose evidence depends on the hash seed cannot be re-run by a reviewer to the same answer.
Writes results/ch47_repro.json.  Usage: ch47_repro.py   (leaves the results files as the second run wrote them)"""
import subprocess, sys, json, hashlib, os, time, shutil
from pathlib import Path
here = Path(__file__).resolve().parent; R = here / "results"
LABS = ["ch07_designs", "ch10_effect_binding", "ch12_egress_ladder", "ch13_tamper", "ch36_faults", "ch36_outage", "ch38_topology", "ch44_register", "ch45_programmes",
        "ch46_exercise", "ch46_hiring_sim", "ch47_malformed", "ch47_regress"]
VOLATILE = {"time", "ts", "made", "when", "stamp", "elapsed", "seconds", "ms", "ms_raw", "ms_hard", "money_ms_raw", "money_ms_hard", "egress_ms_raw", "egress_ms_hard", "slowest", "generated", "at"}
def clean(o):
    if isinstance(o, dict): return {k: clean(v) for k, v in o.items() if k not in VOLATILE}
    if isinstance(o, list): return [clean(x) for x in o]
    return o
def snap():
    out = {}
    for p in sorted(R.glob("*.json")):
        try: out[p.name] = (p.stat().st_mtime_ns, hashlib.sha256(json.dumps(clean(json.load(open(p))), sort_keys=True).encode()).hexdigest())
        except Exception: pass
    return out
def run(lab, seed, args=()):
    b = snap(); env = dict(os.environ, PYTHONHASHSEED=str(seed))
    r = subprocess.run([sys.executable, str(here / f"{lab}.py"), *args], env=env, capture_output=True, text=True, cwd=here, timeout=900)
    a = snap(); return r.returncode, {k: v[1] for k, v in a.items() if k not in b or b[k][0] != v[0]}
res = {}
for lab in LABS:
    args = ("hardened",) if lab == "ch47_malformed" else ()
    c1, f1 = run(lab, 1, args); c2, f2 = run(lab, 2, args)
    differ = sorted(k for k in f1 if f1.get(k) != f2.get(k))
    res[lab] = dict(exit=(c1, c2), files=sorted(f1), differ=differ); print(f"{lab:22} exit {c1},{c2}  files {len(f1)}  differ: {differ or 'none'}")
json.dump(res, open(R / "ch47_repro.json", "w"), indent=1)
