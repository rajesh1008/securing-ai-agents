#!/usr/bin/env python3
"""Chapter 36, lab 1 (no model): where does this project's own code turn a failure into a verdict?  AST scan of every broad exception handler (bare, Exception, BaseException) in bulwark/*.py (the library) and ch*.py (lab scripts).
Counts handlers by what the body does.  Then lists every library handler with its enclosing function and the line, for a by-hand review (written in the chapter).  Writes results/ch36_scan.json and results/ch36_scan.log."""
import sys, json, ast
from pathlib import Path
from collections import Counter
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
from bulwark.degrade import scan_handlers
def enclosing(src):
    tree = ast.parse(src); m = {}
    for f in ast.walk(tree):
        if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for n in ast.walk(f):
                if isinstance(n, ast.ExceptHandler): m[n.lineno] = f.name
    return m
out = {}; log = []
for label, files in (("library", sorted((here / "bulwark").glob("*.py"))), ("labs", sorted(here.glob("ch*.py")))):
    rows = []; total_lines = 0
    for p in files:
        s = p.read_text(); total_lines += s.count("\n"); enc = enclosing(s)
        for h in scan_handlers(s, p.name): h["func"] = enc.get(h["line"], "?"); rows.append(h)
    c = Counter(); 
    for h in rows: c["|".join(h["kinds"])] += 1
    out[label] = dict(files=len(files), lines=total_lines, handlers=len(rows), swallow=sum(h["swallows"] for h in rows), kinds=dict(c.most_common()), rows=rows)
    log.append(f"{label}: {len(files)} files, {total_lines} lines, {len(rows)} broad handlers, {sum(h['swallows'] for h in rows)} do not re-raise")
    for k, v in c.most_common(): log.append(f"   {v:3d}  {k}")
log.append("\nLIBRARY HANDLERS")
for h in out["library"]["rows"]: log.append(f"  {h['path']}:{h['line']} in {h['func']}(): {','.join(h['kinds'])}")
(here / "results/ch36_scan.json").write_text(json.dumps(out, indent=1)); (here / "results/ch36_scan.log").write_text("\n".join(log) + "\n"); print("\n".join(log))
