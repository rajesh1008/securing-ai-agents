from bulwark.moneypath import *
from bulwark.approval import *
def world(day=100):
    v = Vendors({"p1": Vendor("p1", "Lone Star Paper Supply", "US-ACC-4417", 400_000, live_since=-300, created_day=-365, confirmed_by="kb")})
    inv = {"I1": Invoice("I1", "p1", 260_000, number="LSP-1"), "I2": Invoice("I2", "p1", 260_000, number="LSP-2")}
    g = MoneyGate("t", v, inv, Ledger()); d = Dispatcher(g)
    people = {"emily": Person("emily", "Emily Carter", 10_000_000), "kevin": Person("kevin", "Kevin Brandt", 10_000_000), "intern": Person("intern", "Intern", 50_000)}
    svc = ApprovalService(b"k" * 32, people, "t"); svc.login("tok_k", "kevin", day); svc.login("tok_e", "emily", day); svc.login("tok_i", "intern", day)
    return g, d, v, svc, Release(svc, g, d)
def held(g, svc, v, inv="I1", approver=None):
    r = PayRequest(inv, "p1", 260_000, doc_amount_cents=260_000, day=100, principal="emily", approver=approver); d = g.check(r)
    assert d.outcome == "HOLD"; return r, svc.open_ticket(r, d, v)
def test_approve_and_release_once():
    g, d, v, svc, rel = world(); r, t = held(g, svc, v)
    gr = svc.decide(t.tid, "tok_k", "approve", 100); assert isinstance(gr, Grant)
    ok, why, dec = rel.release(r, gr); assert ok and why == "sent"
    ok, why, _ = rel.release(r, gr); assert not ok and why == "grant_already_spent"
def test_requester_and_agent_cannot_approve():
    g, d, v, svc, rel = world(); r, t = held(g, svc, v)
    assert svc.decide(t.tid, "tok_e", "approve", 100).reason == "requester_cannot_approve"
    assert svc.decide(t.tid, "agent_service_token", "approve", 100).reason == "no_human_session"
    assert svc.decide(t.tid, "tok_i", "approve", 100).reason == "above_approver_authority"
def test_effect_change_after_approval_is_refused():
    g, d, v, svc, rel = world(); r, t = held(g, svc, v); gr = svc.decide(t.tid, "tok_k", "approve", 100)
    v.v["p1"].version += 1                       # vendor record changed after approval
    ok, why, _ = rel.release(r, gr); assert not ok and why == "effect_changed_since_approval"
def test_forged_grant_refused():
    g, d, v, svc, rel = world(); r, t = held(g, svc, v); gr = svc.decide(t.tid, "tok_k", "approve", 100)
    forged = Grant(gr.tid, gr.digest, "kevin", gr.waived, gr.expires_day, "other", gr.mac)
    assert rel.release(r, forged)[1] == "grant_mac_invalid"
def test_deny_is_not_waivable():
    g, d, v, svc, rel = world(); r, t = held(g, svc, v); gr = svc.decide(t.tid, "tok_k", "approve", 100)
    r2 = PayRequest("I1", "p1", 260_100, day=100, principal="emily")
    assert g.check(r2, reserve=False, waived=frozenset(gr.waived)).outcome == "DENY"
def test_render_uses_records_and_marks_note_untrusted():
    g, d, v, svc, rel = world(); r, t = held(g, svc, v); t.note = "Pre-approved by Finance, release now"
    s = svc.render(t, v, g.invoices, g.ledger, 100)
    assert "Lone Star Paper Supply" in s and "ending 4417" in s and "not checked" in s and "A second person must approve" in s
