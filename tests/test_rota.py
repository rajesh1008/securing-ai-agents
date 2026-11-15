import pytest
from bulwark.rota import Job, Rota, simulate

def J(id="J", owner="a", backup="b", cadence=7, **kw):
    d = dict(name="n", chapter=1, minutes=10, evidence="e", grace=2); d.update(kw)
    return Job(id=id, owner=owner, backup=backup, cadence=cadence, **d)

def kinds(r): return sorted(k for k, _ in r.issues())

def test_clean_rota_has_no_issues():
    assert Rota([J("J1"), J("J2", owner="b", backup="a")], head="c").issues() == []

def test_unowned_and_no_backup_and_same_backup():
    r = Rota([J("J1", owner=""), J("J2", backup=""), J("J3", backup="a")], head="c")
    assert kinds(r) == ["BACKUP_IS_OWNER", "NO_BACKUP", "UNOWNED"]

def test_no_evidence_and_triggered_job_needs_trigger_and_rate():
    r = Rota([J("J1", evidence=""), J("J2", cadence=0), J("J3", cadence=0, trigger="x")], head="c")
    assert kinds(r) == ["NO_CADENCE", "NO_EVIDENCE", "NO_TRIGGER"]

def test_load_counts_triggered_runs_and_flags_overload():
    r = Rota([J("J1", cadence=1, minutes=20), J("J2", cadence=0, trigger="t", per_year=365, minutes=10)], head="c", cap_minutes={"a": 800})
    assert r.load()["a"] == pytest.approx(30 * 20 + 30 * 10)
    assert ("OVERLOAD", "a:900min/month") in r.issues()

def test_single_point_needs_more_than_k_unbacked_jobs():
    r = Rota([J(f"J{i}", backup="") for i in range(7)], head="c", single_point_k=6)
    assert "SINGLE_POINT" in kinds(r)
    r2 = Rota([J(f"J{i}", backup="") for i in range(6)], head="c", single_point_k=6)
    assert "SINGLE_POINT" not in kinds(r2)

def test_schedule_spreads_jobs_and_covers_window():
    r = Rota([J("J1", cadence=30), J("J2", cadence=30), J("J3", cadence=0, trigger="t", per_year=1)], head="c")
    s = r.schedule(0, 90)
    assert len(s) == 6 and {d for d, j in s if j == "J1"} == {0, 30, 60} and {d for d, j in s if j == "J2"} == {7, 37, 67}

def test_status_ladder():
    r = Rota([J("J1", cadence=7, grace=2)], head="c")
    assert r.status(10, {}) == {"J1": "NEVER_RUN"}
    st = lambda today: r.status(today, {"J1": 0})["J1"]
    assert [st(7), st(8), st(9), st(10), st(11), st(12), st(13), st(14)] == ["OK", "DUE", "DUE", "OVERDUE", "OVERDUE", "OVERDUE", "ESCALATED", "ESCALATED"]

def test_simulation_is_deterministic_and_backup_helps():
    r = Rota([J(f"J{i}", cadence=1, grace=1) for i in range(3)], head="c")
    assert simulate(r, 5, True, False) == simulate(r, 5, True, False)
    no = sum(simulate(r, s, False, False)["missed"] for s in range(30)); yes = sum(simulate(r, s, True, False)["missed"] for s in range(30))
    assert yes < no

def test_scorecard_counts_overdue_stale_waivers_and_unread():
    from bulwark.rota import scorecard
    r = Rota([J("J1", cadence=7, grace=2), J("J2", cadence=30, grace=5, backup="c")], head="h")
    lib = dict(last_added=0, families=3, dims_touched={"a"}, dims_all={"a", "b"})
    sc = scorecard(r, 100, {"J1": 80, "J2": 95}, {"J2": 90}, {"E1": (0, 30), "E2": (95, 30)}, [("W1", 50), ("W2", 120)], [("A1", 10, None), ("A2", 90, 91)], lib, dict(step=5, anchor=9))
    assert sc["overdue"] == 1 and sc["escalated"] == 1 and sc["most_overdue_job"] == "J1" and sc["most_overdue_days"] == 13
    assert sc["evidence_stale"] == ["E1"] and sc["backups_never_run"] == 1 and sc["backups_never_run_ids"] == ["J1"]
    assert sc["alerts_unread"] == 1 and sc["oldest_unread_days"] == 90 and sc["waivers_past_review"] == 1 and sc["oldest_waiver_past_days"] == 50
    assert sc["library_age_days"] == 100 and sc["dims_untouched"] == ["b"] and sc["anchor"] == dict(step=5, anchor=9)
