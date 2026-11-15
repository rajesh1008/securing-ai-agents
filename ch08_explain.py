#!/usr/bin/env python3
"""Chapter 8 lab 6: explaining one payment to an examiner. 300 payments through the money path with an evidence row per step; then one row lost per payment, and the examiner's six questions are answered from what is left. No model."""
import json, random, sys, time, hashlib
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
from bulwark.moneypath import *
rng = random.Random(8006)
QUESTIONS = {"who asked": "task_token", "which invoice and amount": "invoice_binding", "which checks ran and what they said": "money_gate", "where the account came from": "destination_source", "who or what approved above the line": "money_gate", "what was sent and when": "dispatch"}
vs = Vendors({f"p{i}": Vendor(f"p{i}", f"V{i}", f"ACC{i}", 10**9, live_since=-300, created_day=-365, confirmed_by="kb") for i in range(6)})
invs = {}; g = MoneyGate("t", vs, invs, Ledger(), tenant_daily_cap=10**12, payee_daily_count=10**6, payee_daily_cents=10**12); disp = Dispatcher(g)
payments = []; t0 = time.perf_counter(); n = 0
for i in range(300):
    p = f"p{i % 6}"; amt = 10_000 + 137 * i; invs[f"I{i}"] = Invoice(f"I{i}", p, amt); r = PayRequest(f"I{i}", p, amt, doc_amount_cents=amt, day=100 + i // 6, approver="prin_kevin" if amt >= DUAL_CONTROL_CENTS else None)
    d = g.check(r)
    if d.outcome != "ALLOW": continue
    ok, why = disp.dispatch(r, d)
    seq = [("task_token", f"token tok_{i} issued to prin_emily for workload quill, one use, scope pay_invoice {r.invoice_id}"),
           ("invoice_binding", f"invoice {r.invoice_id} open in books at {amt} cents for payee {p}; request matches"),
           ("money_gate", f"bulwark-money-v0.3 outcome {d.outcome} codes {d.codes} approver {r.approver}"),
           ("destination_source", f"account {d.destination} read from vendor record {p} version {d.vendor_version}, confirmed_by kb, live since day -300"),
           ("dispatch", f"sent to {d.destination} idempotency key {d.key}")]
    payments.append([dict(id=f"e{i}_{k}", step=s, text=t) for k, (s, t) in enumerate(seq)])
dt = time.perf_counter() - t0
full = sum(all(not l.startswith("[gap]") for l in explain(rows)) for rows in payments)
lost = []; answered = 0; total_q = 0; gaps_by_step = {}
for rows in payments:
    drop = rng.randrange(len(rows)); left = rows[:drop] + rows[drop + 1:]; lost.append(rows[drop]["step"])
    steps = {r["step"] for r in left}
    for q, st in QUESTIONS.items(): total_q += 1; answered += st in steps
    gaps_by_step[rows[drop]["step"]] = gaps_by_step.get(rows[drop]["step"], 0) + 1
lines = [f"payments executed {len(payments)} of 300; explain() complete (no gap line) for {full}; run time for all decisions and evidence {dt*1000:.0f} ms",
         f"one random evidence row lost per payment: examiner questions answerable {answered} of {total_q} ({100*answered/total_q:.1f}%); rows lost by step {gaps_by_step}",
         "example explanation: " + " | ".join(explain(payments[17]))[:700],
         "example with token row lost: " + " | ".join(explain([r for r in payments[17] if r['step'] != 'task_token']))[:300]]
print("\n".join(lines)); (here / "results/ch08_explain.log").write_text("\n".join(lines) + "\n"); (here / "results/ch08_explain.json").write_text(json.dumps(dict(executed=len(payments), complete=full, answered=answered, total_q=total_q, gaps_by_step=gaps_by_step)))
