#!/usr/bin/env python3
"""Chapter 10, lab 3: who may approve, and what a grant is good for. Sixteen cases against ApprovalService and Release. No model."""
import sys, json, copy
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
from bulwark.moneypath import *
from bulwark.approval import *
def world(kind="m8"):
    v = Vendors({"p": Vendor("p", "Lone Star Paper Supply", "US-ACC-4417", 1_000_000, live_since=-300, created_day=-365, confirmed_by="kb")})
    inv = {"I1": Invoice("I1", "p", 260_000, number="LSP-1"), "I2": Invoice("I2", "p", 260_000, number="LSP-2")}
    if kind == "m4": v.v["p"].account, v.v["p"].live_since = "US-ACC-9902", 98
    g = MoneyGate("t", v, inv, Ledger(), tenant_daily_cap=10**9, payee_daily_cents=10**9); disp = Dispatcher(g)
    people = {"emily": Person("emily", "Emily Carter (owner, requester)", 10**8), "kevin": Person("kevin", "Kevin Brandt", 10**8, can_edit_vendors=True), "nina": Person("nina", "Nina Cole (bookkeeper)", 100_000), "sam": Person("sam", "Sam (second approver)", 10**8)}
    svc = ApprovalService(b"s" * 32, people, "t")
    for tok, pid in (("t_emily", "emily"), ("t_emily2", "emily"), ("t_kevin", "kevin"), ("t_nina", "nina"), ("t_sam", "sam")): svc.login(tok, pid, 100)
    r = PayRequest("I1", "p", 260_000, doc_amount_cents=260_000, day=100, principal="emily"); d = g.check(r, reserve=False)
    t = svc.open_ticket(r, d, v); return g, v, svc, Release(svc, g, disp), r, t
rows = []
def case(n, desc, fn, expect):
    out = fn(); rows.append((n, desc, out, expect, "ok" if out.startswith(expect) else "MISMATCH"))
def dec(svc, t, tok, day=100, cb=False): x = svc.decide(t.tid, tok, "approve", day, cb); return x if isinstance(x, Grant) else x
g, v, svc, rel, r, t = world(); case(1, "requester approves own payment", lambda: dec(svc, t, "t_emily").reason, "requester_cannot_approve")
g, v, svc, rel, r, t = world(); case(2, "requester approves from a second session", lambda: dec(svc, t, "t_emily2").reason, "requester_cannot_approve")
g, v, svc, rel, r, t = world(); case(3, "assistant's service credential tries to approve", lambda: dec(svc, t, "svc_quill_token").reason, "no_human_session")
g, v, svc, rel, r, t = world(); case(4, "approval 'sent' by email reply", lambda: dec(svc, t, "reply-to:kevin@example.com").reason, "no_human_session")
g, v, svc, rel, r, t = world(); case(5, "approver whose limit is $1,000", lambda: dec(svc, t, "t_nina").reason, "above_approver_authority")
g, v, svc, rel, r, t = world(); case(6, "approver session expired the next day", lambda: dec(svc, t, "t_kevin", day=102).reason, "session_expired")
g, v, svc, rel, r, t = world(); case(7, "ticket expired after 3 days", lambda: (svc.login("late", "kevin", 104), dec(svc, t, "late", day=104).reason)[1], "ticket_expired")
g, v, svc, rel, r, t = world(); case(8, "second person approves a dual-control hold", lambda: "grant" if isinstance(dec(svc, t, "t_kevin"), Grant) else "no", "grant")
g, v, svc, rel, r, t = world("m4"); svc.pending_change_authors["p"] = "kevin"; case(9, "person who requested the bank change approves the payment to it", lambda: dec(svc, t, "t_kevin", cb=True).reason, "author_of_vendor_change")
g, v, svc, rel, r, t = world("m4"); case(10, "unseasoned account, approver did not call the vendor", lambda: dec(svc, t, "t_sam").reason, "callback_required")
g, v, svc, rel, r, t = world("m4"); case(11, "unseasoned account, call-back done by a second person", lambda: "grant" if isinstance(dec(svc, t, "t_sam", cb=True), Grant) else "no", "grant")
g, v, svc, rel, r, t = world(); gr = dec(svc, t, "t_kevin"); forged = Grant(gr.tid, gr.digest, "sam", gr.waived, gr.expires_day, gr.nonce, gr.mac)
case(12, "grant with the approver field edited", lambda: rel.release(r, forged)[1], "grant_mac_invalid")
g, v, svc, rel, r, t = world(); gr = dec(svc, t, "t_kevin"); other = Grant(gr.tid, "0" * 64, gr.approver, gr.waived, gr.expires_day, gr.nonce, gr.mac)
case(13, "grant with the digest edited", lambda: rel.release(r, other)[1], "grant_mac_invalid")
g, v, svc, rel, r, t = world(); gr = dec(svc, t, "t_kevin"); r_late = PayRequest(r.invoice_id, r.payee_id, r.amount_cents, doc_amount_cents=r.doc_amount_cents, day=102, principal="emily")
case(14, "grant presented two days later", lambda: rel.release(r_late, gr)[1], "grant_expired")
g, v, svc, rel, r, t = world(); gr = dec(svc, t, "t_kevin"); first = rel.release(r, gr)[1]
case(15, "the same grant spent a second time", lambda: rel.release(r, gr)[1], "grant_already_spent")
g, v, svc, rel, r, t = world(); gr = dec(svc, t, "t_kevin"); svc2 = ApprovalService(b"s" * 32, svc.people, "other_tenant"); rel2 = Release(svc2, g, Dispatcher(g))
case(16, "grant presented to another tenant's service (same key by mistake)", lambda: rel2.release(r, gr)[1], "effect_changed_since_approval")
L = [f"{'#':>2s} {'case':66s} {'result':32s} {'expected':28s}"]
for n, desc, out, exp, st in rows: L.append(f"{n:>2d} {desc:66s} {out:32s} {exp:28s} {st}")
L.append(f"\nfirst release in case 15 (before the replay): {first}")
L.append(f"mismatches: {sum(1 for r_ in rows if r_[4] != 'ok')} of {len(rows)}")
print("\n".join(L)); (here / "results/ch10_authority_cases.log").write_text("\n".join(L) + "\n")
