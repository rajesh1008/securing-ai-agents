#!/usr/bin/env python3
"""Chapter 26, cost: microseconds per operation of the supply-chain controls (mean of repetitions, no model).  Writes results/ch26_cost.json and .log"""
import json, sys, time, tempfile
from datetime import date
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
from bulwark.supplychain import *
from ch26_corpus import write_all
C = write_all(tempfile.mkdtemp(prefix="ch26k_")); (p, d, g) = C[("benign", "invoice-reminder")]
lock = Lock([LockEntry("skill", "invoice-reminder", "1.0.0", "git:x", artefact_digest(p), d, "Ian", "2027-03-01")]); dg = artefact_digest(p)
def t(f, n):
    t0 = time.perf_counter()
    for _ in range(n): f()
    return (time.perf_counter() - t0) / n * 1e6
R = dict(artefact_digest=t(lambda: artefact_digest(p), 500), lint_skill=t(lambda: lint_skill(p, set()), 500), observed_permissions=t(lambda: observed_permissions(p), 500), lock_verify=t(lambda: lock.verify("skill", "invoice-reminder", "1.0.0", dg, d, date(2026, 11, 11), source="git:x"), 5000))
import os; R["skill_bytes"] = sum(os.path.getsize(os.path.join(a, f)) for a, _, fs in os.walk(p) for f in fs)
L = [f"{k}: {v:.1f}" + (" us" if k != "skill_bytes" else " bytes") for k, v in R.items()]
print("\n".join(L)); json.dump(R, open(here / "results/ch26_cost.json", "w"), indent=1); open(here / "results/ch26_cost.log", "w").write("\n".join(L) + "\n")
