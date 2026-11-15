#!/usr/bin/env python3
"""Chapter 6 lab 1: a case table against the per-task verifier and against the ambient tenant credential. No model calls."""
import json, time, base64, copy
from pathlib import Path
from bulwark.models import ActionProposal, ActionKind
from bulwark.identity import Issuer, Verifier, AmbientVerifier, Scope, SupportGrant, IssuanceRefused, b64e, b64d, AUD
here = Path(__file__).resolve().parent
class Clock:
    t = 1_800_000_000.0
    def __call__(self): return self.t
clock = Clock()
iss = Issuer(clock=clock)
ver = Verifier(iss.public_keys(), lambda k: iss.status[k], clock=clock, grace=600)
WL = "spiffe://ledgerly.example/ns/agents/sa/quill"
OTHER_WL = "spiffe://ledgerly.example/ns/agents/sa/support-bot"
def P(kind, **kw):
    base = dict(kind=kind, business_id="biz_hcb", principal_id="prin_emily")
    base.update(kw); return ActionProposal(**base)
PAY_SCOPE = Scope(kinds=["initiate_payment"], payees=["payee_lone_star"], max_cents=250_000)
def tok(**kw):
    d = dict(principal="prin_emily", tenant="biz_hcb", workload=WL, task_id="task_001", scope=PAY_SCOPE, ttl=300, uses=1)
    d.update(kw); return iss.issue(**d)
def tamper(token, **claim_changes):
    h, c, s = token.split("."); cl = json.loads(b64d(c)); cl.update(claim_changes)
    return h + "." + b64e(json.dumps(cl, sort_keys=True).encode()) + "." + s
def alg_none(token):
    h, c, s = token.split("."); hd = json.loads(b64d(h)); hd["alg"] = "none"
    return b64e(json.dumps(hd).encode()) + "." + c + "."
cases = []
def case(name, group, token_fn, proposal, expect_allow, workload=WL, task_id=None, setup=None, ambient_key="tenant-key-hcb"):
    cases.append(dict(name=name, group=group, token_fn=token_fn, proposal=proposal, expect=expect_allow, workload=workload, task_id=task_id, setup=setup, ambient_key=ambient_key))

pay = lambda amt=100_000, payee="payee_lone_star": P(ActionKind.INITIATE_PAYMENT, amount_cents=amt, payee_id=payee)
# ---- legitimate
case("B1 payment inside scope", "legit", lambda: tok(), pay(), True)
case("B2 payment exactly at ceiling", "legit", lambda: tok(), pay(250_000), True)
case("B3 read document with read scope", "legit", lambda: tok(scope=Scope(kinds=["read_document"])), P(ActionKind.READ_DOCUMENT, document_id="doc_1"), True)
case("B4 mail to allowed domain", "legit", lambda: tok(scope=Scope(kinds=["send_email"], mail_domains=["hillcountrybakehouse.example"])), P(ActionKind.SEND_EMAIL, recipient_email="emily@hillcountrybakehouse.example"), True)
case("B5 task id matches", "legit", lambda: tok(), pay(), True, task_id="task_001")
case("B6 previous key inside grace window", "legit", lambda: tok(), pay(), True, setup="rotate_inside_grace")
# ---- hostile or faulty
case("H1 payee outside token scope", "hostile", lambda: tok(), pay(payee="payee_riverside"), False)
case("H2 amount above ceiling by one cent", "hostile", lambda: tok(), pay(250_001), False)
case("H3 email with a payment-scoped token", "hostile", lambda: tok(), P(ActionKind.SEND_EMAIL, recipient_email="emily@hillcountrybakehouse.example"), False)
case("H4 replay after the budgeted use", "hostile", lambda: tok(), pay(), False, setup="use_once_first")
case("H5 expired token", "hostile", lambda: tok(ttl=60), pay(), False, setup="advance_120")
case("H6 claims edited: ceiling raised to $9,800", "hostile", lambda: tamper(tok(), scope=dict(kinds=["initiate_payment"], payees=["payee_lone_star"], max_cents=980_000, mail_domains=None)), pay(900_000), False)
case("H7 alg none", "hostile", lambda: alg_none(tok()), pay(), False)
case("H8 signed by an attacker key with a known kid", "hostile", lambda: "FORGED", pay(), False)
case("H9 token for another tenant", "hostile", lambda: tok(tenant="biz_other"), pay(), False)
case("H10 token for another principal", "hostile", lambda: tok(principal="prin_other"), pay(), False)
case("H11 token minted for another audience", "hostile", lambda: "WRONGAUD", pay(), False)
case("H12 stolen token presented by another workload", "hostile", lambda: tok(), pay(), False, workload=OTHER_WL)
case("H13 key revoked", "hostile", lambda: tok(), pay(), False, setup="revoke_key")
case("H14 key retired beyond the grace window", "hostile", lambda: tok(), pay(), False, setup="rotate_beyond_grace")
case("H15 support read-only session proposes a payment", "hostile", lambda: tok(actor="support_17", scope=Scope(kinds=["read_document", "query_books"])), pay(), False, setup="support_grant")
case("H16 token of task A used for task B", "hostile", lambda: tok(task_id="task_A"), pay(), False, task_id="task_B")
case("H17 token after its task closed", "hostile", lambda: tok(task_id="task_C"), pay(), False, setup="close_task_C")
case("H18 payment with a read scope token", "hostile", lambda: tok(scope=Scope(kinds=["read_document"])), pay(), False)
mint_refusals = []
def try_mint(name, fn):
    try: fn(); mint_refusals.append((name, False))
    except IssuanceRefused as e: mint_refusals.append((name, True, str(e)))

