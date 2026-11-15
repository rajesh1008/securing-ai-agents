from bulwark.moneypath import *
def mk(day=100):
    v = Vendors({"p1": Vendor("p1", "Lone Star Paper Supply", "ACC1", 250_000, live_since=-300, created_day=-365, confirmed_by="kb")})
    inv = {"I1": Invoice("I1", "p1", 100_000), "I2": Invoice("I2", "p1", 100_000), "I3": Invoice("I3", "p1", 300_000)}
    return MoneyGate("t", v, inv, Ledger()), v
def test_happy_and_second_payment_denied():
    g, v = mk(); r = PayRequest("I1", "p1", 100_000, day=100)
    assert g.check(r).outcome == "ALLOW"
    d = g.check(r); assert d.outcome == "DENY" and "M2_invoice_already_reserved_or_paid" in d.codes
def test_amount_and_limit():
    g, v = mk()
    assert g.check(PayRequest("I1", "p1", 100_100, day=100)).outcome == "DENY"
    assert g.check(PayRequest("I3", "p1", 300_000, day=100, approver="x")).outcome == "DENY"
def test_doc_mismatch_holds():
    g, v = mk(); assert g.check(PayRequest("I1", "p1", 100_000, doc_amount_cents=1_000_000, day=100)).outcome == "HOLD"
def test_bank_change_cannot_move_money_until_confirmed():
    g, v = mk(); v.request_change("p1", "MULE", 100, "email")
    d = g.check(PayRequest("I1", "p1", 100_000, day=100)); assert d.outcome == "HOLD" and d.destination == "ACC1"
    assert not v.confirm_change("p1", 101, "kb", callback_ok=False)
    assert v.confirm_change("p1", 101, "kb", callback_ok=True)
    assert g.check(PayRequest("I1", "p1", 100_000, day=102), reserve=False).outcome == "HOLD"   # seasoning
    assert g.check(PayRequest("I1", "p1", 100_000, day=107), reserve=False).outcome == "ALLOW"
def test_likely_duplicate_and_velocity():
    g, v = mk(); assert g.check(PayRequest("I1", "p1", 100_000, day=100)).outcome == "ALLOW"
    d = g.check(PayRequest("I2", "p1", 100_000, day=101)); assert d.outcome == "HOLD" and any(c.startswith("M7") for c in d.codes)
def test_dispatch_recheck():
    g, v = mk(); r = PayRequest("I1", "p1", 100_000, day=100); d = g.check(r)
    v.request_change("p1", "MULE", 100, "email"); v.confirm_change("p1", 100, "kb", True)
    ok, why = Dispatcher(g).dispatch(r, d); assert not ok and g.ledger.count() == 0
def test_explain_reports_gaps():
    out = explain([dict(step="money_gate", id="e1", text="allowed")]); assert sum(l.startswith("[gap]") for l in out) == 4
