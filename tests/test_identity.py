import json, pytest
from bulwark.models import ActionProposal, ActionKind
from bulwark.identity import Issuer, Verifier, Scope, SupportGrant, IssuanceRefused, b64e, b64d
WL = "spiffe://x/quill"
def mk():
    class C:
        t = 1000.0
        def __call__(self): return self.t
    c = C(); i = Issuer(clock=c); v = Verifier(i.public_keys(), lambda k: i.status[k], clock=c)
    return c, i, v
def pay(amt=100, payee="p1"):
    return ActionProposal(kind=ActionKind.INITIATE_PAYMENT, business_id="b", principal_id="u", amount_cents=amt, payee_id=payee)
SC = Scope(kinds=["initiate_payment"], payees=["p1"], max_cents=500)
def tok(i, **kw):
    d = dict(principal="u", tenant="b", workload=WL, task_id="t", scope=SC); d.update(kw); return i.issue(**d)
def test_ok_then_replay():
    c, i, v = mk(); t = tok(i)
    assert v.verify(t, pay(), caller_workload=WL).allow
    assert not v.verify(t, pay(), caller_workload=WL).allow
def test_scope_and_tamper():
    c, i, v = mk(); t = tok(i)
    assert not v.verify(t, pay(600), caller_workload=WL).allow
    h, cl, s = t.split("."); d = json.loads(b64d(cl)); d["scope"]["max_cents"] = 10**6
    forged = h + "." + b64e(json.dumps(d, sort_keys=True).encode()) + "." + s
    assert v.verify(forged, pay(600), caller_workload=WL).reasons == ["bad signature"]
def test_expiry_and_workload():
    c, i, v = mk(); t = tok(i, ttl=10)
    assert not v.verify(t, pay(), caller_workload="other").allow
    c.t += 11
    assert "expired" in v.verify(t, pay(), caller_workload=WL).reasons
def test_derive_attenuates():
    c, i, v = mk(); t = tok(i, ttl=600)
    with pytest.raises(IssuanceRefused): i.derive(t, scope=Scope(kinds=["initiate_payment"], payees=["p1"], max_cents=900), workload=WL, ttl=10)
    assert i.derive(t, scope=Scope(kinds=["initiate_payment"], payees=["p1"], max_cents=100), workload=WL, ttl=10)
def test_support_needs_grant():
    c, i, v = mk()
    with pytest.raises(IssuanceRefused): tok(i, actor="s1", scope=Scope(kinds=["read_document"]))
    i.grants.append(SupportGrant("s1", "b", "u", c.t + 100))
    assert tok(i, actor="s1", scope=Scope(kinds=["read_document"]))
    with pytest.raises(IssuanceRefused): tok(i, actor="s1", scope=Scope(kinds=["initiate_payment"], payees=["p1"], max_cents=1))

def test_shared_use_store_enforces_budget(tmp_path):
    from bulwark.identity import SqliteUseStore
    s = SqliteUseStore(str(tmp_path / "u.db"))
    assert s.consume("j1", 2) and s.consume("j1", 2) and not s.consume("j1", 2)
    assert s.consume("j2", 1) and not s.consume("j2", 1)
