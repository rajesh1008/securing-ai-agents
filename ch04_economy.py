#!/usr/bin/env python3
"""Chapter 4 lab 3 (economy of mechanism): how much code decides? Counts lines and branch points in the enforcement files."""
import ast, json
from pathlib import Path
here = Path(__file__).resolve().parent
files = ["bulwark/policy.py", "bulwark/policy_v02.py", "bulwark/principles.py", "bulwark/registry.py", "bulwark/budget.py", "bulwark/authority.py", "bulwark/anchor.py", "bulwark/refund.py", "bulwark/notice.py", "bulwark/quill_lab.py"]
rows = []
for f in files:
    src = (here / f).read_text(); tree = ast.parse(src)
    loc = sum(1 for l in src.splitlines() if l.strip() and not l.strip().startswith("#"))
    br = sum(isinstance(n, (ast.If, ast.For, ast.While, ast.Try, ast.BoolOp, ast.IfExp)) for n in ast.walk(tree))
    rows.append(dict(file=f, loc=loc, branches=br))
    print(f"{f:26} loc={loc:4} branches={br:3}")
gate = [r for r in rows if r["file"] in ("bulwark/policy.py", "bulwark/policy_v02.py")]
print("gate (v0.1 base + v0.2) loc:", sum(r["loc"] for r in gate), "branches:", sum(r["branches"] for r in gate))
(here / "results/ch04_economy.json").write_text(json.dumps(rows, indent=1))
