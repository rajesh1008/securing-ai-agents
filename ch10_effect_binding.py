#!/usr/bin/env python3
"""Chapter 10, lab 1: what an approval is bound to. A held payment is approved by a second person; then something changes before dispatch.
Designs: D0 approval is a flag on the ticket; D1 bound to invoice+payee; D2 bound to invoice+payee+amount; D3 (Bulwark) bound to a digest of the full effect
including destination account and vendor record version, with the waiver limited to the hold families the person was shown.
D0-D2 release the hold wholesale (waive every hold). Dispatcher recheck is off for all four so that only the binding differs.
No model. 20 seeded variants per class and design."""
import sys, json, random
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
from bulwark.moneypath import *
from bulwark.approval import *
FAMS = frozenset(["M3_document_amount_differs_from_books", "M3_document_amount_not_found", "M4_bank_change_pending", "M4_account_not_yet_seasoned", "M4_account_never_confirmed",
                  "M5_payee_daily_count", "M5_payee_daily_cents", "M5_tenant_daily_cap", "M6_new_payee", "M7_likely_duplicate", "M8_dual_control_missing"])
CLASSES = [("c0_nothing_changes", "control: nothing changes"), ("c1_amount_edited", "amount of the same invoice edited in the books"), ("c2_destination_changed", "vendor bank account changed and confirmed"),
           ("c3_swap_invoice", "pending request points at another invoice, same payee"), ("c4_swap_payee", "pending request points at another seasoned payee"), ("c5_swap_new_payee", "pending request points at a payee added 3 days ago"),
           ("c6_new_velocity", "other payments to the payee land after approval"), ("c7_bank_change_email", "bank-change request arrives after approval")]
def build(rng):
    amt = rng.randrange(200_000, 380_000, 100)
    v = Vendors({"p1": Vendor("p1", "Lone Star Paper Supply", "US-ACC-4417", 1_000_000, live_since=-300, created_day=-365, confirmed_by="kb"),
                 "p2": Vendor("p2", "Riverside Office Interiors", "US-ACC-5521", 1_000_000, live_since=-300, created_day=-365, confirmed_by="kb"),
                 "p3": Vendor("p3", "Zilker Packaging", "US-ACC-7788", 1_000_000, live_since=97, created_day=97, confirmed_by="kb")})
    inv = {"I1": Invoice("I1", "p1", amt, number="LSP-1"), "I2": Invoice("I2", "p1", rng.randrange(200_000, 380_000, 100), number="LSP-2"), "I3": Invoice("I3", "p2", rng.randrange(200_000, 380_000, 100), number="RIO-9"),
           "I4": Invoice("I4", "p3", rng.randrange(200_000, 380_000, 100), number="ZP-3")}
    g = MoneyGate("t", v, inv, Ledger(), tenant_daily_cap=10**9, payee_daily_count=2, payee_daily_cents=10**9); return g, v, inv, amt
def mutate(cls, g, v, inv, rng):
    """Apply the change to the world; return the (possibly different) request the pending state now holds."""
    r0 = PayRequest("I1", "p1", inv["I1"].amount_cents, doc_amount_cents=inv["I1"].amount_cents, day=100, principal="emily")
    if cls == "c1_amount_edited": inv["I1"].amount_cents += rng.randrange(100_000, 900_000, 100); return PayRequest("I1", "p1", inv["I1"].amount_cents, doc_amount_cents=inv["I1"].amount_cents, day=100, principal="emily")
    if cls == "c2_destination_changed": v.request_change("p1", "GB33BUKB20201555555555", 100, "vendor_portal"); v.confirm_change("p1", 100, "kb", True); return r0
    if cls == "c3_swap_invoice": return PayRequest("I2", "p1", inv["I2"].amount_cents, doc_amount_cents=inv["I2"].amount_cents, day=100, principal="emily")
    if cls == "c4_swap_payee": return PayRequest("I3", "p2", inv["I3"].amount_cents, doc_amount_cents=inv["I3"].amount_cents, day=100, principal="emily")
    if cls == "c5_swap_new_payee": return PayRequest("I4", "p3", inv["I4"].amount_cents, doc_amount_cents=inv["I4"].amount_cents, day=100, principal="emily")
    if cls == "c6_new_velocity":
        for k in range(2): g.ledger.reserve(f"x{k}", f"X{k}", "p1", 10_000 + k, 100, "US-ACC-4417")
        return r0
    if cls == "c7_bank_change_email": v.request_change("p1", "GB33BUKB20201555555555", 100, "email"); return r0
    return r0
