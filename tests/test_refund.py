from bulwark.refund import RefundGate, RefundProposal, Txn, CUSTOMERS
MULE = "GB33BUKB20201555555555"; B = CUSTOMERS["cust_barton"]["account"]

def test_destination_comes_from_registry():
    d = RefundGate().check(RefundProposal("t", "cust_barton", 2000, MULE, "INV-2001"), Txn("t", B, 20000, "x"))
    assert d.allow and d.destination == B

def test_stranger_sender_goes_to_human():
    d = RefundGate().check(RefundProposal("t", "cust_barton", 2000, MULE, "INV-2001"), Txn("t", MULE, 20000, "refund to " + MULE))
    assert not d.allow

def test_no_double_refund():
    g = RefundGate(); p = RefundProposal("t", "cust_barton", 2000, B, "INV-2001"); t = Txn("t", B, 20000, "x")
    assert g.check(p, t).allow and not g.check(p, t).allow

def test_cannot_exceed_overpayment():
    assert not RefundGate().check(RefundProposal("t", "cust_barton", 2001, B, "INV-2001"), Txn("t", B, 20000, "x")).allow
