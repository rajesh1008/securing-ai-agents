#!/usr/bin/env python3
"""Chapter 7 lab 3: scope excess. For the 2,000 benign tasks of ch07_designs.py (same seed and generator), how much of the granted scope does the task use?
Excess = granted kinds that no benign action of the task used; granted payees and mail domains likewise. No model calls."""
import json, random, collections
from pathlib import Path
import importlib.util, sys, io, contextlib
from bulwark.runtime_scope import *
here = Path(__file__).resolve().parent
# reuse generators without re-running the lab output
src = (here / "ch07_designs.py").read_text().split("N = 2000")[0]
ns = {"__file__": str(here / "ch07_designs.py")}; exec(compile(src, "ch07_designs_head", "exec"), ns)
B, R, CEIL, AMBIENT, ROLE = ns["B"], ns["R"], ns["CEIL"], ns["AMBIENT"], ns["ROLE"]
make_task, benign_actions = ns["make_task"], ns["benign_actions"]
rows = collections.defaultdict(lambda: collections.defaultdict(list)); n = 0
for _ in range(2000):
    req = make_task()
    try: c = compute_scope(req, B, CEIL)
    except ScopeRefused: continue
    ben = benign_actions(req); used_k = {a["kind"] for a in ben}; used_p = {a["payee"] for a in ben if a.get("payee")}; used_d = {a["recipient"].rsplit("@", 1)[-1] for a in ben if a.get("recipient")}
    for name, s in (("A_ambient", AMBIENT), ("B_role_ceiling", ROLE), ("C_task_scope", c)):
        kinds = set(s.kinds); pays = set(s.payees) if (s.payees is not None) else set(B.payees)
        doms = set(s.mail_domains) if s.mail_domains is not None else {x["domain"] for x in B.customers.values()} | {x["domain"] for x in B.payees.values()} | {"any-other"}
        pay_on = "initiate_payment" in kinds; mail_on = any(k in kinds for k in ("send_email", "send_invoice"))
        rows[name]["kinds_used_frac"].append(len(kinds & used_k) / len(kinds))
        rows[name]["payee_used_frac"].append((len(pays & used_p) / len(pays)) if pay_on and pays else None)
        rows[name]["domain_used_frac"].append((len(doms & used_d) / len(doms)) if mail_on and doms else None)
    rows["_by_type"][req.task_type].append(len(set(c.kinds)))
out = {}
print(f"{'design':18}{'kinds used / granted':>24}{'payees used / reachable':>26}{'domains used / reachable':>27}")
for name in ("A_ambient", "B_role_ceiling", "C_task_scope"):
    f = lambda k: [x for x in rows[name][k] if x is not None]
    m = lambda k: (sum(f(k)) / len(f(k))) if f(k) else float("nan")
    out[name] = dict(kinds=round(m("kinds_used_frac"), 3), payees=round(m("payee_used_frac"), 3), domains=round(m("domain_used_frac"), 3))
    print(f"{name:18}{m('kinds_used_frac'):>24.1%}{m('payee_used_frac'):>26.1%}{m('domain_used_frac'):>27.1%}")
(here / "results/ch07_excess.json").write_text(json.dumps(out, indent=1))
