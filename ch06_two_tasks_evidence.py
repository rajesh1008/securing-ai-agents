#!/usr/bin/env python3
"""Chapter 6 lab 3: the two-task test (Chapter 2 stub), a credential mix-up fault, and what the evidence can say about 'who'. No model calls."""
import json, random
from pathlib import Path
from bulwark.models import ActionProposal, ActionKind
from bulwark.identity import Issuer, Verifier, Scope, SupportGrant, IssuanceRefused, b64d
from bulwark.authority import EvidenceChain
here = Path(__file__).resolve().parent
rng = random.Random(6006)
WL = "spiffe://ledgerly.example/ns/agents/sa/quill"
class Clock:
    t = 1_800_000_000.0
    def __call__(self): return self.t
clock = Clock(); iss = Issuer(clock=clock); ver = Verifier(iss.public_keys(), lambda k: iss.status[k], clock=clock)
TENANTS = {"biz_hcb": ("prin_emily", "Hill Country Bakehouse", "payee_lone_star"), "biz_btx": ("prin_btx_owner", "Barton Creek Plumbing", "payee_riverside")}
ledgers = {"ambient": {t: [] for t in TENANTS}, "per_task": {t: [] for t in TENANTS}}
# ---- two tasks, interleaved, 100 payment actions each; a fault hands the adapter the other task's credential on 15% of calls
N = 100; FAULT = 0.15
tasks = {}
for biz, (prin, name, payee) in TENANTS.items():
    tid = f"task_{biz}"
    tasks[biz] = dict(tid=tid, token=iss.issue(principal=prin, tenant=biz, workload=WL, task_id=tid, ttl=3600, uses=N * 2, scope=Scope(kinds=["initiate_payment"], payees=[payee], max_cents=250_000)), prin=prin, payee=payee)
faults = 0; per_task_denied = 0; ambient_wrong = 0; per_task_wrong = 0
order = [b for _ in range(N) for b in TENANTS]
for i, biz in enumerate(order):
    t = tasks[biz]; other = [b for b in TENANTS if b != biz][0]
    pr = ActionProposal(kind=ActionKind.INITIATE_PAYMENT, business_id=biz, principal_id=t["prin"], amount_cents=rng.randrange(10_000, 200_000, 100), payee_id=t["payee"])
    mixed = rng.random() < FAULT; faults += mixed
    # ambient: one worker holds both tenants' credentials and picks by a 'current task' variable that the fault corrupts
    book = other if mixed else biz
    ledgers["ambient"][book].append(pr.amount_cents)
    ambient_wrong += (book != biz)
    # per-task: the adapter presents whichever token it was handed; the verifier compares it with the proposal
    presented = tasks[other]["token"] if mixed else t["token"]
    r = ver.verify(presented, pr, caller_workload=WL, task_id=t["tid"])
    if r.allow: ledgers["per_task"][biz].append(pr.amount_cents)
    else: per_task_denied += 1
    per_task_wrong += (r.allow and mixed)
two = dict(actions=len(order), fault_rate=FAULT, faults_injected=faults, ambient_executed_in_wrong_tenant=ambient_wrong, per_task_executed_in_wrong_tenant=per_task_wrong,
           per_task_denied=per_task_denied, per_task_denied_equals_faults=(per_task_denied == faults))
print("two-task test:", json.dumps(two))
# ---- evidence: who did each action?
def run_evidence(label, per_task: bool):
    chain = EvidenceChain(here / f"results/ch06_evidence_{label}.jsonl"); rows = []
    iss2 = Issuer(clock=clock); ver2 = Verifier(iss2.public_keys(), lambda k: iss2.status[k], clock=clock)
    iss2.grants.append(SupportGrant("support_17", "biz_hcb", "prin_emily", clock.t + 3600))
    plan = [("owner", "initiate_payment")] * 40 + [("support", "read_document")] * 10 + [("support", "initiate_payment")] * 5
    for who, kind in plan:
        if kind == "read_document":
            pr = ActionProposal(kind=ActionKind.READ_DOCUMENT, business_id="biz_hcb", principal_id="prin_emily", document_id="doc_9")
            scope = Scope(kinds=["read_document", "query_books"])
        else:
            pr = ActionProposal(kind=ActionKind.INITIATE_PAYMENT, business_id="biz_hcb", principal_id="prin_emily", amount_cents=50_000, payee_id="payee_lone_star")
            scope = Scope(kinds=["initiate_payment"], payees=["payee_lone_star"], max_cents=250_000) if who == "owner" else Scope(kinds=["read_document", "query_books"])
        tid = f"t{len(rows)}"
        tok = iss2.issue(principal="prin_emily", tenant="biz_hcb", workload=WL, task_id=tid, scope=scope, ttl=300, actor=("support_17" if who == "support" else None))
        r = ver2.verify(tok, pr, caller_workload=WL, task_id=tid)
        if per_task:
            c = json.loads(b64d(tok.split(".")[1]))
            rec = dict(event="action", kind=kind, allow=r.allow, principal=c["sub"], agent=c["act"]["sub"], agent_ver=c["act"]["ver"], task=c["tid"], jti=c["jti"], kid=json.loads(b64d(tok.split(".")[0]))["kid"], actor=c.get("actor"), acting_for=(c["sub"] if c.get("actor") else None))
        else:
            rec = dict(event="action", kind=kind, allow=True, principal="prin_emily", agent="quill")   # ambient: the tenant credential allows all
        chain.append(rec); rows.append(rec)
    return rows, plan
out = {}
for label, pt in (("ambient", False), ("per_task", True)):
    rows, plan = run_evidence(label, pt)
    support = [r for r, p in zip(rows, plan) if p[0] == "support"]
    distinguishable = sum(1 for r in support if r.get("actor"))
    executed = [r for r in rows if r["allow"]]
    complete = sum(1 for r in executed if all(r.get(k) for k in ("principal", "agent", "task", "jti"))) if pt else 0
    out[label] = dict(rows=len(rows), executed=len(executed), support_rows=len(support), support_rows_with_actor=distinguishable,
                      support_payments_executed=sum(1 for r, p in zip(rows, plan) if p[0] == "support" and p[1] == "initiate_payment" and r["allow"]),
                      executed_rows_with_principal_agent_task_jti=complete)
    print(label, json.dumps(out[label]))
(here / "results/ch06_two_tasks_evidence.json").write_text(json.dumps(dict(two_task=two, evidence=out), indent=1))
