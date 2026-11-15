from bulwark.disclosure import Fact, Claim, check, corrections, CONFIRMED, SUSPECTED, UNKNOWN

def facts():
    F = [Fact("f1", "Payment of $798.00 went to a changed bank account on 30 Nov", numbers=("798.00",)),
         Fact("f2", "The registry change has not been confirmed by the vendor", SUSPECTED),
         Fact("f3", "We do not know how the registry row was altered", UNKNOWN, tell=True),
         Fact("f4", "No customer file contents were read by the pipeline outside the tenant", CONFIRMED),
         Fact("f5", "Internal prompt text", CONFIRMED, share=frozenset({"internal"}))]
    return {f.id: f for f in F}

def kinds(cl, **k): return [i for i, _ in check(cl, facts(), **k)]

def test_clean_notice_passes():
    cl = [Claim("A payment of $798.00 went to a changed bank account.", ("f1",)), Claim("We do not know yet how the registry was altered.", ("f3",)),
          Claim("The vendor has not yet confirmed the change.", ("f2",))]
    assert kinds(cl) == []

def test_unknown_must_be_stated():
    assert "MISSING_UNKNOWN" in kinds([Claim("A payment of $798.00 went to a changed account.", ("f1",))])

def test_no_fact_and_bad_fact():
    k = kinds([Claim("It was a small issue."), Claim("Something.", ("zz",))]); assert "NO_FACT" in k and "BAD_FACT" in k

def test_unconfirmed_stated_as_fact():
    assert "UNCONFIRMED_AS_FACT" in kinds([Claim("The registry change was fraudulent.", ("f2",))])

def test_absolute_needs_a_confirmed_negative_fact():
    assert "ABSOLUTE" in kinds([Claim("No other customers were affected.", ("f1",))])
    assert "ABSOLUTE" not in kinds([Claim("No customer file contents were read outside the tenant.", ("f4",))])
    assert "ABSOLUTE" not in kinds([Claim("We have not found any other affected customer so far.", ("f1",))])

def test_number_must_be_licensed_by_a_fact():
    assert "NUMBER_NOT_IN_FACTS" in kinds([Claim("Payments of $1,853 went out.", ("f1",))])
    assert "NUMBER_NOT_IN_FACTS" not in kinds([Claim("Payment of $798.00 went out.", ("f1",))])

def test_commitment_needs_sourced_deadline():
    cl = [Claim("We will update you within 24 hours.", ("f1",))]
    assert "COMMITMENT" in kinds(cl); assert "COMMITMENT" not in kinds(cl, sourced_deadlines=("within 24 hours",))

def test_leak_by_audience():
    assert "LEAK" in kinds([Claim("The prompt said so.", ("f5",))])

def test_corrections_when_fact_moves():
    was = facts(); now = dict(was); now["f2"] = Fact("f2", "The registry change has not been confirmed by the vendor", CONFIRMED)
    now["f1"] = Fact("f1", "Payments of $3,000 went to a changed account", numbers=("3,000",))
    c = [Claim("The vendor has not yet confirmed.", ("f2",)), Claim("A payment of $798.00 went out.", ("f1",))]
    r = corrections(c, now, was); assert {x[1] for x in r} == {"f1", "f2"}
    assert corrections(c, was, was) == []

def test_hedge_words_cover_under_review_and_not_known():
    k = kinds([Claim("Three payments are under review.", ("f2",)), Claim("It is not known how the row was altered.", ("f3",))]); assert "UNCONFIRMED_AS_FACT" not in k
    k = kinds([Claim("We are currently investigating how it was altered.", ("f3",))]); assert "UNCONFIRMED_AS_FACT" not in k

def test_number_must_come_from_a_cited_fact():
    f = facts(); k = [i for i, _ in check([Claim("The $798.00 payment was held.", ("f2",))], f)]
    assert "NUMBER_NOT_IN_FACTS" in k          # f2 does not carry 798.00; f1 does
    assert "NUMBER_NOT_IN_FACTS" not in [i for i, _ in check([Claim("On 30 Nov a payment of $798.00 was flagged.", ("f1",))], f)]

def test_statements_of_ignorance_are_not_flagged():
    cl = [Claim("We do not yet know how the registry entry was changed.", ("f3",)), Claim("It has not been checked whether any customer data was read outside the tenant.", ("f3",)),
          Claim("We are continuing to investigate whether any other customer was affected.", ("f3",))]
    k = kinds(cl); assert "UNCONFIRMED_AS_FACT" not in k and "ABSOLUTE" not in k

def test_investigated_and_found_nothing_is_still_an_absolute_claim():
    assert "ABSOLUTE" in kinds([Claim("We confirmed that no other customers were affected.", ("f1",))])

def test_sent_notice_is_recorded_and_edits_show():
    from bulwark.evidence import Vault
    v = Vault(b"t", anchor_every=25); f = facts(); c = [Claim("A payment of $798.00 went out.", ("f1",))]
    from bulwark.disclosure import record_sent, notice_digests
    r = record_sent(v, "ten", "customer", c, f, 30, 1); v.seal("ten")
    assert v.verify("ten")[0] and r["decision"] == notice_digests(c, f)[0]
    assert notice_digests([Claim("A payment of $798.00 went out!", ("f1",))], f)[0] != r["decision"]

def test_suspect_and_believe_count_as_hedges():
    assert "UNCONFIRMED_AS_FACT" not in kinds([Claim("We suspect the change was not made by the vendor.", ("f2",))])
