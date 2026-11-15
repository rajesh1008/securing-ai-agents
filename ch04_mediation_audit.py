#!/usr/bin/env python3
"""Chapter 4 lab 2 (complete mediation): a static audit that finds code which can reach a tool, or the outside world, without passing the Mediator.
Run on the clean tree, then on a copy with a seeded 'debug_send' bypass of the kind Chapter 2 warned about."""
import ast, json, shutil, sys, tempfile
from pathlib import Path
here = Path(__file__).resolve().parent
EGRESS_MODULES = {"smtplib", "requests", "httpx", "urllib", "urllib3", "http", "socket", "subprocess", "aiohttp"}
def audit(root: Path):
    findings = []
    for f in sorted(root.rglob("*.py")):
        rel = f.relative_to(root).as_posix()
        if rel.startswith(("tests/", "__pycache__")) or "/tests/" in rel: continue
        tree = ast.parse(f.read_text())
        for n in ast.walk(tree):
            mods = []
            if isinstance(n, ast.Import): mods = [a.name.split(".")[0] for a in n.names]
            if isinstance(n, ast.ImportFrom) and n.module: mods = [n.module.split(".")[0]]
            for m in mods:
                if m in EGRESS_MODULES: findings.append((rel, n.lineno, f"imports egress-capable module {m}"))
            if isinstance(n, ast.Attribute) and n.attr == "_fn" and rel != "bulwark/principles.py":
                findings.append((rel, n.lineno, "reaches into Tool._fn (bypasses token)"))
            if isinstance(n, ast.Name) and n.id == "_TOKEN" and rel != "bulwark/principles.py":
                findings.append((rel, n.lineno, "uses mediator token outside principles.py"))
    return findings
def show(label, fs):
    print(f"{label}: {len(fs)} finding(s)")
    for f in fs: print("  ", *f)
clean = audit(here)
show("clean tree", clean)
tmp = Path(tempfile.mkdtemp()); shutil.copytree(here / "bulwark", tmp / "bulwark")
(tmp / "bulwark/debug_send.py").write_text('import smtplib\nfrom .principles import Tool\ndef debug_send(tool, proposal):\n    return tool._fn(proposal)  # "just for testing"\n')
seeded = audit(tmp); show("seeded bypass", seeded)
(here / "results/ch04_mediation_audit.json").write_text(json.dumps(dict(clean=clean, seeded=seeded), indent=1))
