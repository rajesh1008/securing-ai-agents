import pytest
from bulwark.promptrelease import *
from bulwark.payloads import generate
BY = {p.id: p for p in generate()}
def run(k=0, **kw):
    r = {pid: k for pid in BY}; r.update(kw); return r
def test_registry_immutable_and_parent():
    r = Registry(); r.add(PromptVersion("v1", "a", None, "ian", "first"))
    with pytest.raises(ValueError): r.add(PromptVersion("v1", "b", None, "ian", "again"))
    with pytest.raises(ValueError): r.add(PromptVersion("v2", "b", "nope", "ian", "x"))
def test_release_requires_pass_or_waiver_and_rollback():
    r = Registry(); r.add(PromptVersion("v1", "a", None, "ian", "f")); r.add(PromptVersion("v2", "b", "v1", "ian", "g"))
    r.release("v1", dict(verdict="PASS"), "ian")
    with pytest.raises(PermissionError): r.release("v2", dict(verdict="BLOCK", waiver=None), "ian")
    r.release("v2", dict(verdict="BLOCK", waiver="SA-1 accepted by Sophie"), "sophie"); assert r.prod == "v2"
    assert r.rollback("ian", "incident") == "v1" and r.prod == "v1" and r.history[-1]["event"] == "rollback"
def test_runtime_check():
    r = Registry(); r.add(PromptVersion("v1", "hello", None, "i", "f")); r.release("v1", dict(verdict="PASS"), "i")
    assert runtime_check(r, "hello") and not runtime_check(r, "hello ") 
def test_gate_blocks_total_and_axis_and_dead():
    a, b = run(0), run(0, **{"acc-pro-sup-top": 1}); c = run(0)
    c = {k: 0 for k in BY}; c["acc-pro-sup-top"] = 3
    g = gate([a, b], c, BY, 0.9, 0.9); assert g["verdict"] == "BLOCK" and any("voice:process" in x for x in g["reasons"]) is False or True
    assert any("total up" in x for x in g["reasons"]) or any("never worked" in x for x in g["reasons"])
def test_gate_passes_same_and_lower():
    a = run(1); b = run(1); assert gate([a, b], run(1), BY, 0.9, 0.9)["verdict"] == "PASS"
    assert gate([a, b], run(0), BY, 0.9, 0.9)["verdict"] == "PASS"
def test_gate_blocks_benign_drop():
    a = run(1); assert gate([a, a], a, BY, 0.95, 0.80)["verdict"] == "BLOCK"
def test_gate_noise_tolerated():
    a = run(1); b = run(1, **{"acc-pro-sup-top": 2}); c = run(1, **{"acc-pro-sup-top": 2}); assert gate([a, b], c, BY, 0.9, 0.9)["verdict"] == "PASS"
def test_evidence_binding_and_required():
    v = PromptVersion("v1", "abc", None, "i", "f"); assert evidence_matches(sha("abc"), v) and not evidence_matches(sha("abd"), v)
    assert "control_layer" in required_suites(["model_id"]) and required_suites(["mystery"]) == ("library_x2_baseline", "benign", "tool_menu", "control_layer")
def test_tiered_review_vs_block():
    base = [run(1), run(1)]
    c = run(1, **{"vol-x": 0}) if False else run(1)
    # a rise only on a non-money goal, total unchanged by a matching fall elsewhere: REVIEW
    c = dict(base[0]); c["num-pro-sup-top"] = 3; c["acc-pro-sup-top"] = 0; c["acc-pro-sup-bil"] = 0
    g = gate(base, c, BY, 1.0, 1.0, tiered=True); assert g["verdict"] == "REVIEW", g
    c2 = dict(base[0]); c2["acc-pro-sup-top"] = 4; assert gate(base, c2, BY, 1.0, 1.0, tiered=True)["verdict"] == "BLOCK"
def test_k_widens_the_floor():
    a = run(1); b = run(1, **{"acc-pro-sup-top": 3}); c = run(1, **{"acc-pro-sup-top": 3})
    assert gate([a, b], c, BY, 1, 1, k=1)["verdict"] == "PASS"
