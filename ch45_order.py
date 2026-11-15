#!/usr/bin/env python3
"""Chapter 45, lab 1b (no model): does the order of the work matter?  For Quill's day-0 stage and Harbour and Vale's as-deployed stage, each fix is a step with an effort in engineer-days (the author's estimates).
Steps that put a deterministic gate on a trusted record change the checker's path count; steps on the model's side (a stricter prompt, a detector, a second reviewing model) do not, by the checker's definition, and are included because teams do them first.
Three orders are compared: MODEL-FIRST (model-side steps, then gates in the order a team usually thinks of them), BY-TOOL (gates tool by tool starting with payments), GREEDY (at each point the gate with most paths removed per engineer-day, given what is already done).
The score is exposure: unbounded paths summed over engineer-days elapsed until all are bounded.  Writes results/ch45_order.json and .log."""
import sys, json, copy, itertools
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
from bulwark.casestudy import *
import ch45_programmes as P
R = P.R
def gate(tool, *g):
    def f(p):
        for t in p.tools:
            if t.id == tool: t.gates = [x for x in t.gates if x.kind == "human"] + list(g)
    return f
def memgate(p): p.memory_write_gated = True
def noop(p): pass
QUILL = [("tighter system prompt", 2, noop), ("injection screen on inputs", 4, noop), ("second model reviews emails", 3, noop),
         ("payee registry and invoice binding on pay_invoice", 15, gate("pay_invoice", R("payee registry"), R("invoice binding"))), ("registry-bound refund destination", 6, gate("issue_refund", R("original payment destination"))),
         ("contact book and allow-list on send_email", 5, gate("send_email", R("contact book and allow-list"))), ("egress allow-list on http_fetch", 4, gate("http_fetch", R("egress allow-list"))), ("memory write gate", 8, memgate)]
DHV = [("tighter system prompt", 2, noop), ("anomaly screen on outbound letters", 4, noop), ("recipients must be parties on the claim", 5, gate("send_correspondence", R("parties named on the claim record"))),
       ("proxy allow-list on fetch_url", 4, gate("fetch_url", R("proxy allow-list"))), ("memory write gate", 8, memgate)]
def curve(base, steps, order):
    p = copy.deepcopy(base); days = 0; area = 0; pts = [(0, len(findings(p)))]
    for i in order:
        n, d, f = steps[i]; area += len(findings(p)) * d; days += d; f(p); pts.append((days, len(findings(p)), n))
    return area, days, pts
def greedy(base, steps):
    p = copy.deepcopy(base); left = list(range(len(steps))); order = []
    while left:
        def score(i):
            q = copy.deepcopy(p); steps[i][2](q); return (len(findings(p)) - len(findings(q))) / steps[i][1]
        best = max(left, key=lambda i: (score(i), -steps[i][1])); order.append(best); left.remove(best); steps[best][2](p)
    return order
def main():
    L = []; out = {}
    for name, base, steps, byt in (("Quill", P.A_day0(), QUILL, [3, 4, 5, 6, 7, 0, 1, 2]), ("Harbour and Vale", P.D_deployed(), DHV, [2, 3, 4, 0, 1])):
        orders = {"MODEL-FIRST": list(range(len(steps))), "BY-TOOL": byt, "GREEDY": greedy(base, steps)}
        L.append(f"{name}: starting unbounded paths {len(findings(base))}; total effort {sum(s[1] for s in steps)} engineer-days")
        for k, o in orders.items():
            area, days, pts = curve(base, steps, o); out[f"{name}|{k}"] = dict(area=area, order=[steps[i][0] for i in o], pts=pts)
            L.append(f"  {k:12} exposure {area:5d} path-days; paths after each step: " + " ".join(str(p[1]) for p in pts) + "; first day with fewer than half the paths: " + str(next((p[0] for p in pts if p[1] <= pts[0][1] / 2), None)))
            L.append("     order: " + " > ".join(steps[i][0] for i in o))
    (here / "results/ch45_order.json").write_text(json.dumps(out, indent=1)); (here / "results/ch45_order.log").write_text("\n".join(L) + "\n"); print("\n".join(L))
if __name__ == "__main__": main()