results = []
for c in cases:
    # fresh issuer state per case so cases cannot contaminate each other
    clock.t = 1_800_000_000.0
    iss = Issuer(clock=clock); ver = Verifier(iss.public_keys(), lambda k: iss.status[k], clock=clock, grace=600)
    su = c["setup"]
    if su == "support_grant": iss.grants.append(SupportGrant("support_17", "biz_hcb", "prin_emily", clock.t + 3600))
    token = c["token_fn"]()
    if token == "FORGED":
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        legit = tok(); h, cl, _ = legit.split(".")
        token = h + "." + cl + "." + b64e(Ed25519PrivateKey.generate().sign((h + "." + cl).encode()))
    if token == "WRONGAUD":
        legit = tok(); h, cl, s = legit.split("."); claims = json.loads(b64d(cl)); claims["aud"] = "some-other-service"
        token = iss._sign(claims)
    if su == "rotate_inside_grace": clock.t += 100; iss.rotate(); ver = Verifier(iss.public_keys(), lambda k: iss.status[k], clock=clock, grace=600)
    if su == "rotate_beyond_grace": clock.t += 100; iss.rotate(); clock.t += 900; ver = Verifier(iss.public_keys(), lambda k: iss.status[k], clock=clock, grace=600)
    if su == "revoke_key": iss.status[iss.current] = ("revoked", clock.t)
    if su == "advance_120": clock.t += 120
    if su == "close_task_C": ver.closed_tasks.add("task_C")
    if su == "use_once_first": ver.verify(token, c["proposal"], caller_workload=c["workload"])
    r = ver.verify(token, c["proposal"], caller_workload=c["workload"], task_id=c["task_id"])
    amb = AmbientVerifier({"biz_hcb": "tenant-key-hcb", "biz_other": "tenant-key-other"}).verify(c["ambient_key"], c["proposal"])
    results.append(dict(name=c["name"], group=c["group"], expect_allow=c["expect"], per_task_allow=r.allow, reasons=r.reasons, ambient_allow=amb.allow))
