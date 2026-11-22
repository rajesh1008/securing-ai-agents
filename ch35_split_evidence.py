#!/usr/bin/env python3
"""Chapter 35, lab 6 (no model, no network): split the pytest evidence of control C06 by test file, and count what a change to one module reopens.
In the lab bundle C06 rests on one log of the whole suite (item E01), which cites 16 modules, so almost any change reopens it.  Here the evidence is cut to the test files that exercise C06's claim, and a test file is taken to depend on every bulwark module it imports, directly or through other bulwark modules (static import analysis with ast; nothing is run).
Three readings of 'C06 is reopened by a change to module M':  A) the whole-suite log (M among the 16 subjects of E01, as in ch35_collect.py);  B) the C06 test files, direct imports only;  C) the C06 test files, imports followed transitively.
C06's claim: 'A tool outside the loadout or the registry fails the build.'  Its test files are the ones whose imports, followed transitively, reach bulwark.registry or bulwark.runtime_scope.
Writes results/ch35_split_evidence.log and .json"""
import sys, ast, json
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
import ch35_collect as K
MODS = sorted(K.MODS); E01 = next(i for i in K.ITEMS if i[0] == "E01")[3]
def imports(p: Path) -> set:
    out = set(); lab = set()
    for n in ast.walk(ast.parse(p.read_text())):
        if isinstance(n, ast.ImportFrom) and n.level == 1:   # relative import inside the package
            if n.module: out.add(n.module.split(".")[0])
            else: out |= {a.name for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module:
            if n.module.startswith("bulwark."): out.add(n.module.split(".")[1])
            elif n.module == "bulwark": out |= {a.name for a in n.names}
        elif isinstance(n, ast.Import):
            out |= {a.name.split(".")[1] for a in n.names if a.name.startswith("bulwark.")}
            lab |= {a.name for a in n.names if (here / f"{a.name}.py").exists()}
        if isinstance(n, ast.ImportFrom) and n.level == 0 and n.module and (here / f"{n.module}.py").exists(): lab.add(n.module)
    return {m for m in out if (here / "bulwark" / f"{m}.py").exists()} | {"lab:" + m for m in lab}
graph = {p.stem: imports(p) for p in (here / "bulwark").glob("*.py") if p.stem != "__init__"}
for p in here.glob("*.py"): graph["lab:" + p.stem] = imports(p)   # lab scripts at the repository root, which tests sometimes import
def key(m): return m
def closure(ms):
    seen, stack = set(), list(ms)
    while stack:
        m = stack.pop()
        if m in seen: continue
        seen.add(m); stack += graph.get(m, ())  # lab:NAME nodes are root scripts
    return seen
tests = {p.name: imports(p) for p in sorted((here / "tests").glob("test_*.py"))}
c06 = [t for t, im in tests.items() if closure(im) & {"registry", "runtime_scope"}]
c06_direct = [t for t, im in tests.items() if im & {"registry", "runtime_scope"}]
direct = set().union(*(tests[t] for t in c06)); trans = closure(direct)
L = []; P = L.append
NB = sum(1 for m in graph if not m.startswith('lab:'))
P(f"bulwark modules: {NB}; test files: {len(tests)}; modules in the lab bundle: {len(MODS)}")
P(f"test files that import registry or runtime_scope directly ({len(c06_direct)}): {', '.join(c06_direct)}")
P(f"C06 test files, reaching them transitively ({len(c06)}): {', '.join(c06)}")
P(f"A) whole-suite log: modules that reopen C06 = {len([m for m in MODS if m in E01])} of {len(MODS)}")
B = [m for m in MODS if m in direct]; C = [m for m in MODS if m in trans]
P(f"B) C06 test files, direct imports: {len(B)} of {len(MODS)}: {', '.join(B)}")
P(f"C) C06 test files, transitive imports: {len(C)} of {len(MODS)}: {', '.join(C)}")
P(f"modules in the lab bundle whose change no longer reopens C06 under C: {', '.join(m for m in MODS if m in E01 and m not in trans)}")
P(f"modules that reopen C06 under C but are not cited in E01: {', '.join(m for m in MODS if m not in E01 and m in trans) or 'none'}")
P(f"all bulwark modules (not only the bundle's) that a C06 test file reaches: {len([m for m in trans if not m.startswith('lab:')])} of {NB}")
for t in c06: P(f"   {t}: reaches {len([m for m in MODS if m in closure(tests[t])])} of the bundle's modules ({', '.join(m for m in MODS if m in closure(tests[t]))})")
import subprocess
code = "import sys, pytest; pytest.main(['-q', '-p', 'no:cacheprovider', 'tests']); print('LOADED ' + ','.join(sorted(m[8:] for m in sys.modules if m.startswith('bulwark.'))))"
o = subprocess.run([sys.executable, "-c", code], cwd=here, capture_output=True, text=True).stdout
loaded = set(next(l for l in o.splitlines() if l.startswith("LOADED ")).split(" ", 1)[1].split(","))
never = [m for m in MODS if m in E01 and m not in loaded]
P(f"D) the whole suite run in one process: {len(loaded)} bulwark modules loaded; cited in E01 but never loaded by any test: {', '.join(never) or 'none'}")
rows = dict(never_loaded=never, c06_tests=c06, whole_suite=[m for m in MODS if m in E01], direct=B, transitive=C, reached=sorted(m for m in trans if not m.startswith('lab:')), n_modules=NB, n_tests=len(tests))
json.dump(rows, open(here / "results/ch35_split_evidence.json", "w"), indent=1)
open(here / "results/ch35_split_evidence.log", "w").write("\n".join(L) + "\n"); print("\n".join(L))
