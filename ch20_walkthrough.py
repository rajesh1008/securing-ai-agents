#!/usr/bin/env python3
"""Chapter 20 walkthrough (live reader, deterministic rest): three documents through the clerk, the books and the plan.
  W1 a clean invoice;  W2 an invoice with a payload of the account goal that worked 4 of 4 on the plain extractor (the reader has no account field);  W3 an invoice with an amount-goal payload that worked 4 of 4 on the reader in both runs.
Each: the reader's record, verify (level 2) route and reasons, then the plan (read, then pay with invoice and amount from the verified record and the destination from the registry), executed under PlanLock.  Writes results/ch20_walkthrough.log"""
import sys, json
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
import ch16_notes_live as N, ch17_library_live as L17
import ch20_reader_live as R
from bulwark.payloads import generate
from bulwark.architecture import *
LIB = {p.id: p for p in generate()}
r1 = json.load(open(here / "results/ch20_reader_R-1.json"))["per_payload"]; r2 = json.load(open(here / "results/ch20_reader_R-2.json"))["per_payload"]
a = json.load(open(here / "results/ch18_release_gate_live.json")); b = json.load(open(here / "results/ch18_noise_runs.json")); rr = {**a["runs"], **b["runs"]}
acc = next(p for p in LIB if LIB[p].goal == "account" and all(rr[n][p] == 4 for n in ("A_1", "A_2", "PLAIN-3", "PLAIN-4")))
amt = next(p for p in LIB if LIB[p].goal == "amount" and r1[p] == 4 and r2[p] == 4)
L = []
def say(x): L.append(x); print(x)
i = N.IDS[0]; x = N.rec.invoices[i]; v = N.rec.vendors[x["payee_id"]]
say(f"books: invoice {i} number {x['number']} amount_cents {x['amount_cents']} vendor {v['name']} registry account {v['account']}")
for name, pid in (("W1 clean", None), ("W2 account payload " + (acc or ""), acc), ("W3 amount payload " + (amt or ""), amt)):
    if pid is None: t, d = N.doc_text(i, ""); goal = None
    else:
        p = LIB[pid]; tv = L17.target(p.goal, i); t, d = N.doc_text(i, p.text(L17.shown(p.goal, tv)).replace("{A}", ""), p.position); goal = (p.goal, tv)
    raw, jj = R.read(t); e = R.to_ex(jj); vd = R.verify_l2(d, e)
    say(f"\n{name}" + (f"  (note asks for {goal[0]} = {goal[1]})" if goal else ""))
    say(f"  reader record: {json.dumps(jj)}")
    say(f"  verify level 2: route {vd.route}, reasons {vd.reasons}")
    plan = [Step("read_invoice", {"id": ("const", i)}), Step("pay_invoice", {"invoice": ("field", "invoice_number"), "dest": ("registry", "vendor_account"), "amount": ("field", "amount")})]
    if vd.route != "AUTO": say("  plan: stops before pay_invoice; document goes to a person with the verify reasons"); continue
    eff = vd.effect; fields = {"invoice_number": x["number"], "amount": eff["amount_cents"]}
    des = PlanLock(plan, {"vendor_account": v["account"]}, fields)
    res = run(des, [Call("read_invoice", {"id": i}), Call("pay_invoice", {"invoice": x["number"], "dest": eff["destination"], "amount": eff["amount_cents"]})])
    say(f"  plan executed: {[(c.tool, ok) for c, ok, _ in res]}; effect {eff}; destination is the registry's: {eff['destination'] == v['account']}")
open(here / "results/ch20_walkthrough.log", "w").write("\n".join(L) + "\n")
