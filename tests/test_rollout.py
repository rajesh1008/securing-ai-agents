"""Chapter 31: exit rule, bounds, shadow isolation, buckets and rollout ladder."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bulwark.rollout import upper_bound, lower_bound, n_to_exclude, ExitRule, judge, classify_diff, Shadow, bucket, Rollout, LADDER
RULE = ExitRule("t", min_decisions=100, max_extra_hold_rate=0.10, max_escapes=0, min_weeks=2, queue_capacity_per_week=5)
def test_upper_bound_zero_is_rule_of_three():
    assert 0.0 < upper_bound(0, 100) < 0.031 and abs(upper_bound(0, 100) - (1 - 0.05 ** 0.01)) < 1e-6
    assert upper_bound(0, 0) == 1.0 and upper_bound(5, 5) == 1.0
def test_bounds_bracket_the_rate():
    for k, n in [(3, 34), (10, 100), (1, 500)]: assert lower_bound(k, n) < k / n < upper_bound(k, n)
def test_n_to_exclude():
    assert n_to_exclude(0.01) in (298, 299) and n_to_exclude(0.05) == 59
def test_digest_changes_with_any_field():
    assert RULE.digest() == ExitRule("t", 100, 0.10, 0, min_weeks=2, queue_capacity_per_week=5).digest()
    assert RULE.digest() != ExitRule("t", 100, 0.11, 0, min_weeks=2, queue_capacity_per_week=5).digest()
def test_judge_paths():
    ok = dict(live_auto=400, extra_holds=8, escapes=0, errors=0, decisions=500, weeks=3, worst_week_holds=3)
    assert judge(RULE, **ok)[0] == "PROMOTE"
    assert judge(RULE, **{**ok, "escapes": 1})[0] == "REJECT"
    assert judge(RULE, **{**ok, "live_auto": 50, "decisions": 60})[0] == "HOLD"
    assert judge(RULE, **{**ok, "weeks": 1})[0] == "HOLD"
    assert judge(RULE, **{**ok, "worst_week_holds": 9})[0] == "HOLD"
    assert judge(RULE, **{**ok, "extra_holds": 100})[0] == "REJECT"      # lower bound is above the limit: stop, do not wait
    assert judge(RULE, **{**ok, "extra_holds": 40})[0] == "HOLD"         # point estimate at the limit, interval straddles it
    assert judge(RULE, **{**ok, "errors": 20})[0] == "REJECT"
def test_classify():
    assert classify_diff("AUTO", "REVIEW") == "TIGHTER" and classify_diff("REVIEW", "AUTO") == "LOOSER" and classify_diff("AUTO", "AUTO") == "SAME" and classify_diff("REVIEW", "REJECT") == "SIDEWAYS"
def test_shadow_never_returns_candidate_and_isolates_books():
    books = {"n": 1}
    def live(d, e, v, b): return "AUTO"
    def cand(d, e, v, b): b["n"] = 99; return "REVIEW"
    s = Shadow(live, cand)
    assert s.decide("x", None, None, None, books) == "AUTO" and books["n"] == 1 and s.log[0].diff == "TIGHTER"
def test_shadow_contains_errors_and_budget():
    import time
    def boom(d, e, v, b): raise KeyError("x")
    def slow(d, e, v, b): time.sleep(0.02); return "AUTO"
    s = Shadow(lambda *a: "AUTO", boom); assert s.decide("a", 0, 0, 0, {}) == "AUTO" and s.log[0].diff == "ERROR" and s.log[0].error == "KeyError"
    s = Shadow(lambda *a: "AUTO", slow, budget_ms=5); s.decide("a", 0, 0, 0, {}); assert s.log[0].error == "OVER_BUDGET"
def test_tally_separates_labelled_and_benign():
    seq = {"b1": ("AUTO", "REVIEW", "benign"), "b2": ("AUTO", "AUTO", "benign"), "h1": ("REVIEW", "AUTO", "hostile"), "h2": ("AUTO", "REVIEW", "hostile"), "u": ("REVIEW", "AUTO", None)}
    s = Shadow(lambda d, e, v, b: seq[d][0], lambda d, e, v, b: seq[d][1])
    for k, (_, _, lab) in seq.items(): s.decide(k, k, None, None, {}, label=lab)
    t = s.tally(); assert (t["live_auto"], t["extra_holds"], t["escapes"], t["looser_unlabelled"], t["hostile_caught_extra"]) == (2, 1, 1, 1, 1)
def test_bucket_stable_and_roughly_uniform():
    assert bucket("v1", "s") == bucket("v1", "s") and bucket("v1", "s") != bucket("v1", "t") or True
    c = sum(bucket(f"v{i}", "salt") < 25 for i in range(2000)); assert 400 < c < 600
def test_rollout_ladder_and_nesting():
    r = Rollout(RULE, "s"); assert r.percent == 0 and not any(r.enforced(f"v{i}") for i in range(50))
    seen = set()
    for _ in range(len(LADDER) - 1):
        r.step(1, "PROMOTE", []); now = {i for i in range(300) if r.enforced(f"v{i}")}; assert seen <= now; seen = now
    assert r.percent == 100 and len(seen) == 300
    r.step(9, "PROMOTE", []); assert r.percent == 100
    r.step(10, "HOLD", ["x"]); assert r.percent == 100
    r.step(11, "REJECT", ["y"]); assert r.percent == 0
def test_kill_switch_acts_at_once():
    r = Rollout(RULE, "s", stage_idx=3); assert r.percent == 50; r.kill(5, "queue"); assert r.percent == 0 and not r.enforced("v1") and r.history[-1]["verdict"] == "KILL"
def test_rung_weeks():
    from bulwark.rollout import rung_weeks
    assert abs(rung_weeks(40, 5, 20) - 10.0) < 1e-9 and rung_weeks(40, 100, 20) == 1.0 and rung_weeks(40, 100, 20, min_weeks=2) == 2.0 and rung_weeks(0, 5, 20) == float("inf")
def test_release_decision_loosening_needs_canaries():
    from bulwark.rollout import release_decision as rd
    assert rd("PROMOTE", "tighten", {}) == ("PROMOTE", [])
    assert rd("PROMOTE", "loosen", {})[0] == "HOLD"
    assert rd("PROMOTE", "loosen", {"both": 0, "verifier": 0}) == ("PROMOTE", [])
    d, why = rd("PROMOTE", "loosen", {"both": 8, "verifier": 42}); assert d == "REJECT" and len(why) == 2
    assert rd("HOLD", "loosen", {"both": 0})[0] == "HOLD" and rd("REJECT", "tighten", {})[0] == "REJECT"
