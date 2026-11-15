import json, pytest
from bulwark.schema import *
from bulwark.moneypath import *
def ok(d): return strict_parse(json.dumps(d), PAY_INVOICE)
G = {"invoice_id": "INV-1007", "payee_id": "payee_lone_star", "amount_cents": 141200}
def test_accepts_exact_and_exact_fence():
    assert ok(G).ok
    assert strict_parse("```json\n" + json.dumps(G) + "\n```", PAY_INVOICE).notes == ["unwrapped_fence"]
@pytest.mark.parametrize("raw,code", [
    ('{"invoice_id":"A1","invoice_id":"A2","payee_id":"pp","amount_cents":5}', "duplicate_key"),
    ('{"invoice_id":"A1","payee_id":"pp","amount_cents":5,"account":"X"}', "unexpected_field"),
    ('{"invoice_id":"A1","payee_id":"pp","amount_cents":"5"}', "amount_cents:type_not_integer"),
    ('{"invoice_id":"A1","payee_id":"pp","amount_cents":5.0}', "float_not_allowed"),
    ('{"invoice_id":"A1","payee_id":"pp","amount_cents":true}', "amount_cents:type_not_integer"),
    ('{"invoice_id":"A1","payee_id":"pp","amount_cents":NaN}', "non_finite_number"),
    ('{"invoice_id":"A1","payee_id":"pp","amount_cents":9007199254740993}', "amount_cents:amount_range"),
    ('{"invoice_id":"A1\\n","payee_id":"pp","amount_cents":5}', "invoice_id:id_pattern"),
    ('{"invoice_id":{"id":"A1"},"payee_id":"pp","amount_cents":5}', "invoice_id:type_not_string"),
    ('Sure! {"invoice_id":"A1","payee_id":"pp","amount_cents":5}', "not_one_json_object"),
    ('[' * 50 + ']' * 50, "not_one_json_object"),
    ('{"a":' * 50 + '1' + '}' * 50, "too_deep"),
])
def test_rejects(raw, code):
    p = strict_parse(raw, PAY_INVOICE); assert not p.ok and p.code.startswith(code)
def test_mass_assignment_is_closed():
    p = ok({**G, "approver": "x"}); assert not p.ok
    r = build_pay_request(ok(G).value, day=100, principal="prin_emily"); assert r.approver is None and r.doc_amount_cents == DOC_NOT_FOUND
def test_rationale_is_bounded_text():
    assert ok({**G, "rationale": "paper, October"}).ok
    assert not ok({**G, "rationale": "a\nINJECTED log line"}).ok
    assert not ok({**G, "rationale": "x" * 281}).ok
def test_sentinel_holds_in_m3():
    v = Vendors({"p1": Vendor("p1", "L", "ACC1", 250_000, live_since=-300, created_day=-365, confirmed_by="kb")})
    g = MoneyGate("t", v, {"I1": Invoice("I1", "p1", 100_000)}, Ledger())
    d = g.check(PayRequest("I1", "p1", 100_000, doc_amount_cents=DOC_NOT_FOUND, day=100), reserve=False)
    assert d.outcome == "HOLD" and "M3_document_amount_not_found" in d.codes
def test_json_schema_shape():
    s = to_json_schema(PAY_INVOICE); assert s["additionalProperties"] is False and set(s["required"]) == {"invoice_id", "payee_id", "amount_cents"}
def test_retry_budget_and_notice_never_echo_model_text():
    seen = []
    def ask(notice):
        seen.append(notice); return '{"invoice_id":"A1","payee_id":"pp","amount_cents":5,"account":"EVIL-ACCOUNT-123"}' if notice is None else '{"invoice_id":"A1","payee_id":"pp","amount_cents":5}'
    p, n, codes = parse_with_retry(ask, PAY_INVOICE, 2)
    assert p.ok and n == 2 and codes[0].startswith("unexpected_field") and "EVIL" not in seen[1]
    p, n, codes = parse_with_retry(lambda _: "nope", PAY_INVOICE, 2); assert not p.ok and n == 2 and p.code == "retry_budget_spent"
