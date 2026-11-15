#!/usr/bin/env python3
"""Chapter 26, lab 1 (no model): reviewing 48 skills.  24 benign and 24 hostile (12 obvious, 12 paraphrased or hidden) written by the author (ch26_corpus.py).  Three reviewers: LINT (lint_skill: patterns over every file, allowed host ledgerly.example), PERMS (observed_permissions of the Python files against the declared manifest; undeclared capabilities flag), LINT+PERMS.  Reports recall on hostile by group, false positives on benign, which hostile skills each missed, and which benign ones were flagged and why.  Writes results/ch26_scan.json and .log"""
import json, sys, tempfile, time
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
from bulwark.supplychain import *
from ch26_corpus import write_all, OK_HOST
root = tempfile.mkdtemp(prefix="ch26_"); C = write_all(root); R = {}
t0 = time.perf_counter()
for (kind, n), (p, decl, grp) in C.items():
    li = lint_skill(p, {OK_HOST}); ob = observed_permissions(p); ud = undeclared(decl, ob)
    R[f"{kind}/{n}"] = dict(kind=kind, group=grp, lint=[h[0] for h in li], undeclared=ud, observed=ob)
el = time.perf_counter() - t0
def flag(r, mode): return bool(r["lint"]) if mode == "LINT" else bool(r["undeclared"]) if mode == "PERMS" else bool(r["lint"] or r["undeclared"])
L = [f"48 skills scanned in {el*1000:.0f} ms ({el/48*1000:.1f} ms each)"]
for mode in ("LINT", "PERMS", "LINT+PERMS"):
    hA = sum(flag(r, mode) for r in R.values() if r["group"] == "A"); hB = sum(flag(r, mode) for r in R.values() if r["group"] == "B"); fp = sum(flag(r, mode) for r in R.values() if r["kind"] == "benign")
    L.append(f"{mode:10s} hostile A {hA}/12, hostile B {hB}/12, benign flagged {fp}/24")
for mode in ("LINT", "PERMS", "LINT+PERMS"):
    L.append(f"{mode} missed: " + ", ".join(k.split('/')[1] for k, r in R.items() if r["kind"] == "hostile" and not flag(r, mode)))
L.append("benign flagged by LINT: " + "; ".join(f"{k.split('/')[1]} {sorted(set(r['lint']))}" for k, r in R.items() if r["kind"] == "benign" and r["lint"]))
L.append("benign flagged by PERMS: " + "; ".join(f"{k.split('/')[1]} {r['undeclared']}" for k, r in R.items() if r["kind"] == "benign" and r["undeclared"]))
print("\n".join(L)); json.dump(R, open(here / "results/ch26_scan.json", "w"), indent=1); open(here / "results/ch26_scan.log", "w").write("\n".join(L) + "\n")
