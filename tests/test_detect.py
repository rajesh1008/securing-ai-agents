import sys, math
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from bulwark.detect import *

def ob(i, day, v, amt, dest="A1", route="AUTO", old=None, conflict=None, conf=None, paid=None):
    return Obs(i, day, v, amt, dest, route, (), old, conflict, conf, paid)

def test_amount_silent_until_history():
    d = AmountDetector(min_hist=4)
    assert all(d.see(ob(f"o{k}", k, "v", 1000 + k)) is None for k in range(4)); assert d.silent == 4

def test_amount_fixed_vendor_any_change_alarms():
    d = AmountDetector(); [d.see(ob(f"o{k}", k, "v", 5000)) for k in range(5)]
    assert d.see(ob("x", 9, "v", 5001)).score == 9.0 and d.see(ob("y", 10, "v", 5000)) is None

def test_amount_variable_vendor_outlier_and_inlier():
    d = AmountDetector(); [d.see(ob(f"o{k}", k, "v", a)) for k, a in enumerate([900, 1100, 1000, 1200, 800, 1000])]
    assert d.see(ob("in", 9, "v", 1150)) is None and d.see(ob("out", 10, "v", 9000)) is not None

def test_amount_held_item_not_alerted_but_teaches_when_adaptive():
    d = AmountDetector(frozen=False); [d.see(ob(f"o{k}", k, "v", a)) for k, a in enumerate([900, 1100, 1000, 1200])]
    assert d.see(ob("h", 5, "v", 9000, route="REVIEW")) is None and 9000 in d.hist["v"]

def test_frozen_baseline_does_not_absorb_alerted_amounts():
    f, a = AmountDetector(frozen=True), AmountDetector(frozen=False)
    for d in (f, a):
        [d.see(ob(f"o{k}", k, "v", x)) for k, x in enumerate([900, 1100, 1000, 1200, 1000])]
        [d.see(ob(f"p{k}", 10 + k, "v", 20000)) for k in range(6)]
    assert 20000 not in f.hist["v"] and a.hist["v"].count(20000) >= 1

def test_account_alerts_on_unseasoned_new_destination_and_confirmation_lowers_score():
    d = AccountDetector(); [d.see(ob(f"o{k}", k, "v", 100)) for k in range(3)]
    a = d.see(ob("n1", 9, "v", 100, dest="B2", conf=False)); assert a and a.score == 8.0
    b = AccountDetector(); [b.see(ob(f"o{k}", k, "w", 100)) for k in range(3)]
    assert b.see(ob("c1", 9, "w", 100, dest="C3", conf=True)).score == 5.0

def test_account_new_destination_seasons_after_three_payments():
    d = AccountDetector(); [d.see(ob(f"o{k}", k, "v", 100)) for k in range(2)]
    r = [d.see(ob(f"n{k}", 5 + k, "v", 100, dest="B2", conf=True)) for k in range(5)]
    assert [x is not None for x in r] == [True, True, True, False, False]

def test_account_first_ever_payment_is_not_a_change():
    assert AccountDetector().see(ob("a", 1, "v", 100)) is None

def test_account_held_item_is_not_a_payment_but_carries_confirmation():
    d = AccountDetector(); [d.see(ob(f"o{k}", k, "v", 100)) for k in range(2)]
    assert d.see(ob("h", 5, "v", 100, dest="B2", route="REVIEW", conf=True)) is None
    assert d.see(ob("p", 6, "v", 100, dest="B2")).score == 5.0

def test_reverse_shadow_alerts_only_on_alarm_kind():
    r = ReverseShadow()
    assert r.see(ob("a", 1, "v", 1, old="REVIEW", conflict="PARSER_ABSTAIN")) is None
    assert r.see(ob("b", 1, "v", 1, old="REVIEW", conflict="PARSER_CONFLICT")) is not None
    assert r.see(ob("c", 1, "v", 1, old="AUTO")) is None and r.see(ob("d", 1, "v", 1, route="REVIEW", old="REVIEW")) is None
    assert r.counts == {"PARSER_ABSTAIN": 1, "PARSER_CONFLICT": 1}

