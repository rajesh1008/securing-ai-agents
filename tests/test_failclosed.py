import sys, math
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bulwark.failclosed import *
from bulwark.moneypath import *
from bulwark.egress import Ctx, Output, Egress
from bulwark.budget import Budget
from bulwark.mcpguard import AudienceTokens

def gate():
    v = Vendors({"p1": Vendor("p1", "L", "ACC-1", 300_000, live_since=-300, created_day=-365, confirmed_by="kb")})
    return MoneyGate("t", v, {"i1": Invoice("i1", "p1", 50_000)}, Ledger())
def req(**kw): return PayRequest(**{**dict(invoice_id="i1", payee_id="p1", amount_cents=50_000, doc_amount_cents=50_000, day=0, principal="prin_emily"), **kw})

def test_good_request_unchanged():
    assert hard_money(gate(), req()).outcome == gate().check(req()).outcome == "ALLOW"
def test_malformed_amounts_denied_with_code():
    for bad in (None, "50000", 5.5, True, -1, 0, float("nan"), 10**13):
        d = hard_money(gate(), req(amount_cents=bad)); assert d.outcome == "DENY" and d.codes[0].startswith("G1_malformed_amount")
def test_raw_gate_crashes_on_none_day_hard_does_not():
    try: gate().check(req(day=None)); raised = False
    except TypeError: raised = True
    assert raised and hard_money(gate(), req(day=None)).outcome == "DENY"
def test_approver_must_be_a_principal():
    assert hard_money(gate(), req(approver="None")).codes == ["G1_malformed_approver"]
def test_gate_crash_becomes_named_refusal():
    class Boom:
        def check(self, r): raise KeyError("x")
    assert hard_money(Boom(), req()).codes == ["G0_gate_error:KeyError"]
CTX = Ctx("t", ("ledgerly.example",), (), frozenset({"a@ledgerly.example"}), ("US-ACC-44110022",))
def test_egress_malformed_and_oversize_refused():
    e = Egress(4, CTX)
    assert not hard_egress(e, Output("email", to="a@ledgerly.example", body=None))[0]
    assert hard_egress(e, Output("email", to="a@ledgerly.example", body="x" * (MAX_TEXT + 1)))[1] == "G1_too_large_body"
    assert hard_egress(e, Output("request", url="https://[::1/x"))[1] == "G1_malformed_url"
    assert hard_egress(e, Output("request", url="https://ledgerly.example:99999999/"))[1] == "G1_malformed_url"
    assert hard_egress(e, Output("request", url="https://app.ledgerly.example/x"))[0]
def test_unknown_effect_is_charged_as_egress():
    b = Budget(max_calls=20, max_egress=1)
    assert hard_budget(b, "t", "Mony", {})[0] and not hard_budget(b, "t2", "money", {"a": 1})[0]
def test_nan_clock_refused():
    tk = AudienceTokens(b"k" * 32); tok = tk.mint("quill", ["r"], "t", 60, 1000.0)
    assert hard_token(tk, tok, "quill", "r", float("nan"))[0] is None and hard_token(tk, tok, "quill", "r", 1000.0)[0] is not None
def test_empty_or_nonstring_host_is_internal():
    assert hard_internal("") and hard_internal(None) and hard_internal(5) and not hard_internal("93.184.216.34")
def test_args_must_be_plain():
    assert hard_args({"properties": {"a": {}}}, None) == (False, "G1_malformed_input")
    assert hard_args({"properties": {"a": {}}}, {"a": object()})[1] == "G1_malformed_value"
def test_safe_join_name_length():
    assert hard_join("/tmp", "a" * 5000) is None and hard_join("/tmp", None) is None
def test_library_callers_use_the_edge():
    root = Path(__file__).resolve().parents[1] / "bulwark"
    for f in ("approval.py", "reconcile.py"):
        src = (root / f).read_text(); assert "hard_money(" in src and "self.gate.check(" not in src, f
