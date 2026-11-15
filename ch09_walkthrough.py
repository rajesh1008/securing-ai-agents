#!/usr/bin/env python3
"""Chapter 9: five raw model outputs through the Quill v0.3 intake path: strict_parse -> build_pay_request -> MoneyGate -> Dispatcher.
The raw texts are hand-written stand-ins in the shapes recorded in Chapter 1-6 labs (fenced, extra fields) plus two hostile ones. No model."""
import sys, json
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
from bulwark.moneypath import *
from bulwark.schema import *
vs = Vendors({"p_ls": Vendor("p_ls", "Lone Star Paper Supply", "US-ACC-4417", 400_000, live_since=-400, created_day=-500, confirmed_by="kb")})
invs = {"INV-1007": Invoice("INV-1007", "p_ls", 141_200), "INV-2001": Invoice("INV-2001", "p_ls", 260_000)}
g = MoneyGate("biz_hcb", vs, invs, Ledger()); disp = Dispatcher(g); L = []
def run(title, raw, doc=141_200):
    L.append(f"{title}\n  raw: {raw[:150]!r}")
    p = strict_parse(raw, PAY_INVOICE)
    if not p.ok:
        L.append(f"  schema: REJECT {p.code}\n  notice to model: {reject_notice(p.code, PAY_INVOICE)}"); return
    r = build_pay_request(p.value, 100, "prin_emily", doc)
    d = g.check(r); ok, why = disp.dispatch(r, d) if d.outcome == "ALLOW" else (False, "not allowed")
    L.append(f"  schema: ok notes={p.notes} value={p.value}\n  request: {r}\n  gate: {d.outcome} {d.codes}; dispatch: {ok} ({why})")
run("1. Clean, fenced, three fields", '```json\n{"invoice_id": "INV-1007", "payee_id": "p_ls", "amount_cents": 141200}\n```')
run("2. The old Quill v0.2 reply shape: identity, currency and name restated", '```json\n{"kind": "initiate_payment", "business_id": "biz_hcb", "principal_id": "prin_emily", "amount_cents": 141200, "currency": "USD", "payee_id": "p_ls", "payee_name": "Lone Star Paper Supply", "rationale": "Payment for INV-1007"}\n```')
run("3. Mass assignment: the model supplies the second approver", '{"invoice_id": "INV-2001", "payee_id": "p_ls", "amount_cents": 260000, "approver": "kevin_brandt"}', doc=260_000)
run("4. Well-formed and wrong: right shape, unknown payee", '{"invoice_id": "INV-1007", "payee_id": "p_evil", "amount_cents": 141200}')
run("5. Well-formed, right values, but 260,000 needs a second person", '{"invoice_id": "INV-2001", "payee_id": "p_ls", "amount_cents": 260000}', doc=260_000)
# bounded retry with a scripted stand-in model that obeys the notice on the second try
calls = []
def scripted(notice):
    calls.append(notice)
    return ('```json\n{"kind": "initiate_payment", "payee_id": "p_ls", "invoice_id": "INV-1008", "amount_cents": 5000}\n```' if notice is None else '{"invoice_id": "INV-1008", "payee_id": "p_ls", "amount_cents": 5000}')
p, n, codes = parse_with_retry(scripted, PAY_INVOICE, 2)
L.append(f"6. Retry: scripted stand-in model (not a measurement). attempts={n} ok={p.ok} first reject={codes}\n  notice sent: {calls[1]}")
print("\n".join(L)); (here / "results/ch09_walkthrough.log").write_text("\n".join(L) + "\n")
