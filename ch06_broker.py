#!/usr/bin/env python3
"""Chapter 6 lab 7: a token broker for third-party credentials. No model calls.

Two designs hold the same bank refresh token. In design A the refresh token sits in the agent's
runtime (an environment variable); in design B it sits in a vault behind the broker and the runtime
holds only a per-task token. The same 40 hostile payment attempts are made by someone who has
copied what the runtime holds: 4 payees x 5 amounts x 2 replays. Hill Country's registered payee is
payee_lone_star; the task scope is that payee, one use, ceiling $2,500."""
import json
from pathlib import Path
from bulwark.models import ActionProposal, ActionKind
from bulwark.identity import Issuer, Verifier, Scope
from bulwark.broker import Broker, BankProvider
here = Path(__file__).resolve().parent
WL = "spiffe://ledgerly.example/ns/agents/sa/quill"
RT = "rt-hcb-0000-not-a-real-credential"
PAYEES = ["payee_lone_star", "payee_unknown_1", "payee_unknown_2", "payee_attacker"]
AMOUNTS = [10_000, 100_000, 250_000, 250_001, 5_000_000]
def pp(payee, amt):
    return ActionProposal(kind=ActionKind.INITIATE_PAYMENT, business_id="biz_hcb", principal_id="prin_emily", amount_cents=amt, payee_id=payee)
attempts = [(p, a) for p in PAYEES for a in AMOUNTS] * 2

# design A: refresh token in the runtime; the thief calls the provider directly
provA = BankProvider({"biz_hcb": RT})
for p, a in attempts: provA.pay(RT, p, a, via="direct")
A = dict(attempts=len(attempts), executed=sum(r["executed"] for r in provA.log),
         dollars=sum(r["amount_cents"] for r in provA.log if r["executed"]) // 100,
         distinct_payees=len({r["payee"] for r in provA.log if r["executed"]}))

# design B: the thief holds a copy of the task token and presents it from the right workload
iss = Issuer(); ver = Verifier(iss.public_keys(), lambda k: iss.status[k])
provB = BankProvider({"biz_hcb": RT}); broker = Broker(ver, provB, {"biz_hcb": RT})
tok = iss.issue(principal="prin_emily", tenant="biz_hcb", workload=WL, task_id="task_inv_88",
                scope=Scope(kinds=["initiate_payment"], payees=["payee_lone_star"], max_cents=250_000), uses=1)
for p, a in attempts: broker.pay(tok, pp(p, a), caller_workload=WL)
reasons = {}
for r in broker.refusals:
    for x in r: reasons[x] = reasons.get(x, 0) + 1
B = dict(attempts=len(attempts), executed=sum(r["executed"] for r in provB.log),
         dollars=sum(r["amount_cents"] for r in provB.log if r["executed"]) // 100,
         refused=len(broker.refusals), refusal_reasons=reasons,
         executed_rows_carry_jti=all(r["jti"] for r in provB.log if r["executed"]))
# the same copied token from a different workload
provC = BankProvider({"biz_hcb": RT}); brokerC = Broker(ver, provC, {"biz_hcb": RT})
tok2 = iss.issue(principal="prin_emily", tenant="biz_hcb", workload=WL, task_id="task_inv_89",
                 scope=Scope(kinds=["initiate_payment"], payees=["payee_lone_star"], max_cents=250_000), uses=1)
C = dict(attempts=len(attempts), executed=sum(brokerC.pay(tok2, pp(p, a), caller_workload="spiffe://evil/x").allow for p, a in attempts))
out = dict(A_refresh_token_in_runtime=A, B_broker_token_copied=B, C_broker_wrong_workload=C)
for k, v in out.items(): print(k, json.dumps(v))
(here / "results/ch06_broker.json").write_text(json.dumps(out, indent=1))
