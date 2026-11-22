import pytest
from bulwark.redteam import *
def eng(**k):
    d = dict(name="x", in_scope=["invoice path"], out_of_scope=["production bank"], knowledge="grey", budget_rounds=10, budget_campaigns=12, stop_conditions=["real money moves"], data="synthetic"); d.update(k); return Engagement(**d)
def test_engagement_ok(): assert eng().problems() == []
def test_engagement_needs_exclusions_and_stop(): assert len(eng(out_of_scope=[], stop_conditions=[]).problems()) == 2
def test_live_data_needs_stop_on_customer_data_or_money(): assert eng(data="live", stop_conditions=["a person asks"]).problems() == ["live data without a customer-data or money stop condition"]
def test_zero_impact_is_a_note_whatever_the_reach(): assert Finding("F1", "t", "e", "a", 0, 3, 2).severity() == "note"
def test_score_and_bands():
    assert Finding("F", "t", "e", "a", 3, 3, 0).score() == 12 and Finding("F", "t", "e", "a", 3, 3, 2).severity() == "critical"
    assert Finding("F", "t", "e", "a", 1, 0, 0).severity() == "low" and Finding("F", "t", "e", "a", 2, 1, 1).severity() == "low" and Finding("F", "t", "e", "a", 2, 2, 1).severity() == "medium"
def test_triage_orders_by_severity_then_reach():
    a = Finding("A", "t", "e", "a", 1, 3, 0); b = Finding("B", "t", "e", "a", 3, 1, 0); assert [f.id for f in triage([a, b])] == ["B", "A"]
def test_closed_needs_fix_and_passing_retest():
    f = Finding("F", "t", "e", "a", 2, 2, 1); assert not f.closed(); f.fix = "x"; assert not f.closed(); f.retest = "pass"; assert f.closed()
def test_rule_of_three():
    assert campaigns_needed(0.05) == 59 and 0.045 < upper_bound(60, 0) < 0.05 and abs(upper_bound(36, 0) - 0.0803) < 0.001
def test_upper_bound_with_hits(): assert 0.2 < upper_bound(20, 2) < 0.30 and upper_bound(5, 5) == 1.0
def test_discovery_curve(): assert discovery_curve([1, 3, 3], 6, 4) == [1 / 6, 1 / 6, 3 / 6, 3 / 6]
def test_queue_flood_hurts_fifo_and_quota_protects():
    base = queue_wait(40, 0, 60); fl = queue_wait(40, 80, 60); q = queue_wait(40, 80, 60, policy="quota")
    assert base["median_wait_days"] == 0 and fl["backlog"] > 500 and fl["p90_wait_days"] > 10 and q["p90_wait_days"] < fl["p90_wait_days"]
def test_webhook_tenant_trust():
    books = {"tenant_a": {"INV-1": "a-row"}, "tenant_b": {"INV-1": "b-row"}}; body = {"tenant": "tenant_b", "invoice": "INV-1"}
    import json; sig = sign("tenant_a", json.dumps(body, sort_keys=True).encode())
    assert tenant_from_body(body, sig, books, "tenant_a") == "b-row"
    assert tenant_from_credential(body, sig, books, "tenant_a") == "REFUSED:tenant mismatch"

def test_impact3_reachable_is_at_least_high():
    assert Finding("F", "t", "e", "a", 3, 1, 0).severity() == "high" and Finding("F", "t", "e", "a", 3, 0, 0).severity() == "low"
def test_provenance_never_loosens():
    S = {"billing@lonestarpaper.example"}
    assert provenance_route("AUTO", "x@attacker.example", S) == "REVIEW" and provenance_route("AUTO", "billing@lonestarpaper.example", S) == "AUTO"
    assert provenance_route("REJECT", "billing@lonestarpaper.example", S) == "REJECT" and provenance_route("REVIEW", "x", S) == "REVIEW"

def test_severity_is_monotone_over_the_whole_grid():
    import itertools
    order = ["note", "low", "medium", "high", "critical"]
    sev = lambda i, r, d: order.index(Finding("x", "x", "x", "x", i, r, d).severity())
    for i, r, d in itertools.product(range(4), range(4), range(3)):
        for di, dr, dd in ((1, 0, 0), (0, 1, 0), (0, 0, 1)):
            if i + di < 4 and r + dr < 4 and d + dd < 3: assert sev(i + di, r + dr, d + dd) >= sev(i, r, d)
    assert sum(1 for c in itertools.product(range(4), range(4), range(3)) if sev(*c) == 4) == 1
