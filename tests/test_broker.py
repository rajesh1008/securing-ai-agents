from bulwark.models import ActionProposal, ActionKind
from bulwark.identity import Issuer, Verifier, Scope
from bulwark.broker import Broker, BankProvider
WL = "spiffe://x/quill"
def setup():
    i = Issuer(); v = Verifier(i.public_keys(), lambda k: i.status[k])
    prov = BankProvider({"b": "rt-secret"})
    return i, Broker(v, prov, {"b": "rt-secret"}), prov
def pp(amt=100, payee="p1"):
    return ActionProposal(kind=ActionKind.INITIATE_PAYMENT, business_id="b", principal_id="u", amount_cents=amt, payee_id=payee)
def tok(i): return i.issue(principal="u", tenant="b", workload=WL, task_id="t", scope=Scope(kinds=["initiate_payment"], payees=["p1"], max_cents=500))
def test_legit_call_executes_once_and_carries_jti():
    i, b, prov = setup(); t = tok(i)
    assert b.pay(t, pp(), caller_workload=WL).allow
    assert not b.pay(t, pp(), caller_workload=WL).allow
    assert len(prov.log) == 1 and prov.log[0]["jti"] and prov.log[0]["via"] == "broker"
def test_outside_scope_never_reaches_provider():
    i, b, prov = setup(); t = tok(i)
    assert not b.pay(t, pp(amt=501), caller_workload=WL).allow
    assert not b.pay(t, pp(payee="p2"), caller_workload=WL).allow
    assert not b.pay(t, pp(), caller_workload="spiffe://x/other").allow
    assert prov.log == []
