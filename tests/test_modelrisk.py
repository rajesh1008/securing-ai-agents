import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bulwark.modelrisk import Component, classify, tier, pack, agreement, norm, IN_SCOPE, EXCLUDED_RULES, OUT_GENAI

def C(**kw):
    d = dict(id="x", name="x", chapter="1", method="rules", output="decision", feeds="payment"); d.update(kw); return Component(**d)

def test_llm_and_agent_are_out_of_scope_not_excluded():
    assert classify(C(method="llm", output="text"))[0] == OUT_GENAI and classify(C(method="agent"))[0] == OUT_GENAI

def test_rules_excluded_statistical_in_scope():
    assert classify(C(method="rules"))[0] == EXCLUDED_RULES
    assert classify(C(method="statistical", output="estimate"))[0] == IN_SCOPE

def test_tier_depends_on_gate_after():
    assert tier(C(feeds="payment", gate_after=False)) == "HIGH" and tier(C(feeds="payment")) == "MEDIUM" and tier(C(feeds="alert")) == "LOW"

def test_pack_marks_missing_weak_ok_and_skips_rules():
    comps = [C(id="m", method="statistical", output="estimate", feeds="alert"), C(id="r")]
    items = {"E1": ("LAB_SIM", ()), "E2": ("REVIEW", ())}
    p = pack(comps, items, {("m", "outcomes_analysis"): ("E1",), ("m", "ongoing_monitoring"): ("E2",)})
    st = {(c, e): s for c, e, s, _ in p.rows}
    assert st[("m", "outcomes_analysis")] == "OK" and st[("m", "ongoing_monitoring")] == "WEAK" and st[("m", "conceptual_soundness")] == "MISSING"
    assert all(c != "r" for c, _, _, _ in p.rows)

def test_agreement_and_norm():
    assert norm("$1,234.50") == 1234.5 and norm(" Lone  Star ") == "lone star"
    a = [[{"v": "1"}, {"v": "2"}], [{"v": "1.0"}, {"v": "3"}]]
    assert agreement(a, ["v"]) == 0.5
