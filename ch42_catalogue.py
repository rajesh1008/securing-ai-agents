#!/usr/bin/env python3
"""Chapter 42, lab 1 (no model): run the catalogue of bulwark/patterns.py over four design sheets (ch42_designs.py), and scan this project's own code for A06.
Writes results/ch42_catalogue.json and .log."""
import sys, json
from pathlib import Path
from collections import Counter
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
from bulwark import patterns as P
import ch42_designs as D
L = []; R = {}
lib = P.scan_code(sorted((here / "bulwark").glob("*.py"))); labs = P.scan_code(sorted(here.glob("ch*.py")))
L.append(f"code scan A06: library {lib['fail_open_handlers']} fail-open handlers; lab scripts {labs['fail_open_handlers']}")
for r in lib["rows"] + labs["rows"]: L.append(f"   {Path(r['path']).name}:{r['line']} {r['func']}() {r['why']}")
R["scan"] = dict(library=lib, labs=labs)
grid = {}
for k, f in D.DESIGNS.items():
    d = f()
    if k == "Q41":
        d["code_scan"] = dict(fail_open_handlers=lib["fail_open_handlers"], rows=lib["rows"])
        res0 = P.check(d); L.append(""); L.append(f"== Q41 with the code scan and no waiver: A06 {res0['A06'][0]}: {res0['A06'][1]}; findings {P.findings(res0)}")
        d["code_scan"]["waived"] = {"principles.py:execute": "W-A06-1"}
        d["waivers"].append(dict(id="W-A06-1 Mediator fail_mode parameter (lab use only; test asserts the default is closed)", owner="Kevin", review_day=361))
    res = P.check(d); grid[k] = res
    c = Counter(v for v, _ in res.values())
    pats = [e.id for e in P.CATALOGUE if e.kind == "pattern"]; antis = [e.id for e in P.CATALOGUE if e.kind == "anti"]
    pf = sum(res[i][0] == "FAIL" for i in pats); pp = sum(res[i][0] == "PASS" for i in pats); pn = sum(res[i][0] == "NA" for i in pats)
    ap = sum(res[i][0] == "PRESENT" for i in antis); aa = sum(res[i][0] == "ABSENT" for i in antis); an = sum(res[i][0] == "NA" for i in antis)
    L.append(""); L.append(f"== {d['name']}: patterns PASS {pp} FAIL {pf} NA {pn}; anti-patterns PRESENT {ap} ABSENT {aa} NA {an}; errors {c.get('ERROR', 0)}; claim level {P.claim_level(d)}")
    L += ["   " + x for x in P.table(res)]
    R[k] = dict(name=d["name"], pass_=pp, fail=pf, na_p=pn, present=ap, absent=aa, na_a=an, errors=c.get("ERROR", 0), result=res, level=P.claim_level(d))
# which controls each entry realises, and how often each control appears
cc = Counter(c for e in P.CATALOGUE for c in e.controls)
L.append(""); L.append("controls named by the catalogue: " + ", ".join(f"{k} {v}" for k, v in sorted(cc.items())))
missing = sorted({f"C{i:02d}" for i in range(1, 21)} - set(cc)); L.append("controls named by no entry: " + (", ".join(missing) or "none"))
up = [e.id for e in P.CATALOGUE if e.kind == "pattern" and not e.upkeep]; L.append("patterns with no Chapter 41 upkeep job: " + ", ".join(up))
R["controls"] = dict(cc); R["controls_missing"] = missing; R["no_upkeep"] = up
(here / "results/ch42_catalogue.json").write_text(json.dumps(R, indent=1, default=str)); (here / "results/ch42_catalogue.log").write_text("\n".join(L) + "\n"); print("\n".join(L))
