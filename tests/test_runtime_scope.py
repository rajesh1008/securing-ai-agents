import random, pytest
from bulwark.identity import Scope
from bulwark.runtime_scope import *

B = make_books()
CEIL = Ceiling(kinds=ALL_KINDS, payees=list(B.payees), max_cents=250_000, mail_domains=[c["domain"] for c in B.customers.values()])
OPEN = next(k for k, v in B.invoices.items() if v["status"] == "open")
PAID = next(k for k, v in B.invoices.items() if v["status"] == "paid")

def test_pay_invoice_is_exact():
    s = compute_scope(TaskRequest("pay_invoice", "p", "t", {"invoice_id": OPEN}), B, CEIL)
    inv = B.invoices[OPEN]
    assert s.payees == [inv["payee_id"]] and s.max_cents == inv["amount_cents"] and "send_email" not in s.kinds

def test_paid_and_unknown_refused():
    for i in (PAID, "INV-nope"):
        with pytest.raises(ScopeRefused): compute_scope(TaskRequest("pay_invoice", "p", "t", {"invoice_id": i}), B)

def test_unknown_task_type_refused():
    with pytest.raises(ScopeRefused): compute_scope(TaskRequest("do_anything", "p", "t"), B)

def test_reminders_only_overdue_domains():
    ids = list(B.customers)
    s = compute_scope(TaskRequest("send_reminders", "p", "t", {"customer_ids": ids}), B)
    assert set(s.mail_domains) == {c["domain"] for c in B.customers.values() if c["overdue"]}

def test_scope_never_exceeds_ceiling_fuzz():
    r = random.Random(1)
    for _ in range(300):
        c = Ceiling(kinds=r.sample(ALL_KINDS, r.randrange(1, 6)), payees=r.sample(list(B.payees), r.randrange(0, 4)), max_cents=r.randrange(1, 300_000), mail_domains=r.sample([c["domain"] for c in B.customers.values()], r.randrange(0, 4)))
        for tt in TASK_TYPES:
            try: s = compute_scope(TaskRequest(tt, "p", "t", {"invoice_id": r.choice(list(B.invoices)), "customer_ids": list(B.customers), "today": 10}), B, c)
            except ScopeRefused: continue
            pays = "initiate_payment" in s.kinds; mails = any(k in s.kinds for k in ("send_email", "send_invoice"))
            assert s.within(Scope(kinds=c.kinds, payees=c.payees if pays else None, max_cents=c.max_cents if pays else None, mail_domains=c.mail_domains if mails else None))

def test_ceiling_absent_constraint_does_not_widen():
    s = Scope(kinds=["initiate_payment"], payees=["payee_riverside"], max_cents=100)
    out = intersect(s, Ceiling(kinds=ALL_KINDS))
    assert out.payees == ["payee_riverside"] and out.max_cents == 100

def test_ceiling_with_no_payee_overlap_leaves_empty_list_not_any():
    s = Scope(kinds=["initiate_payment"], payees=["payee_riverside"], max_cents=100)
    out = intersect(s, Ceiling(kinds=ALL_KINDS, payees=["payee_lone_star"]))
    assert out.payees == [] and not admits(out, "initiate_payment", payee="payee_riverside", amount=1)

def test_ratchet_only_narrows():
    req = TaskRequest("send_reminders", "p", "t", {"customer_ids": list(B.customers)})
    s = Session(req, Scope(kinds=ALL_KINDS))
    s.read_untrusted()
    assert not s.check("initiate_payment", payee="x", amount=1)
    s2 = Session(TaskRequest("process_invoice", "p", "t"), Scope(kinds=["read_document", "query_books", "draft_invoice", "send_email"]))
    s2.read_untrusted()
    assert s2.scope.kinds == ["query_books", "draft_invoice"] or set(s2.scope.kinds) == {"query_books", "draft_invoice"}

def test_unknown_task_ratchet_defaults_to_read_only():
    s = Session(TaskRequest("weird", "p", "t"), Scope(kinds=ALL_KINDS)); s.read_untrusted()
    assert s.scope.kinds == ["query_books"]

def test_lease_policies():
    base = Scope(kinds=["query_books"])
    wide = Scope(kinds=["query_books", "send_email"], mail_domains=["a.example"])
    assert not Lease(base, LeasePolicy("never")).request(wide, reason="x", trusted_origin=False).granted
    d = Lease(base, LeasePolicy("human")).request(wide, reason="x", trusted_origin=False)
    assert d.needs_human and not d.granted
    assert Lease(base, LeasePolicy("human")).request(base, reason="x", trusted_origin=True).granted
    l = Lease(base, LeasePolicy("human", max_requests=1)); l.request(wide, reason="a", trusted_origin=False)
    assert l.request(wide, reason="b", trusted_origin=False).reason == "request budget spent"