def run_naive(design, cls, rng):
    g, v, inv, amt = build(rng); disp = Dispatcher(g, recheck=False)
    r = PayRequest("I1", "p1", amt, doc_amount_cents=amt, day=100, principal="emily"); d = g.check(r, reserve=False); assert d.outcome == "HOLD" and any(c.startswith("M8") for c in d.codes), d
    approved = dict(inv="I1", payee="p1", amt=amt)
    r2 = mutate(cls, g, v, inv, rng)
    bind = {"D0": [], "D1": ["inv", "payee"], "D2": ["inv", "payee", "amt"]}[design]
    cur = dict(inv=r2.invoice_id, payee=r2.payee_id, amt=r2.amount_cents)
    if any(cur[k] != approved[k] for k in bind): return "refused_binding"
    d2 = g.check(PayRequest(r2.invoice_id, r2.payee_id, r2.amount_cents, doc_amount_cents=r2.doc_amount_cents, day=100, principal="emily", approver="kevin"), waived=FAMS)
    if d2.outcome != "ALLOW": return "gate_" + d2.outcome.lower()
    ok, _ = disp.dispatch(r2, d2); return "executed" if ok else "dispatch_refused"
def run_d3(cls, rng):
    g, v, inv, amt = build(rng); disp = Dispatcher(g, recheck=False)
    people = {"emily": Person("emily", "Emily Carter", 10**8), "kevin": Person("kevin", "Kevin Brandt", 10**8)}
    svc = ApprovalService(b"x" * 32, people, "t"); svc.login("tk", "kevin", 100); rel = Release(svc, g, disp)
    r = PayRequest("I1", "p1", amt, doc_amount_cents=amt, day=100, principal="emily"); d = g.check(r, reserve=False); t = svc.open_ticket(r, d, v)
    gr = svc.decide(t.tid, "tk", "approve", 100); assert isinstance(gr, Grant)
    r2 = mutate(cls, g, v, inv, rng); ok, why, dec = rel.release(r2, gr)
    if ok: return "executed"
    return "refused_binding" if why in ("effect_changed_since_approval",) else ("gate_hold" if "hold" in why else "other:" + why)
N = 20; res = {}; L = []; P = L.append
for cls, _ in CLASSES:
    for design in ("D0", "D1", "D2", "D3"):
        c = {}
        for i in range(N):
            rng = random.Random(f"{cls}{i}")                     # the same world for every design
            out = run_d3(cls, rng) if design == "D3" else run_naive(design, cls, rng); c[out] = c.get(out, 0) + 1
        res[f"{cls}|{design}"] = c
P(f"{'class':50s} " + " ".join(f"{d:>5s}" for d in ("D0", "D1", "D2", "D3")) + "   (executed of 20; the payment that executed is not the one the person approved, except in c0)")
tot = {d: 0 for d in ("D0", "D1", "D2", "D3")}
for cls, desc in CLASSES:
    cells = []
    for d in ("D0", "D1", "D2", "D3"):
        n = res[f"{cls}|{d}"].get("executed", 0); cells.append(f"{n:>5d}")
        if cls != "c0_nothing_changes": tot[d] += n
    P(f"{cls + ': ' + desc:50s} " + " ".join(cells))
P(f"{'TOTAL substituted payments executed (c1-c7, of 140)':50s} " + " ".join(f"{tot[d]:>5d}" for d in ("D0", "D1", "D2", "D3")))
P("\nwhat happened to the ones that did not execute (D3):")
for cls, _ in CLASSES: P(f"  {cls:26s} {res[cls + '|D3']}")
P("what happened to the ones that did not execute (D2):")
for cls, _ in CLASSES: P(f"  {cls:26s} {res[cls + '|D2']}")
print("\n".join(L)); (here / "results/ch10_effect_binding.log").write_text("\n".join(L) + "\n"); json.dump(res, open(here / "results/ch10_effect_binding.json", "w"), indent=1)
