"""Chapter 10: standing-order creation is a held action (bulwark/orders.py)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from bulwark.approval import ApprovalService, Person, Refusal, StandingOrder
from bulwark.orders import OrderService, OrderProposal

def world():
    people = {"emily": Person("emily", "Emily", 10**8), "kevin": Person("kevin", "Kevin", 10**8), "nina": Person("nina", "Nina", 100_000)}
    ap = ApprovalService(b"k" * 32, people, "t")
    for tok, pid in (("t_emily", "emily"), ("t_kevin", "kevin"), ("t_nina", "nina")): ap.login(tok, pid, 100)
    return OrderService(ap, {"p": "Lone Star Paper Supply"})

GOOD = OrderProposal("p", 260_000, 90, 260_000, 300, "assistant")

def test_second_person_activates_exact_order():
    s = world(); d = s.propose(GOOD, 100); o = s.decide(d, GOOD, "t_kevin", 100)
    assert isinstance(o, StandingOrder) and o.created_by == "kevin" and o.amount_cents == 260_000 and s.active == [o]

def test_agent_credential_cannot_approve():
    s = world(); d = s.propose(GOOD, 100)
    assert s.decide(d, GOOD, "svc_token", 100).reason == "no_human_session" and not s.active

def test_proposer_and_low_authority_refused():
    s = world(); mine = OrderProposal("p", 260_000, 90, 260_000, 300, "kevin"); d = s.propose(mine, 100)
    assert s.decide(d, mine, "t_kevin", 100).reason == "proposer_cannot_approve"
    d2 = s.propose(GOOD, 100); assert s.decide(d2, GOOD, "t_nina", 100).reason == "above_approver_authority"

def test_changed_proposal_does_not_activate():
    s = world(); d = s.propose(GOOD, 100); wider = OrderProposal("p", None, 90, 260_000, 300, "assistant")
    assert s.decide(d, wider, "t_kevin", 100).reason == "proposal_changed_since_shown" and not s.active

def test_policy_limits_for_every_proposer():
    s = world()
    assert s.propose(OrderProposal("p", None, None, 100, 200, "emily"), 100).reason == "scope_too_wide"
    assert s.propose(OrderProposal("p", None, 30, 600_000, 200, "emily"), 100).reason == "cap_above_policy"
    assert s.propose(OrderProposal("p", 1, 30, 100, 1000, "emily"), 100).reason == "expiry_above_policy"
    assert s.propose(OrderProposal("zz", 1, 30, 100, 200, "emily"), 100).reason == "unknown_payee"
    assert s.propose(OrderProposal("p", 200, 30, 100, 200, "emily"), 100).reason == "amount_above_cap"

def test_digest_decided_once():
    s = world(); d = s.propose(GOOD, 100); s.decide(d, GOOD, "t_kevin", 100)
    assert s.decide(d, GOOD, "t_emily", 100).reason == "no_pending_proposal"

def test_screen_is_rendered_from_fields():
    s = world(); r = s.render(GOOD)
    assert "exactly $2,600.00" in r and "every 90 days" in r and "Every other hold still applies" in r