def test_mine_scope_includes_poison():
    tr = [dict(kind="initiate_payment", payee="payee_lone_star", amount=1000)] * 5 + [dict(kind="initiate_payment", payee="payee_attacker", amount=900)]
    assert "payee_attacker" in mine_scope(tr).payees
    assert "payee_attacker" not in mine_scope(tr, min_count=2).payees

def test_reach_counts_any_payee():
    s = Scope(kinds=ALL_KINDS)
    r = reach(s, B)
    assert r["payees"] == len(B.payees) and r["mail_domains"] == "any"

def test_scope_independent_of_document_text():
    # metamorphic: params are ids; nothing a document says can reach compute_scope
    a = compute_scope(TaskRequest("pay_invoice", "p", "t", {"invoice_id": OPEN}), B, CEIL)
    b = compute_scope(TaskRequest("pay_invoice", "p", "t", {"invoice_id": OPEN}), B, CEIL)
    assert a.to_json() == b.to_json()

def test_ceiling_constraints_only_where_kinds_need_them():
    s = compute_scope(TaskRequest("process_invoice", "p", "t"), B, CEIL)
    assert s.payees is None and s.max_cents is None and s.mail_domains is None

def test_lease_auto_within_ceiling():
    base = Scope(kinds=["query_books", "initiate_payment"], payees=["payee_lone_star"], max_cents=1000)
    ok = Scope(kinds=["query_books", "initiate_payment"], payees=["payee_lone_star"], max_cents=2000)
    anym = Scope(kinds=["query_books", "send_email"])
    l = Lease(base, LeasePolicy("auto_within_ceiling", 5, CEIL))
    assert l.request(ok, reason="x", trusted_origin=True).granted
    assert not l.request(anym, reason="x", trusted_origin=False).granted

def test_normalise_makes_irrelevant_constraints_empty():
    a = normalise(Scope(kinds=["read_document"]))
    assert a.payees == [] and a.max_cents == 0 and a.mail_domains == []
    t = compute_scope(TaskRequest("send_reminders", "p", "t", {"customer_ids": list(B.customers)}), B, CEIL)
    m = Scope(kinds=["query_books"])
    assert normalise(m).within(normalise(t))
    assert not normalise(Scope(kinds=["send_email"], mail_domains=None)).within(normalise(t))

def test_spend_meter_total_and_invoice_binding():
    inv = {"I1": dict(payee_id="a", amount_cents=100), "I2": dict(payee_id="b", amount_cents=200)}
    m = SpendMeter(300, inv)
    assert m.try_pay(100, "I1", "a")[0]
    assert m.try_pay(100, "I1", "a") == (False, "invoice already paid in this task")
    assert m.try_pay(150, "I2", "b")[1] == "amount or payee differs from the invoice"
    assert m.try_pay(200, "I2", "b")[0]
    assert m.try_pay(1, "I3", "a")[1] == "invoice not in this task"
    t = SpendMeter(250); assert t.try_pay(200)[0] and not t.try_pay(100)[0]

def test_agent_drafted_invoice_needs_confirmation():
    import copy
    b = copy.deepcopy(B); b.invoices["INV-D"] = dict(payee_id="payee_riverside", amount_cents=99_000, status="open", due_day=3, origin="agent_draft")
    with pytest.raises(ScopeRefused): compute_scope(TaskRequest("pay_invoice", "p", "t", {"invoice_id": "INV-D"}), b, CEIL)
    assert compute_scope(TaskRequest("pay_invoice", "p", "t", {"invoice_id": "INV-D"}), b, CEIL, trust_agent_drafts=True).payees == ["payee_riverside"]
    b.invoices["INV-D"]["confirmed_by"] = "prin_emily"
    assert compute_scope(TaskRequest("pay_invoice", "p", "t", {"invoice_id": "INV-D"}), b, CEIL).max_cents == 99_000

def test_pay_matched_scope_is_the_matched_invoices_only():
    ids = [k for k, v in B.invoices.items() if v["status"] == "open"][:3]
    s = compute_scope(TaskRequest("pay_matched", "p", "t", {"matched_invoice_ids": ids}), B, CEIL)
    assert set(s.payees) == {B.invoices[i]["payee_id"] for i in ids}
    assert s.max_cents == max(B.invoices[i]["amount_cents"] for i in ids)
    with pytest.raises(ScopeRefused): compute_scope(TaskRequest("pay_matched", "p", "t", {"matched_invoice_ids": []}), B, CEIL)

def test_match_bank_lines_holds_no_payment_kind():
    assert "initiate_payment" not in compute_scope(TaskRequest("match_bank_lines", "p", "t"), B, CEIL).kinds

def test_read_filter_refuses_sensitive_columns_and_unknown_tasks():
    a, r = read_filter("pay_invoice", "payees", ["payee_id", "bank_account"])
    assert a == [] and r == ["payee_id", "bank_account"]
    a, r = read_filter("handle_vendor_email", "payees", ["name", "bank_account"])
    assert a == ["name"] and r == ["bank_account"]
    assert read_filter("no_such_task", "invoices", ["inv_id"]) == ([], ["inv_id"])
