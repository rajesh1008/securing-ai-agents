#!/usr/bin/env python3
"""Chapter 5 lab 4: classify the Quill invoice-to-payment flow, lint it, and compare with the 'ask the model' plan."""
import json
from pathlib import Path
from bulwark.stepclass import Step, Cls, lint
here = Path(__file__).resolve().parent
C = Cls
# name, class, untrusted_input, decides_authority, reversible, checked_downstream, owner note
CLASSIFIED = [
 Step("fetch attachment",                 C.C0, True,  False, True,  True,  "size and type limits in code"),
 Step("identify document type",           C.C2, True,  False, True,  True,  "enum: invoice|statement|other; other goes to a human"),
 Step("extract fields",                   C.C2, True,  False, True,  True,  "typed schema; totals check follows"),
 Step("match vendor to payee registry",   C.C1, True,  False, True,  True,  "owner Sophie: alias table, exact after normalisation"),
 Step("compute due date",                 C.C0, False, False, True,  True,  "terms table"),
 Step("duplicate check",                  C.C0, False, False, True,  True,  "payee + normalised number"),
 Step("totals check",                     C.C0, False, False, True,  True,  "exact cents"),
 Step("categorise lines",                 C.C2, True,  False, True,  True,  "enum of nine; rule disagreement routes to human"),
 Step("payment authority decision",       C.C0, False, True,  False, True,  "owner Ian: gate v0.2 + registry + limits"),
 Step("choose payment date",              C.C0, False, False, True,  True,  "due date minus lead time"),
 Step("draft owner notice",               C.C3, True,  False, True,  True,  "draft only; send is a separate step"),
 Step("send owner notice",                C.C0, False, True,  False, True,  "owner Ian: fixed recipient, allow-list, rate limit"),
 Step("explain anomaly in plain words",   C.C3, True,  False, True,  True,  "shown to principal, no action attached"),
 Step("match payment to bank line",       C.C1, False, False, True,  True,  "amount + date window + reference"),
]
ASK_THE_MODEL = [Step(s.name, C.C3, s.untrusted_input or s.name in ("compute due date", "duplicate check", "totals check", "choose payment date", "payment authority decision", "send owner notice", "match payment to bank line"),
                      s.decides_authority, s.reversible, False, "") for s in CLASSIFIED]
def census(steps):
    d = {}
    for s in steps: d[f"C{int(s.cls)}"] = d.get(f"C{int(s.cls)}", 0) + 1
    return d
out = {}
for name, plan in (("classified", CLASSIFIED), ("ask_the_model", ASK_THE_MODEL)):
    f = lint(plan)
    out[name] = dict(steps=len(plan), census=census(plan), model_calls_per_invoice=sum(1 for s in plan if s.cls >= C.C2),
        authority_steps=[s.name for s in plan if s.decides_authority], authority_steps_on_model=[s.name for s in plan if s.decides_authority and s.cls >= C.C2],
        findings=f, finding_count=len(f), findings_by_code={k: sum(1 for x in f if x.startswith(k)) for k in ("L1", "L2", "L3", "L4", "L5")})
    print(f"{name:14} steps={len(plan)} census={census(plan)} model calls/invoice={out[name]['model_calls_per_invoice']} findings={len(f)} {out[name]['findings_by_code']}")
for x in out["ask_the_model"]["findings"][:6]: print("  ", x)
# single mutation: demote one authority step on the classified plan to a model and see the lint go red
mut = [Step(s.name, C.C3 if s.name == "payment authority decision" else s.cls, s.untrusted_input or s.name == "payment authority decision", s.decides_authority, s.reversible, s.checked_downstream, s.note) for s in CLASSIFIED]
out["mutation_authority_to_model"] = lint(mut)
print("mutation:", *out["mutation_authority_to_model"], sep="\n  ")
(here / "results/ch05_flow_audit.json").write_text(json.dumps(out, indent=1))
