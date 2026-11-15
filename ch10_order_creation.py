#!/usr/bin/env python3
"""Chapter 10, lab 5: creating a standing order is a held action. Policy limits and approval rules for the proposal, then a
seeded sweep of 400 proposals (300 from the assistant's side with hostile shapes, 100 ordinary from the owner). No model."""
import sys, random
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
from bulwark.approval import ApprovalService, Person, Refusal, StandingOrder
from bulwark.orders import OrderService, OrderProposal, MAX_CAP_CENTS
def world():
    people = {"emily": Person("emily", "Emily", 10**8), "kevin": Person("kevin", "Kevin", 10**8), "nina": Person("nina", "Nina", 100_000)}
    ap = ApprovalService(b"k" * 32, people, "t")
    for tok, pid in (("t_emily", "emily"), ("t_kevin", "kevin"), ("t_nina", "nina")): ap.login(tok, pid, 100)
    return ap, OrderService(ap, {"p": "Lone Star Paper Supply", "q": "Other Vendor"})
rows = []
def case(n, desc, out, exp): rows.append((n, desc, out, exp, "ok" if out == exp else "MISMATCH"))
def name(x): return x.reason if isinstance(x, Refusal) else ("order_active" if isinstance(x, StandingOrder) else ("proposed" if isinstance(x, str) else str(x)))
good = OrderProposal("p", 260_000, 90, 260_000, 300, "assistant")
ap, os_ = world(); d = os_.propose(good, 100); case(1, "exact order proposed by the assistant", name(d), "proposed")
case(2, "approved by Kevin (owner side, not the proposer)", name(os_.decide(d, good, "t_kevin", 100)), "order_active")
ap, os_ = world(); d = os_.propose(good, 100); case(3, "assistant's own credential tries to approve", name(os_.decide(d, good, "svc_quill_token", 100)), "no_human_session")
ap, os_ = world(); d = os_.propose(OrderProposal("p", 260_000, 90, 260_000, 300, "kevin"), 100); pk = OrderProposal("p", 260_000, 90, 260_000, 300, "kevin"); case(4, "the person who proposed it approves it", name(os_.decide(d, pk, "t_kevin", 100)), "proposer_cannot_approve")
ap, os_ = world(); d = os_.propose(good, 100); case(5, "approver whose limit is $1,000", name(os_.decide(d, good, "t_nina", 100)), "above_approver_authority")
ap, os_ = world(); d = os_.propose(good, 100); wider = OrderProposal("p", None, None, 260_000, 300, "assistant"); case(6, "the order is widened after the screen was shown", name(os_.decide(d, wider, "t_kevin", 100)), "proposal_changed_since_shown")
ap, os_ = world(); d = os_.propose(good, 100); case(7, "approver session expired", name(os_.decide(d, good, "t_kevin", 102)), "session_expired")
ap, os_ = world(); case(8, "payee-wide order (no amount, no cadence)", name(os_.propose(OrderProposal("p", None, None, 200_000, 300, "assistant"), 100)), "scope_too_wide")
case(9, "cap of $6,000", name(os_.propose(OrderProposal("p", None, 30, 600_000, 300, "assistant"), 100)), "cap_above_policy")
case(10, "expiry in 900 days", name(os_.propose(OrderProposal("p", 100, 30, 100, 1000, "assistant"), 100)), "expiry_above_policy")
case(11, "payee not in the vendor master", name(os_.propose(OrderProposal("zz", 100, 30, 100, 200, "assistant"), 100)), "unknown_payee")
ap, os_ = world(); d = os_.propose(good, 100); os_.decide(d, good, "t_kevin", 100); case(12, "the same digest decided a second time", name(os_.decide(d, good, "t_emily", 100)), "no_pending_proposal")
ap, os_ = world(); d = os_.propose(good, 100); case(13, "screen shows the fields and the limit", "ok" if all(s in os_.render(good) for s in ("exactly $2,600.00", "every 90 days", "Every other hold still applies")) else "no", "ok")
L = [f"{'#':>2s} {'case':58s} {'result':32s} {'expected':30s}"]
for n, desc, out, exp, st in rows: L.append(f"{n:>2d} {desc:58s} {out:32s} {exp:30s} {st}")
L.append(f"mismatches: {sum(1 for r in rows if r[4] != 'ok')} of {len(rows)}")
# sweep
rng = random.Random(1010); ap, os_ = world(); outcome = {}; activated_without_person = 0; broad_active = 0
def tally(k): outcome[k] = outcome.get(k, 0) + 1
for i in range(300):
    shape = rng.choice(["payee_wide", "big_cap", "far_expiry", "wide_amount_cap", "cadence_only_big"])
    amt = None if shape in ("payee_wide", "wide_amount_cap") else rng.choice([100_000, 260_000])
    ev = rng.choice([None, 30, 90])
    if shape == "payee_wide": ev = None
    cap = {"payee_wide": 200_000, "big_cap": 900_000, "far_expiry": 260_000, "wide_amount_cap": 400_000, "cadence_only_big": 450_000}[shape]
    exp = 100 + (900 if shape == "far_expiry" else 200)
    r = os_.propose(OrderProposal("p", amt, ev, cap, exp, "assistant"), 100)
    if isinstance(r, str):
        o = os_.decide(r, os_.pending[r], "svc_quill_token", 100)
        tally("proposed_then_refused_agent_approval:" + name(o))
    else: tally("refused_at_proposal:" + r.reason)
    activated_without_person += len(os_.active)
for i in range(100):
    p = OrderProposal("p", rng.choice([100_000, 260_000]), 90, 260_000, 300 + i, "emily"); r = os_.propose(p, 100)
    o = os_.decide(r, p, "t_kevin", 100); tally("owner_ordinary:" + name(o))
L.append("\nsweep (seed 1010): 300 hostile-shaped proposals from the assistant, then 100 ordinary owner proposals approved by a second person")
for k in sorted(outcome): L.append(f"  {k:70s} {outcome[k]:4d}")
L.append(f"orders active after the 300 assistant proposals: {activated_without_person}")
L.append(f"orders active at the end: {len(os_.active)}")
print("\n".join(L)); (here / "results/ch10_order_creation.log").write_text("\n".join(L) + "\n")
