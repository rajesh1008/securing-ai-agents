import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bulwark.ownership import Person, Decision, Register
import ch44_org as O
P = {p.id: p for p in [Person("A", "A", "head", budget=True, risk_appetite=True), Person("B", "B", "lead", reports_to="A"), Person("X", "X", "contractor", internal=False)]}
def reg(*ds, **kw): return Register(P, list(ds), **kw)
def kinds(r): return {k for k, _ in r.issues()}
def test_role_and_shared_accountable_are_flagged():
    assert "ACCOUNTABLE_NOT_A_PERSON" in kinds(reg(Decision("D1", "x", "security", max_days=3, on_timeout="hold", deputy="A")))
    assert "SHARED_ACCOUNTABLE" in kinds(reg(Decision("D1", "x", "A, B", max_days=3, on_timeout="hold", deputy="A")))
def test_self_approval_and_silent_timeout():
    k = kinds(reg(Decision("D1", "x", "B", requested_by=("B",), max_days=2, on_timeout="accept", deputy="A")))
    assert {"SELF_APPROVAL", "SILENT_TIMEOUT"} <= k
def test_risk_acceptance_needs_authority_and_deputy_too():
    assert "NO_AUTHORITY_TO_ACCEPT" in kinds(reg(Decision("D1", "x", "B", max_days=5, on_timeout="hold", needs_risk_appetite=True, deputy="A")))
    assert "DEPUTY_NO_AUTHORITY" in kinds(reg(Decision("D1", "x", "A", max_days=5, on_timeout="hold", needs_risk_appetite=True, deputy="B")))
def test_deputy_rules():
    assert "NO_DEPUTY" in kinds(reg(Decision("D1", "x", "A", max_days=5, on_timeout="hold")))
    assert "NO_DEPUTY" not in kinds(reg(Decision("D1", "x", "A", max_days=5, on_timeout="hold"), check_deputy=False))
    assert "DEPUTY_SELF_APPROVAL" in kinds(reg(Decision("D1", "x", "A", requested_by=("B",), max_days=5, on_timeout="hold", deputy="B")))
def test_outside_owner_and_escalation_to_self():
    r = reg(Decision("D1", "x", "A", max_days=5, on_timeout="escalate:A", deputy="B"), controls={"C1": "X"})
    assert {"BAD_ESCALATION", "CONTROL_OWNER_OUTSIDE"} <= kinds(r)
def test_departure_moves_to_deputy():
    r = reg(Decision("D1", "x", "B", max_days=5, on_timeout="hold", deputy="A"), Decision("D2", "y", "B", max_days=5, on_timeout="hold"))
    d = r.depart("B"); assert d["decisions"] == ["D2"] and d["decisions_to_deputy"] == ["D1"]
def test_route_unknown_kind_goes_to_head_with_approval():
    assert reg(Decision("D1", "x", "B", max_days=5, on_timeout="hold", deputy="A")).route("ZZ") == ("A", True)
def test_book_registers():
    assert len(O.draft().issues()) == 71 and O.revised().issues() == []
    assert ("CONCENTRATION", "Kevin:13") in O.rev1().issues()