def test_run_detector_fires_on_kth_consecutive_rise_and_resets():
    d = RunDetector(k=3, step=0.03); r = [d.see(ob(f"o{k}", k, "v", x)) for k, x in enumerate([100, 110, 121, 133, 146])]
    assert [x is not None for x in r] == [False, False, False, True, True]
    assert d.see(ob("dip", 9, "v", 90)) is None and d.run["v"] == 0

def test_cusum_ignores_baseline_rate_and_fires_on_shift():
    c = Cusum(0.1, 0.3, 4.0); assert not any(c.see(0) for _ in range(200))
    c2 = Cusum(0.1, 0.3, 4.0); fired = [c2.see(1, k) for k in range(10)]
    assert any(fired) and c2.fired_at is not None

def test_cusum_arl0_grows_with_threshold():
    assert arl0(0.1, 0.2, 5.0, runs=200) > arl0(0.1, 0.2, 2.0, runs=200)

def test_budget_keeps_top_scores_per_week_and_reports_shed():
    al = [Alert(f"a{k}", k % 7, "d", float(k), "") for k in range(5)] + [Alert("late", 8, "d", 1.0, "")]
    kept, shed = Budget(2).apply(al); assert {a.id for a in kept} == {"a4", "a3", "late"} and len(shed) == 3

def test_merge_keeps_best_score_and_lists_detectors():
    m = merge([Alert("i", 1, "amount", 4.0, "x"), Alert("i", 1, "account", 8.0, "y"), Alert("j", 2, "amount", 4.0, "z")])
    d = {a.id: a for a in m}; assert d["i"].detector == "account+amount" and d["i"].score == 8.0 and len(m) == 2

def test_score_in_time_and_loss_before_alert():
    obs = {"a": ob("a", 1, "v", 10, paid=4), "b": ob("b", 1, "v", 20, paid=4), "c": ob("c", 1, "v", 40, paid=4), "n": ob("n", 1, "v", 5, paid=4)}
    al = [Alert("a", 1, "d", 1, ""), Alert("b", 5, "d", 1, ""), Alert("n", 1, "d", 1, "")]
    r = score(al, {"a": 10, "b": 20, "c": 40}, obs, lag_days=1)
    assert (r["caught"], r["in_time"], r["false_alerts"], r["loss_paid_before_alert"]) == (2, 1, 1, 60)

def test_next_friday_weekday_arithmetic():
    assert [next_friday(d) for d in (0, 4, 5, 6)] == [4, 4, 11, 11]

def test_anchor_stops_baseline_learning():
    d = AmountDetector(frozen=False, anchor=5); [d.see(ob(f"o{k}", k, "v", x)) for k, x in enumerate([900, 1100, 1000, 1200, 1000])]
    [d.see(ob(f"p{k}", 10 + k, "v", 1300 + 100 * k)) for k in range(6)]
    assert len(d.hist["v"]) == 5

def test_config_digest_changes_with_any_threshold():
    a, b = DetectConfig(), DetectConfig(amount_z=3.5)
    assert a.digest() == DetectConfig().digest() and a.digest() != b.digest() and len(a.digest()) == 12

def test_monitor_merges_detectors_per_observation_and_sheds_by_cap():
    m = Monitor(DetectConfig(weekly_cap=1))
    for k in range(5): m.see(ob(f"o{k}", k, "v", 5000))
    a = m.see(ob("x", 6, "v", 6000)); assert a and a.score == 9.0
    b = m.see(ob("y", 6, "w", 100, old="REVIEW", conflict="PARSER_CONFLICT")); assert b.detector == "reverse_shadow"
    shown, shed = m.weekly_view(); assert [s.id for s in shown] == ["x"] and shed[0]["id"] == "y" and shed[0]["shed_by_cap"] == 1

def test_monitor_matches_manual_runs_on_the_same_stream():
    obs = [ob(f"o{k}", k, "v", 5000 if k < 6 else 7000, old=("REVIEW" if k == 8 else None), conflict=("PARSER_CONFLICT" if k == 8 else None)) for k in range(10)]
    m = Monitor(); [m.see(o) for o in obs]
    A, R_, Rn = AmountDetector(), ReverseShadow(), RunDetector(); Ac = AccountDetector(); al = []
    for o in obs: al += [a for d in (A, Ac, R_, Rn) if (a := d.see(o))]
    assert sorted(a.id for a in m.log) == sorted(a.id for a in merge(al))
