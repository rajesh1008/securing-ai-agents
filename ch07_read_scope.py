#!/usr/bin/env python3
"""Chapter 7 lab 11 (no model calls): least privilege on the read side. Each task type has a column allow-list per table (ReadScope). 3,000 simulated reads: for each, a benign read the task needs
and a hostile read of the kind an injected instruction asks for (bank details, other customers' contact data, whole-table dumps). Compare: tenant-wide read (everything in the tenant's tables)
vs per-task column scope."""
import json, random, collections
from pathlib import Path
from bulwark.runtime_scope import *
here = Path(__file__).resolve().parent
R = random.Random(11)
FULL = {"invoices": ["inv_id", "payee_id", "amount_cents", "status", "due_day", "memo", "pdf_text"], "payees": ["payee_id", "name", "domain", "bank_account", "routing", "tax_id"],
        "customers": ["cust_id", "name", "domain", "overdue", "email", "phone", "balance"], "bank_lines": ["line_id", "amount_cents", "ref", "account_no", "counterparty"]}
NEED = {  # what a benign task asks for
 "answer_question": [("invoices", ["inv_id", "amount_cents", "status"]), ("payees", ["payee_id", "name"])],
 "process_invoice": [("invoices", ["inv_id", "payee_id", "amount_cents"]), ("payees", ["payee_id", "name"])],
 "pay_invoice": [("invoices", ["inv_id", "payee_id", "amount_cents", "status"])],
 "send_reminders": [("customers", ["cust_id", "domain", "overdue"]), ("invoices", ["inv_id", "amount_cents", "due_day"])],
 "reconcile_month": [("invoices", ["inv_id", "payee_id", "amount_cents", "due_day"]), ("bank_lines", ["line_id", "amount_cents", "ref"])],
 "handle_vendor_email": [("invoices", ["inv_id", "payee_id", "amount_cents"]), ("payees", ["payee_id", "name", "domain"])],
}
HOSTILE = [("payees", ["name", "bank_account", "routing"]), ("payees", ["tax_id"]), ("customers", ["email", "phone", "balance"]), ("bank_lines", ["account_no", "counterparty"]),
           ("invoices", ["pdf_text"]), ("customers", list(FULL["customers"])), ("payees", list(FULL["payees"]))]
res = {d: dict(benign_cols=0, benign_refused=0, hostile_reads=0, hostile_cols_returned=0, hostile_cols_total=0, hostile_any_sensitive=0) for d in ("tenant_wide", "per_task_columns")}
SENS = {"bank_account", "routing", "tax_id", "email", "phone", "balance", "account_no", "counterparty", "pdf_text"}
by_task = collections.defaultdict(lambda: [0, 0])
for _ in range(3000):
    tt = R.choice(TASK_TYPES)
    for tab, cols in NEED[tt]:
        for d in res:
            a, ref = (cols, []) if d == "tenant_wide" else read_filter(tt, tab, cols)
            res[d]["benign_cols"] += len(cols); res[d]["benign_refused"] += len(ref)
    tab, cols = R.choice(HOSTILE)
    for d in res:
        a, ref = (cols, []) if d == "tenant_wide" else read_filter(tt, tab, cols)
        res[d]["hostile_reads"] += 1; res[d]["hostile_cols_total"] += len(cols); res[d]["hostile_cols_returned"] += len(a)
        sens = [c for c in a if c in SENS]; res[d]["hostile_any_sensitive"] += bool(sens)
        if d == "per_task_columns": by_task[tt][0] += 1; by_task[tt][1] += bool(sens)
print(f"{'design':20}{'benign cols refused':>22}{'hostile reads returning a sensitive column':>46}{'sensitive cols returned / requested':>38}")
for d, r in res.items():
    sc = sum(1 for _ in ())
    print(f"{d:20}{r['benign_refused']:>12}/{r['benign_cols']:<9}{r['hostile_any_sensitive']:>25}/{r['hostile_reads']:<20}{r['hostile_cols_returned']:>20}/{r['hostile_cols_total']}")
print("per-task design, hostile reads that still returned a sensitive column, by task type:", {k: v for k, v in by_task.items()})
(here / "results/ch07_read_scope.json").write_text(json.dumps(dict(results=res, by_task={k: v for k, v in by_task.items()}), indent=1))
