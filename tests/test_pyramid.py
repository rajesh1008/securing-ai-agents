import pytest
from bulwark.pyramid import *
from bulwark.sandbox import Manifest
BASE = Deployment(mounts={"/data/inv.csv": "ro:/work/inv.csv"}, env_names=["TZ"], network="none", tools=["read_doc"], egress_hosts=["mail.ledgerly.example"],
                  model_alias="quill-main", prompt_digest="aa", budget=dict(max_calls=12, max_egress=3), rung="R3")
def mod(**kw):
    d = Deployment(**{**BASE.__dict__, **kw}); return d
def test_identical_deployment_passes():
    ok, why = check_deployment(BASE, mod()); assert ok and why == []
def test_added_mount_fails_and_names_it():
    ok, why = check_deployment(BASE, mod(mounts={**BASE.mounts, "/home/u": "/home/u"})); assert not ok and "mount added: /home/u" in why[0]
def test_mount_made_writable_fails():
    ok, why = check_deployment(BASE, mod(mounts={"/data/inv.csv": "/work/inv.csv"})); assert not ok and "writable" in why[0]
def test_each_widening_kind_is_caught():
    for d in (mod(env_names=["TZ", "HOME"]), mod(network="open"), mod(network="broker:x"), mod(tools=["read_doc", "shell"]), mod(egress_hosts=["a.example", "mail.ledgerly.example"]),
              mod(budget=dict(max_calls=13, max_egress=3)), mod(budget=dict(max_calls=12)), mod(budget=dict(max_calls=12, max_egress=3, max_tokens=9)), mod(rung="R2")):
        assert not check_deployment(BASE, d)[0], d
def test_narrowing_and_neutral_changes_pass():
    assert check_deployment(BASE, mod(budget=dict(max_calls=6, max_egress=3), tools=[], rung="R3", env_names=[]))[0]
def test_model_and_prompt_change_pass_but_are_routed_to_live():
    ok, why = check_deployment(BASE, mod(model_alias="quill-next", prompt_digest="bb")); assert ok and all(w.startswith("live-floor") for w in why) and len(why) == 2
def test_waiver_needs_a_sentence_with_a_name():
    d = mod(env_names=["TZ", "HOME"]); key = "environment variable added: HOME"
    assert not check_deployment(BASE, d, {key: "ok"})[0]
    assert not check_deployment(BASE, d, {key: "needed for the path lookup in the export"})[0]
    assert check_deployment(BASE, d, {key: "Needed for the export path; approved by Sophie Adler on review 41"})[0]
def test_from_manifest_has_names_not_values():
    m = Manifest(inputs={"/x": "/work/x"}, env={"TZ": "secret-value"}); d = Deployment.from_manifest(m); assert d.env_names == ["TZ"] and "secret-value" not in d.to_json()
def test_binom_sf_known_values():
    assert binom_sf(10, 0, .3) == 1.0 and abs(binom_sf(10, 10, .5) - 0.5 ** 10) < 1e-12 and abs(binom_sf(4, 1, .5) - 15 / 16) < 1e-12
def test_plan_live_test_meets_both_targets():
    n, k = plan_live_test(0.02, 0.15); assert binom_sf(n, k, 0.02) <= 0.05 and binom_sf(n, k, 0.15) >= 0.8
    assert binom_sf(n - 1, k, 0.15) < 0.8 or plan_live_test(0.02, 0.15)[0] == n
def test_plan_from_zero_baseline_and_impossible():
    n, k = plan_live_test(0.0, 0.1); assert k == 1 and binom_sf(n, 1, 0.1) >= 0.8
    assert plan_live_test(0.1, 0.11, n_max=50) is None
def test_live_verdict_tiers():
    assert live_verdict(60, 0, 0.0) == "PASS" and live_verdict(60, 5, 0.01) == "BLOCK" and live_verdict(60, 3, 0.02) in ("REVIEW", "BLOCK") and live_verdict(60, 1, 0.05) == "PASS"
def test_pyramid_stops_at_first_failure_and_lists_skipped():
    fl = [Floor("unit", lambda: (True, "")), Floor("scenario", lambda: (False, "case 3")), Floor("live", lambda: (True, ""), 4.0)]
    rec = Pyramid(fl).run(); assert [r["floor"] for r in rec] == ["unit", "scenario"] and Pyramid.skipped(rec, fl) == ["live"]
def test_corpus_is_append_only_and_reports_gaps():
    c = Corpus(); c.add(Case("B1", "red team", "mount", "deployment")); c.add(Case("B2", "incident", "recipient", "scenario"))
    with pytest.raises(ValueError): c.add(Case("B1", "x", "y", "unit"))
    with pytest.raises(ValueError): c.add(Case("B3", "x", "y", "ceiling"))
    c.record("B1", "deployment"); c.record("B2", "live"); assert c.gaps() == ["B2"] and c.lowest_catch("B2") == "live" and c.lowest_catch("B1") == "deployment"
def test_monitor_probes_alert_at_once():
    m = Monitor(0.05); m.probe("must_allow", True); m.probe("must_refuse", False); assert m.first_alert() is None
    m.probe("must_refuse", True); assert m.first_alert() == 3
    m2 = Monitor(0.05); m2.probe("must_allow", False); assert m2.first_alert() == 1
def test_monitor_denial_rate_alerts_only_on_a_real_shift():
    import random; r = random.Random(3); m = Monitor(0.05, window=200, alpha=0.001)
    for _ in range(600): m.traffic(r.random() < 0.05)
    assert m.first_alert() is None
    for _ in range(400): m.traffic(r.random() < 0.20)
    assert m.first_alert() is not None and "up" in m.alerts[0][1]
