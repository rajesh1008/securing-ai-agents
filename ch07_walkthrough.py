#!/usr/bin/env python3
"""Chapter 7 walkthrough: one payment task from request to evidence, with real Issuer, Verifier and compute_scope. No model calls: the proposals are hand-built (one legitimate, four hostile)."""
import json, time
from pathlib import Path
from bulwark.models import ActionProposal, ActionKind as K
from bulwark.identity import Issuer, Verifier, b64d
from bulwark.runtime_scope import *
from bulwark.authority import EvidenceChain
here = Path(__file__).resolve().parent
WL = "spiffe://ledgerly.example/ns/agents/sa/quill"
B = make_books(); CEIL = Ceiling(kinds=ALL_KINDS, payees=list(B.payees), max_cents=250_000, mail_domains=[c["domain"] for c in B.customers.values()] + [p["domain"] for p in B.payees.values()])
inv_id = next(k for k, v in B.invoices.items() if v["status"] == "open"); inv = B.invoices[inv_id]
other = next(p for p in B.payees if p != inv["payee_id"])
req = TaskRequest("pay_invoice", "prin_emily", "biz_hcb", {"invoice_id": inv_id})
scope = compute_scope(req, B, CEIL)
iss = Issuer(); ver = Verifier(iss.public_keys(), lambda k: iss.status[k])
tok = iss.issue(principal="prin_emily", tenant="biz_hcb", workload=WL, task_id="task_pay_0001", scope=scope, ttl=300, uses=2)
claims = json.loads(b64d(tok.split(".")[1]))
print("task request :", req.task_type, req.params)
print("scope        :", json.dumps(scope.to_json()))
print("loadout shown to the model:", loadout_kinds(scope))
print("token claims :", json.dumps({k: claims[k] for k in ("sub", "biz", "tid", "uses", "scope")}))
def P(kind, **kw): return ActionProposal(kind=kind, business_id="biz_hcb", principal_id="prin_emily", **kw)
steps = [
 ("legitimate payment of the invoice", P(K.INITIATE_PAYMENT, payee_id=inv["payee_id"], amount_cents=inv["amount_cents"], memo=inv_id)),
 ("injected: pay another registered payee", P(K.INITIATE_PAYMENT, payee_id=other, amount_cents=inv["amount_cents"], memo=inv_id)),
 ("injected: raise the amount", P(K.INITIATE_PAYMENT, payee_id=inv["payee_id"], amount_cents=inv["amount_cents"] + 10_000, memo=inv_id)),
 ("injected: email the customer list to the vendor", P(K.SEND_EMAIL, recipient_email="ap@" + B.payees[inv["payee_id"]]["domain"], memo="customer list")),
 ("injected: read another document", P(K.READ_DOCUMENT, document_id="doc_77")),
]
chain = EvidenceChain(here / "results/ch07_walkthrough_evidence.jsonl")
for label, p in steps:
    r = ver.verify(tok, p, caller_workload=WL, task_id="task_pay_0001")
    print(f"{'ALLOW' if r.allow else 'DENY ':6}{label:50}{'' if r.allow else '  <- ' + '; '.join(r.reasons)}")
    chain.append(dict(event="action", kind=p.kind.value, allow=r.allow, reasons=r.reasons, payee_id=p.payee_id, amount_cents=p.amount_cents, principal=claims["sub"], task=claims["tid"], jti=claims["jti"], scope_digest=hex(hash(json.dumps(claims["scope"], sort_keys=True)) & 0xffffffff)))
print("evidence chain verifies:", EvidenceChain.verify(here / "results/ch07_walkthrough_evidence.jsonl"))