iss = Issuer(clock=clock); clock.t = 1_800_000_000.0
parent = tok(scope=Scope(kinds=["initiate_payment", "read_document"], payees=["payee_lone_star", "payee_riverside"], max_cents=500_000), ttl=600)
try_mint("M1 child with a wider ceiling", lambda: iss.derive(parent, scope=Scope(kinds=["initiate_payment"], payees=["payee_lone_star"], max_cents=900_000), workload=WL, ttl=100))
try_mint("M2 child with an extra kind", lambda: iss.derive(parent, scope=Scope(kinds=["initiate_payment", "send_email"], payees=["payee_lone_star"], max_cents=100_000), workload=WL, ttl=100))
try_mint("M3 child with no payee list (wider)", lambda: iss.derive(parent, scope=Scope(kinds=["initiate_payment"], payees=None, max_cents=100_000), workload=WL, ttl=100))
try_mint("M4 child outliving its parent", lambda: iss.derive(parent, scope=Scope(kinds=["initiate_payment"], payees=["payee_lone_star"], max_cents=100_000), workload=WL, ttl=3000))
try_mint("M5 support token without a grant", lambda: tok(actor="support_17", scope=Scope(kinds=["read_document"])))
iss.grants.append(SupportGrant("support_17", "biz_hcb", "prin_emily", clock.t + 3600))
try_mint("M6 support token for a payment under a read-only grant", lambda: tok(actor="support_17", scope=Scope(kinds=["initiate_payment"], payees=["payee_lone_star"], max_cents=1000)))
ok_child = iss.derive(parent, scope=Scope(kinds=["initiate_payment"], payees=["payee_lone_star"], max_cents=100_000), workload=WL, ttl=100)
mint_refusals.append(("M7 narrower, shorter child (should succeed)", ok_child is not None and True, "minted"))
hostile = [r for r in results if r["group"] == "hostile"]; legit = [r for r in results if r["group"] == "legit"]
S = dict(legit_cases=len(legit), legit_allowed_per_task=sum(r["per_task_allow"] for r in legit), legit_allowed_ambient=sum(r["ambient_allow"] for r in legit),
         hostile_cases=len(hostile), hostile_allowed_per_task=sum(r["per_task_allow"] for r in hostile), hostile_allowed_ambient=sum(r["ambient_allow"] for r in hostile),
         mint_refusals=sum(1 for m in mint_refusals[:6] if m[1]), mint_attempts=6, mismatches=[r["name"] for r in results if r["per_task_allow"] != r["expect_allow"]])
print(f"{'case':58} per-task  ambient  reason")
for r in results: print(f"{r['name']:58} {'ALLOW' if r['per_task_allow'] else 'deny ':8} {'ALLOW' if r['ambient_allow'] else 'deny ':8} {'; '.join(r['reasons'])[:70]}")
print("minting:")
for m in mint_refusals: print("  ", m[0], "->", ("refused: " + m[2]) if m[1] and len(m) > 2 and m[0][:2] != "M7" else ("minted" if m[0][:2] == "M7" else "NOT REFUSED"))
print(json.dumps(S))
# timing
iss = Issuer(); ver = Verifier(iss.public_keys(), lambda k: iss.status[k]); pr = pay()
tk = iss.issue(principal="prin_emily", tenant="biz_hcb", workload=WL, task_id="t", scope=PAY_SCOPE, uses=10**9)
N = 5000; t0 = time.perf_counter()
for _ in range(N): iss.issue(principal="prin_emily", tenant="biz_hcb", workload=WL, task_id="t", scope=PAY_SCOPE)
t_issue = (time.perf_counter() - t0) / N * 1e6
t0 = time.perf_counter()
for _ in range(N): ver.verify(tk, pr, caller_workload=WL)
t_ver = (time.perf_counter() - t0) / N * 1e6
print(f"issue {t_issue:.0f} us, verify {t_ver:.0f} us (mean of {N}, this box)")
(here / "results/ch06_identity_cases.json").write_text(json.dumps(dict(summary=S, results=results, mint=[list(m) for m in mint_refusals], issue_us=round(t_issue), verify_us=round(t_ver)), indent=1))
