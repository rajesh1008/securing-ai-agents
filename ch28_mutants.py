#!/usr/bin/env python3
"""Chapter 28, lab 2: mutation testing of Bulwark's own controls by the unit layer.
Operators (AST, inside function bodies only):  CMP swap (== != < <= > >= in not in is is not), BOOL and<->or, NOT removed, GUARD (an `if` test replaced by False),
RETFLIP (return True <-> return False), CONST (small int constant +1 or -1, only ints 2..10**7).
Modules mutated: the decision code of the controls (not sandbox.py: its tests start real boxes and a mutant there can hang the host).
Each mutant: copy of the project to a scratch directory, one change, full unit suite with -x, 90 s limit.  Outcome killed / survived / timeout / error(import or collect).
Usage: ch28_mutants.py N SEED  -> sample N mutants with the seed, run on 6 workers, write results/ch28_mutants.json"""
import ast, copy, json, os, random, shutil, subprocess, sys, tempfile, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
HERE = Path(__file__).resolve().parent
TARGET = os.environ.get("MUT_TARGET", "tests").split()          # the floor(s) the mutants are run against
ONLY = os.environ.get("MUT_ONLY")                             # a results file: re-run only the mutants that survived there
OUT = os.environ.get("MUT_OUT", "ch28_mutants.json")
MODULES = ["policy", "policy_v02", "egress", "budget", "mcpguard", "supplychain", "tenancy", "authority", "moneypath", "refund", "approval", "memory",
           "anchor", "schema", "toolresults", "identity", "evidence", "registry", "notice", "steps", "stepclass", "reconcile", "promptrelease", "runtime_scope",
           "gateway", "alignment", "defences", "payloads", "architecture", "anatomy", "principles"]
SWAP = {ast.Eq: ast.NotEq, ast.NotEq: ast.Eq, ast.Lt: ast.LtE, ast.LtE: ast.Lt, ast.Gt: ast.GtE, ast.GtE: ast.Gt, ast.In: ast.NotIn, ast.NotIn: ast.In, ast.Is: ast.IsNot, ast.IsNot: ast.Is}
def sites(tree):
    out = []
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)): continue
        for n in ast.walk(fn):
            if isinstance(n, ast.Compare):
                for i, op in enumerate(n.ops):
                    if type(op) in SWAP: out.append(("CMP", n, i, fn.name))
            elif isinstance(n, ast.BoolOp): out.append(("BOOL", n, 0, fn.name))
            elif isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.Not): out.append(("NOT", n, 0, fn.name))
            elif isinstance(n, ast.If): out.append(("GUARD", n, 0, fn.name))
            elif isinstance(n, ast.Return) and isinstance(n.value, ast.Constant) and isinstance(n.value.value, bool): out.append(("RETFLIP", n, 0, fn.name))
            elif isinstance(n, ast.Constant) and type(n.value) is int and 2 <= n.value <= 10**7: out.append(("CONST", n, 0, fn.name))
    # drop sites that sit under a docstring or are in nested duplicates; keep order stable
    return out
def all_sites():
    res = []
    for m in MODULES:
        p = HERE / "bulwark" / f"{m}.py"
        if not p.exists(): continue
        tree = ast.parse(p.read_text())
        for k, (op, node, i, fn) in enumerate(sites(tree)):
            res.append(dict(module=m, op=op, idx=k, fn=fn, line=node.lineno))
    return res
def apply(m, idx):
    p = HERE / "bulwark" / f"{m}.py"; tree = ast.parse(p.read_text())
    op, node, i, fn = sites(tree)[idx]
    if op == "CMP": node.ops[i] = SWAP[type(node.ops[i])]()
    elif op == "BOOL": node.op = ast.Or() if isinstance(node.op, ast.And) else ast.And()
    elif op == "NOT": node.__dict__.update(ast.Name(id="__TRUE__", ctx=ast.Load()).__dict__) if False else None; node.op = ast.UAdd()
    elif op == "GUARD": node.test = ast.Constant(value=False)
    elif op == "RETFLIP": node.value = ast.Constant(value=not node.value.value)
    elif op == "CONST": node.value = node.value + 1
    ast.fix_missing_locations(tree); return ast.unparse(tree), op, fn, node.lineno
def run_one(job, base):
    m, idx = job["module"], job["idx"]; d = tempfile.mkdtemp(prefix="mut_", dir="/tmp")
    try:
        for part in ("bulwark", "tests", "scenarios"):
            shutil.copytree(HERE / part, Path(d) / part, ignore=shutil.ignore_patterns("__pycache__"))
        for f in HERE.glob("*.py"): shutil.copy(f, d)
        for part in ("fixtures", "results", "threatmodel", "attacks", "pyproject.toml"):
            if (HERE / part).exists(): os.symlink(HERE / part, Path(d) / part)
        src, op, fn, ln = apply(m, idx)
        (Path(d) / "bulwark" / f"{m}.py").write_text(src)
        t = time.time()
        try:
            r = subprocess.run([sys.executable, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", "--ignore=tests/test_sandbox.py", *TARGET], cwd=d, capture_output=True, text=True, timeout=90,
                               env={**{k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}, "PYTHONPATH": d, "PYTHONDONTWRITEBYTECODE": "1"})
            tail = (r.stdout + r.stderr)[-4000:]
            if r.returncode == 0: out = "survived"
            elif "error" in tail.lower().split("\n")[-2] and "failed" not in tail.lower().split("\n")[-2]: out = "error"
            else: out = "killed"
            failing = [l.split("::")[0].replace("FAILED ", "") for l in tail.split("\n") if l.startswith("FAILED ")][:1]
        except subprocess.TimeoutExpired: out, failing = "timeout", []
        return {**job, "op": op, "fn": fn, "line": ln, "outcome": out, "killer": failing[0] if failing else None, "secs": round(time.time() - t, 1)}
    finally: shutil.rmtree(d, ignore_errors=True)
def main():
    n = int(sys.argv[1]); seed = int(sys.argv[2]); S = all_sites(); rnd = random.Random(seed)
    if ONLY:
        prev = {(r["module"], r["idx"]) for r in json.load(open(HERE / "results" / ONLY))["results"] if r["outcome"] in ("survived", "error")}
        S = [s for s in S if (s["module"], s["idx"]) in prev]
    print("sites", len(S)); pick = rnd.sample(S, min(n, len(S)))
    base = subprocess.run([sys.executable, "-m", "pytest", "-q", "--ignore=tests/test_sandbox.py", *TARGET], cwd=HERE, capture_output=True, text=True).stdout.strip().split("\n")[-1]
    print("baseline:", base); res = []
    with ThreadPoolExecutor(6) as ex:
        for r in ex.map(lambda j: run_one(j, None), pick):
            res.append(r); print(len(res), r["module"], r["op"], r["fn"], r["outcome"], flush=True)
    from collections import Counter
    json.dump(dict(baseline=base, sites=len(S), seed=seed, n=len(pick), results=res, summary=Counter(r["outcome"] for r in res)), open(HERE / "results" / OUT, "w"), indent=1)
    print(Counter(r["outcome"] for r in res))
if __name__ == "__main__": main()
