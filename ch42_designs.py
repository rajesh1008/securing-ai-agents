"""Chapter 42: design sheets for four versions of an invoice agent, written from the book's own history and one composite.
Q01 is Quill as Chapter 1 found it; Q12 is Quill after Part II's controls (Chapters 6-15); Q41 is Quill as Chapter 41 left it; DEMO is a composite of the way a framework quick-start wires an agent (author's judgement, no named product).
The sheets are data, written by the author from the chapters' text; nothing here is read from a running system."""
import copy, sys
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
import ch41_rota as R41

def _jobs(which):
    return [dict(id=j.id, owner=j.owner, backup=j.backup, evidence=j.evidence) for j in R41.build(which).jobs]

def q01():
    return dict(name="Q01 Quill, Chapter 1",
        steps=[dict(id="read_invoice", effect=None, decided_by="model"),
               dict(id="pay", effect="payment", decided_by="model", gate=False, destination_from="document", authority_from="model_label"),
               dict(id="email", effect="send_email", decided_by="model", gate=False, destination_from="model")],
        credentials=dict(in_context=True, per_task=False), tools=dict(loadout="all", third_party=False),
        egress=dict(mode="none"), controls_claimed=[dict(name="system prompt: never pay unknown vendors", kind="prompt")],
        scanners=[dict(name="marker scan v0.1", mode="denylist", role="control")], monitors=[], baselines=[], waivers=[], claims={})

def q12():
    d = dict(name="Q12 Quill after Part II",
        steps=[dict(id="read_invoice", effect=None, decided_by="model"),
               dict(id="pay", effect="payment", decided_by="code", gate=True, on_gate_error="closed", destination_from="registry", reviewer="person"),
               dict(id="bank_change", effect="bank_change", decided_by="rules", gate=True, on_gate_error="closed", destination_from="registry"),
               dict(id="email", effect="send_email", decided_by="code", gate=True, on_gate_error="closed", destination_from="registry")],
        credentials=dict(in_context=False, per_task=True), tools=dict(loadout="task", ratchet=True, third_party=False),
        egress=dict(mode="allowlist"), approvals=dict(bound_to_effect=True, render="full"), memory=dict(trust_labels=True),
        evidence=dict(chained=True, anchored=True, fields_for_examiner=False), budgets=dict(calls=12, egress=3, repeats=3),
        controls_claimed=[dict(name="money path M1-M8", kind="code"), dict(name="hardened prompt", kind="prompt")],
        scanners=[dict(name="marker scan", mode="denylist", role="signal")], monitors=[], baselines=[], waivers=[], claims={})
    return d

def q41():
    d = copy.deepcopy(q12()); d["name"] = "Q41 Quill, Chapter 41"
    d["controls_claimed"] = [dict(name="money path M1-M8", kind="code")]
    d["tools"].update(third_party=True, pinned=True)
    d["model_files"] = dict(refuse_code_formats=True, bill=True)
    d["agents"] = dict(count=3, handoff="typed", grant_shrinks=True)
    d["evidence"]["fields_for_examiner"] = True
    d["degradation"] = {"model_provider": "hold", "bank_feed": "queue", "registry": "deny", "anchor_service": "queue", "detector": "fallback_owned"}
    d["release_gate"] = dict(mode="strict", baseline_runs=True, anchor=True, new_hit_rule=True)
    d["monitors"] = [dict(name="amount detector", kind="threshold", role="signal", owner="Ian", alerts_per_week=1.5, read_capacity_per_week=10),
                     dict(name="extractor confidence", kind="confidence", role="signal", owner="security", alerts_per_week=4, read_capacity_per_week=10)]
    d["baselines"] = [dict(name="amount detector", ack_days=7, retune_days=91)]
    d["waivers"] = [dict(id="W03 detector shed cap", owner="Ian", review_day=300)]
    d["steps"].append(dict(id="run_report_code", effect="execute_code", decided_by="code", gate=True, on_gate_error="closed", sandbox="narrowed", network=False))
    d["incident"] = dict(blank_blocks_close=True, notices_sealed=True)
    d["jobs"] = _jobs("C") + [dict(id="J31", owner="Sophie", backup="Kevin", evidence="dated check output"), dict(id="J32", owner="Sophie", backup="Ian", evidence="access list with decision")]; d["claims"] = dict(compliant_with=[], evidence_levels=True)
    return d

def demo():
    return dict(name="DEMO framework quick-start composite",
        steps=[dict(id="pay", effect="payment", decided_by="model", gate=True, on_gate_error="open", destination_from="model", reviewer="model", authority_from="model_label"),
               dict(id="email", effect="send_email", decided_by="model", gate=True, on_gate_error="open", destination_from="model")],
        credentials=dict(in_context=False, per_task=False), tools=dict(loadout="all", third_party=True, pinned=False),
        egress=dict(mode="denylist"), approvals=dict(bound_to_effect=False, render="summary"),
        memory=dict(trust_labels=False), agents=dict(count=2, handoff="free_text", grant_shrinks=False),
        evidence=dict(chained=False, anchored=False, fields_for_examiner=False), budgets=dict(calls=50),
        controls_claimed=[dict(name="guardrail system prompt", kind="prompt"), dict(name="guardrail classifier", kind="model")],
        scanners=[dict(name="injection keyword filter", mode="denylist", role="control")],
        monitors=[dict(name="guardrail confidence", kind="confidence", role="gate", owner="", alerts_per_week=40, read_capacity_per_week=0)],
        baselines=[dict(name="anomaly score", ack_days=None, retune_days=None)], waivers=[dict(id="W1 skip approval for small payments", owner="", review_day=None)],
        release_gate=dict(mode="margins", baseline_runs=True, anchor=False, new_hit_rule=False), jobs=None,
        claims=dict(compliant_with=["OWASP Agentic Top 10"], evidence_levels=False))

DESIGNS = {"Q01": q01, "Q12": q12, "Q41": q41, "DEMO": demo}
