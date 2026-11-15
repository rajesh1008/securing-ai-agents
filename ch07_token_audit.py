#!/usr/bin/env python3
"""Chapter 7 lab 12 (no model calls): the ten-token diff. Issue 600 tokens under two issuers (role-default scope vs computed scope), then audit the token store the way a reviewer would:
distinct scopes per task type, the share of tokens whose scope equals the role default, and the mean reach."""
import json, random, collections
from pathlib import Path
from bulwark.identity import Issuer, b64d, Scope
from bulwark.runtime_scope import *
here = Path(__file__).resolve().parent
WL = "spiffe://ledgerly.example/ns/agents/sa/quill"
B = make_books(); CEIL = Ceiling(kinds=ALL_KINDS, payees=list(B.payees), max_cents=250_000, mail_domains=[c["domain"] for c in B.customers.values()] + [p["domain"] for p in B.payees.values()])
ROLE = Scope(kinds=CEIL.kinds, payees=CEIL.payees, max_cents=CEIL.max_cents, mail_domains=CEIL.mail_domains)
R = random.Random(5)
open_invs = [k for k, v in B.invoices.items() if v["status"] == "open"]
def req():
    tt = R.choice(TASK_TYPES); p = {}
    if tt == "pay_invoice": p = {"invoice_id": R.choice(open_invs)}
    if tt == "send_reminders": p = {"customer_ids": R.sample(list(B.customers), 8)}
    if tt == "reconcile_month": p = {"today": R.randrange(0, 30), "window_days": 7}
    if tt == "handle_vendor_email": p = {"payee_id": R.choice(list(B.payees))}
    return TaskRequest(tt, "prin_emily", "biz_hcb", p)
# the table of three hand-typed task types from Chapter 6's lab, with the role default for everything else
HAND = {"answer_question": Scope(kinds=["query_books", "read_document"]), "draft_reminders": Scope(kinds=["draft_invoice", "send_invoice", "send_email"], mail_domains=["hillcountrybakehouse.example"]),
        "pay_invoice": Scope(kinds=["initiate_payment"], payees=["payee_lone_star"], max_cents=250_000)}
issuers = {"role_default_with_hand_table": Issuer(), "computed_per_task": Issuer()}; stores = {k: [] for k in issuers}
for n in range(600):
    r = req()
    try: comp = compute_scope(r, B, CEIL)
    except ScopeRefused: continue
    hand = HAND.get(r.task_type, ROLE)
    for name, sc in (("role_default_with_hand_table", hand), ("computed_per_task", comp)):
        t = issuers[name].issue(principal="prin_emily", tenant="biz_hcb", workload=WL, task_id=f"{r.task_type}:{n}", scope=sc, uses=3)
        c = json.loads(b64d(t.split(".")[1])); c["_type"] = r.task_type; stores[name].append(c)
out = {}
for name, store in stores.items():
    sig = lambda c: json.dumps(c["scope"], sort_keys=True)
    default_sig = json.dumps(ROLE.to_json(), sort_keys=True)
    by = collections.defaultdict(set)
    for c in store: by[c["_type"]].add(sig(c))
    n_default = sum(1 for c in store if sig(c) == default_sig)
    reaches = [reach(Scope(**c["scope"]), B) for c in store]
    out[name] = dict(tokens=len(store), distinct_scopes=len({sig(c) for c in store}), role_default_tokens=n_default, role_default_share=round(n_default / len(store), 3),
                     mean_kinds=round(sum(r["kinds"] for r in reaches) / len(reaches), 2), mean_payees=round(sum(r["payees"] for r in reaches) / len(reaches), 2),
                     types_with_one_scope={t: len(v) == 1 for t, v in by.items()})
    print(name, json.dumps({k: v for k, v in out[name].items() if k != "types_with_one_scope"}))
    print("   task types whose tokens all carry one identical scope:", sorted(t for t, v in by.items() if len(v) == 1))
(here / "results/ch07_token_audit.json").write_text(json.dumps(out, indent=1))
