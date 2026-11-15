#!/usr/bin/env python3
"""Chapter 10: one invoice, two approvals. Real ApprovalService, MoneyGate and Dispatcher output. No model."""
import sys, json
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
from bulwark.moneypath import *
from bulwark.approval import *
v = Vendors({"p": Vendor("p", "Lone Star Paper Supply", "US-ACC-4417", 1_000_000, live_since=-400, created_day=-500, confirmed_by="kevin_brandt")})
inv = {"INV-1007": Invoice("INV-1007", "p", 260_000, number="LSP-88213"), "INV-1009": Invoice("INV-1009", "p", 260_000, number="LSP-88301")}
g = MoneyGate("biz_hcb", v, inv, Ledger()); disp = Dispatcher(g)
people = {"emily": Person("emily", "Emily Carter", 10**8), "kevin": Person("kevin", "Kevin Brandt", 10**8, can_edit_vendors=True), "sam": Person("sam", "Sophie Adler", 10**8)}
svc = ApprovalService(b"walkthrough-key-not-a-secret" * 2, people, "biz_hcb"); rel = Release(svc, g, disp)
for tok, pid in (("tok_emily", "emily"), ("tok_kevin", "kevin"), ("tok_sophie", "sam")): svc.login(tok, pid, 100)
L = []; P = L.append
r1 = PayRequest("INV-1007", "p", 260_000, doc_amount_cents=260_000, day=100, principal="emily"); d1 = g.check(r1)
P(f"1. Gate on INV-1007 ($2,600.00, no second person): {d1.outcome} {d1.codes}")
t1 = svc.open_ticket(r1, d1, v, note="Quarterly paper order, vendor asked for prompt payment. Safe to release.")
P("\n" + svc.render(t1, v, g.invoices, g.ledger, 100))
P(f"\n   Emily (requester) tries to approve: {svc.decide(t1.tid, 'tok_emily', 'approve', 100)}")
gr1 = svc.decide(t1.tid, "tok_kevin", "approve", 100); P(f"   Kevin approves: grant for digest {gr1.digest[:12]}, waives {gr1.waived}, approver {gr1.approver}")
ok, why, dec = rel.release(r1, gr1); P(f"   release: sent={ok} ({why}); decision {dec.outcome if dec else None}")
r2 = PayRequest("INV-1009", "p", 260_000, doc_amount_cents=260_000, day=101, principal="emily"); d2 = g.check(r2, reserve=False)
P(f"\n2. Next day, INV-1009 ($2,600.00): {d2.outcome} {d2.codes}")
t2 = svc.open_ticket(r2, d2, v); gr2 = svc.decide(t2.tid, "tok_kevin", "approve", 101); P(f"   Kevin approves at day 101: grant {gr2.nonce}")
v.request_change("p", "GB33BUKB20201555555555", 101, "vendor_portal"); svc.pending_change_authors["p"] = "kevin"; v.confirm_change("p", 101, "kevin_brandt", True)
P(f"   Before release, the vendor's bank account is changed and confirmed (record now v{v.v['p'].version}).")
ok, why, dec = rel.release(r2, gr2); P(f"   release with the old grant: sent={ok} ({why})")
d3 = g.check(PayRequest("INV-1009", "p", 260_000, doc_amount_cents=260_000, day=101, principal="emily"), reserve=False); P(f"3. New gate decision: {d3.outcome} {d3.codes}")
t3 = svc.open_ticket(r2, d3, v); P("\n" + svc.render(t3, v, g.invoices, g.ledger, 101))
P(f"\n   Kevin (who confirmed the change) tries to approve: {svc.decide(t3.tid, 'tok_kevin', 'approve', 101, callback_ok=True)}")
P(f"   Sophie approves without a call-back: {svc.decide(t3.tid, 'tok_sophie', 'approve', 101)}")
gr3 = svc.decide(t3.tid, "tok_sophie", "approve", 101, callback_ok=True); P(f"   Sophie approves after calling the vendor: waives {gr3.waived}")
ok, why, dec = rel.release(r2, gr3); P(f"   release: sent={ok} ({why}) to {dec.destination if dec else None}")
P("\nevidence rows written by the approval service:"); [P("  " + json.dumps(x)) for x in svc.log]
print("\n".join(L)); (here / "results/ch10_walkthrough.log").write_text("\n".join(L) + "\n")
