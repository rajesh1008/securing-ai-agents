import pytest
from bulwark.models import ActionProposal, ActionKind, Principal, AgentIdentity
from bulwark.policy_v02 import BulwarkGateV02
from bulwark.principles import Mediator, Tool, MediationError, SeparationOfDuties, Approval
P = Principal(principal_id='prin_emily', display_name='E', business_id='biz_hcb'); A = AgentIdentity()
def prop(kind, **kw): return ActionProposal(kind=kind, business_id='biz_hcb', principal_id='prin_emily', **kw)
def mk(fail_mode="closed", gate=None):
    calls = []
    tools = {ActionKind.SEND_EMAIL: Tool("send_email", lambda p: calls.append(p.recipient_email) or "sent")}
    return Mediator(gate or BulwarkGateV02(), tools, fail_mode), calls
class Boom:
    def check(self, *a): raise TimeoutError("policy service down")
def test_tool_refuses_direct_call():
    m, calls = mk()
    with pytest.raises(MediationError): m.tools[ActionKind.SEND_EMAIL](prop(ActionKind.SEND_EMAIL, recipient_email='x@lonestarpaper.example'))
    assert calls == []
def test_allowed_email_executes():
    m, calls = mk(); r = m.execute(prop(ActionKind.SEND_EMAIL, recipient_email='accounts@lonestarpaper.example'), P, A)
    assert r.executed and calls == ['accounts@lonestarpaper.example']
def test_lookalike_denied():
    m, calls = mk(); assert not m.execute(prop(ActionKind.SEND_EMAIL, recipient_email='accounts@lonestarpapers.com'), P, A).executed and calls == []
def test_gate_error_fails_closed():
    m, calls = mk("closed", Boom()); r = m.execute(prop(ActionKind.SEND_EMAIL, recipient_email='accounts@lonestarpapers.com'), P, A)
    assert not r.executed and r.gate_error and calls == []
def test_gate_error_fails_open_when_configured():
    m, calls = mk("open", Boom()); assert m.execute(prop(ActionKind.SEND_EMAIL, recipient_email='accounts@lonestarpapers.com'), P, A).executed
def test_unregistered_kind_does_nothing():
    m, _ = mk(); assert not m.execute(prop(ActionKind.QUERY_BOOKS), P, A).executed
def test_separation_of_duties():
    s = SeparationOfDuties(); big = prop(ActionKind.INITIATE_PAYMENT, payee_id='payee_lone_star', amount_cents=150_000)
    assert not s.check(big, None)[0]
    assert not s.check(big, Approval('prin_emily'))[0]
    assert not s.check(big, Approval('quill', approver_is_agent=True))[0]
    assert s.check(big, Approval('prin_nina'))[0]
    assert s.check(prop(ActionKind.INITIATE_PAYMENT, payee_id='payee_lone_star', amount_cents=42_000), None)[0]
