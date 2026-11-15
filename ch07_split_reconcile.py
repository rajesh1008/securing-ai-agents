#!/usr/bin/env python3
"""Chapter 7 lab 13 (no model calls): splitting reconcile_month into a reader (match_bank_lines: read kinds only) and an actor (pay_matched: pays invoices matched by a deterministic rule).
2,000 runs; each run has the invoices due in its window and one bank line per invoice; 15% of lines are 'fuzzy' (reference garbled or amount off by a fee) and the deterministic matcher leaves them for a person.
Hostile steering arrives while the reader reads (3-25 payment attempts to in-window payees under the per-action ceiling). Compare the single task with invoice binding (Section 7.12) and the split."""
import json, random
from pathlib import Path
from bulwark.runtime_scope import *
here = Path(__file__).resolve().parent
B = make_books(); CEIL = Ceiling(kinds=ALL_KINDS, payees=list(B.payees), max_cents=250_000, mail_domains=[])
R = random.Random(404); runs = 0
S = {"single_with_binding": dict(hostile_exec=0, hostile_cents=0, benign_auto=0, benign_to_person=0), "split": dict(hostile_exec=0, hostile_cents=0, benign_auto=0, benign_to_person=0)}
for _ in range(2000):
    today = R.randrange(0, 30); req = TaskRequest("reconcile_month", "p", "t", {"today": today, "window_days": 7}, "scheduler")
    try: single = compute_scope(req, B, CEIL)
    except ScopeRefused: continue
    runs += 1
    due = {k: v for k, v in B.invoices.items() if v["status"] == "open" and v["due_day"] <= today + 7}
    lines = {k: dict(ref=k if R.random() > 0.15 else "garbled", amount=v["amount_cents"] if R.random() > 0.0 else 0) for k, v in due.items()}
    for k, l in lines.items():
        if l["ref"] == "garbled" and R.random() < 0.5: l["ref"] = k; l["amount"] = due[k]["amount_cents"] - 350   # fee deducted
    hostile = []
    for _ in range(R.randrange(3, 26)):
        iid = R.choice(list(due)); hostile.append((iid, due[iid]["payee_id"], R.randrange(5_000, single.max_cents + 1, 100)))
    # --- single task: scope pays, SpendMeter binds invoices; the hostile payments arrive among the real ones
    m = SpendMeter(sum(v["amount_cents"] for v in due.values()), due)
    steps = [("b", i, v["payee_id"], v["amount_cents"]) for i, v in due.items()] + [("h", i, p, a) for i, p, a in hostile]; R.shuffle(steps)
    for kind, iid, p, a in steps:
        ok = admits(single, "initiate_payment", payee=p, amount=a) and m.try_pay(a, iid, p)[0]
        if kind == "b": S["single_with_binding"]["benign_auto" if ok else "benign_to_person"] += 1
        elif ok: S["single_with_binding"]["hostile_exec"] += 1; S["single_with_binding"]["hostile_cents"] += a
    # --- split: the reader holds no payment kind; the actor is issued from the deterministic matcher's output only
    reader = compute_scope(TaskRequest("match_bank_lines", "p", "t"), B, CEIL)
    for iid, p, a in hostile:
        if admits(reader, "initiate_payment", payee=p, amount=a): S["split"]["hostile_exec"] += 1; S["split"]["hostile_cents"] += a
    matched = [i for i, l in lines.items() if l["ref"] == i and l["amount"] == due[i]["amount_cents"]]
    S["split"]["benign_auto"] += len(matched); S["split"]["benign_to_person"] += len(due) - len(matched)
    if matched:
        actor = compute_scope(TaskRequest("pay_matched", "p", "t", {"matched_invoice_ids": matched}), B, CEIL)
        for i in matched: assert admits(actor, "initiate_payment", payee=due[i]["payee_id"], amount=due[i]["amount_cents"])
print(f"{runs} reconcile runs\n{'design':24}{'hostile executed':>18}{'hostile $':>12}{'legit paid automatically':>26}{'legit sent to a person':>24}")
for k, v in S.items(): print(f"{k:24}{v['hostile_exec']:>18}{v['hostile_cents']/100:>12,.0f}{v['benign_auto']:>26}{v['benign_to_person']:>24}")
(here / "results/ch07_split_reconcile.json").write_text(json.dumps(dict(runs=runs, results=S), indent=1))
