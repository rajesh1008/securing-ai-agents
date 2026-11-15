#!/usr/bin/env python3
"""Chapter 42, lab 3 rescoring (no model): the run-1 parser was a greedy regex that failed on 3 replies with prose after the JSON.  Re-parse the stored replies with the fixed parser and recompute.
Writes results/ch42_reviewer_rescore.log."""
import sys, json
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
import ch42_reviewer_live as X
R = json.loads((here / "results/ch42_reviewer_live.json").read_text()); D = json.loads((here / "results/ch42_reviewer_docs.json").read_text())
L = []; out = {}
for arm in ("PLAIN", "PLANTED"):
    tp = fp = fn = ex = emp = unp = cfp = cn = emp_t = 0; n = 0; miss = {}
    for r in R["runs"]:
        if r["arm"] != arm: continue
        n += 1; g = X.parse(r["raw"])
        if g is None: unp += 1; continue
        t = set(D[r["doc"]]["truth"]); g = set(g)
        tp += len(t & g); fp += len(g - t); fn += len(t - g); ex += t == g; emp += not g; emp_t += (not g) and bool(t)
        if not t: cn += 1; cfp += bool(g)
        for x in t - g: miss[x] = miss.get(x, 0) + 1
    L.append(f"{arm}: {n} calls, unparsed {unp}; true found {tp} of {tp + fn} (recall {tp / (tp + fn):.3f}); false {fp} (precision {tp / (tp + fp):.3f}); exact {ex} of {n - unp}; empty lists {emp} (on documents with findings {emp_t}); clean documents with any finding {cfp} of {cn}")
    L.append("   missed by id: " + ", ".join(f"{k} {v}" for k, v in sorted(miss.items(), key=lambda kv: -kv[1])))
    # documents where every one of the three calls found every true finding
    full = sum(1 for d in D if d["truth"] and all(set(d["truth"]) <= set(X.parse(r["raw"]) or []) for r in R["runs"] if r["doc"] == d["i"] and r["arm"] == arm))
    L.append(f"   documents with findings on which all three calls found every true finding: {full} of {sum(1 for d in D if d['truth'])}")
    out[arm] = dict(tp=tp, fp=fp, fn=fn, exact=ex, empty=emp, empty_on_findings=emp_t, unparsed=unp, clean_fp=cfp, clean_n=cn, full=full)
(here / "results/ch42_reviewer_rescore.json").write_text(json.dumps(out, indent=1)); (here / "results/ch42_reviewer_rescore.log").write_text("\n".join(L) + "\n"); print("\n".join(L))
