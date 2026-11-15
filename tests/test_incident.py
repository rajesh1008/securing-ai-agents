import pytest
from bulwark.detect import Obs
from bulwark.incident import scope, contain, standing_hold, Case, Decision

def O(i, day, v="v1", amt=1000, dest="A", route="AUTO", old="AUTO", conflict=None, paid=None, conf=None):
    return Obs(i, day, v, amt, dest, route, (), old, conflict, conf, paid if paid is not None else day + (4 - day) % 7)

def world():
    return [O("a", 1, "v1"), O("b", 2, "v1", dest="B"), O("c", 3, "v1", dest="B"), O("d", 9, "v1", dest="B"), O("e", 3, "v2"), O("f", 10, "v2", route="REVIEW", old="REVIEW")]

def test_scope_same_account_and_vendor():
    obs = world(); s = scope(obs[1], obs)
    assert s["same_item"] == {"b"} and s["same_account"] == {"b", "c", "d"} and s["same_vendor"] == {"a", "b", "c", "d"}

def test_scope_window_excludes_old_days():
    obs = world() + [O("z", 80, "v1", dest="B")]; s = scope(obs[-1], obs, window=30)
    assert s["same_account"] == {"z"}

def test_contain_only_unpaid_items_are_prevented():
    obs = world(); truth = {"b": 500, "c": 700, "d": 900}   # b, c paid day 4 and d day 11
    r = contain(obs, truth, obs[1], "freeze_account", lag=0)
    assert r["prevented"] == 500 + 700 + 900 and r["gone"] == 0
    r = contain(obs, truth, obs[1], "freeze_account", lag=3)   # eff 5: b and c are paid on day 4
    assert r["gone"] == 1200 and r["prevented"] == 900

def test_hold_days_limits_a_hold_but_not_a_rollback():
    obs = [O("x", 1, dest="B"), O("y", 40, dest="B", old="REVIEW")]; truth = {"x": 100, "y": 100}
    assert contain(obs, truth, obs[0], "hold_vendor", 0, hold_days=14)["prevented"] == 100
    assert contain(obs, truth, obs[0], "rollback_control", 0, hold_days=14)["prevented"] == 100   # only y differs from the old route

def test_collateral_counts_non_attack_items():
    obs = world(); r = contain(obs, {"b": 1}, obs[1], "pause_auto", 0)
    assert r["collateral_items"] == 4 and r["stopped_attacks"] == 1

def test_standing_hold_ignores_a_vendors_first_account_and_ages_out():
    obs = [O("a", 1), O("b", 8, dest="B"), O("c", 15, dest="B"), O("d", 22, dest="B"), O("e", 29, dest="B"), O("f", 36, "v1")]
    truth = {i: 100 for i in "bcde"}; r = standing_hold(obs, truth, eff=0, season=3)
    assert r["prevented"] == 300 and r["remaining"] == 100 and r["collateral_items"] == 0

def test_standing_hold_confirmation_is_a_hole_when_honoured():
    obs = [O("a", 1), O("b", 8, dest="B", conf=True), O("c", 15, dest="B")]; truth = {"b": 100, "c": 100}
    assert standing_hold(obs, truth, 0, honour_confirmation=False)["prevented"] == 200
    assert standing_hold(obs, truth, 0, honour_confirmation=True)["prevented"] == 0

def test_case_cannot_close_with_unknowns():
    c = Case("1", "a", [{"x": 1}], "cfg"); c.add(Decision("hold", "ann", "2026-01-01", "contract s3", True))
    assert c.can_close()
    c.add(Decision("notify", "ann", "5 days", "VERIFY", True)); assert "DEADLINE_UNSOURCED:notify" in c.open_questions() and not c.can_close()
    c2 = Case("2", "a", [], "cfg"); c2.add(Decision("x", None, None, None)); assert set(c2.open_questions()) == {"NO_OWNER:x", "NO_DEADLINE:x", "OPEN:x"}

def test_case_digest_changes_with_rows():
    a = Case("1", "a", [{"x": 1}], "c"); b = Case("1", "a", [{"x": 2}], "c"); assert a.digest() != b.digest()
