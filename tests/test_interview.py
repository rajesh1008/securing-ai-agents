import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bulwark.interview import *
def test_three_exercises_start_unbounded():
    assert [score(e, {})["before"] for e in exercises()] == [6, 12, 6]
def test_careful_passes_all_and_reciter_none():
    for e in exercises():
        assert score(e, archetype_answer(e, "careful"))["pass"]
        assert not score(e, archetype_answer(e, "reciter (model review everywhere)"))["pass"]
def test_trap_record_does_not_bound():
    e = exercises()[0]; s = score(e, dict(fixes=dict(issue_credit="d", change_contact="b", send_sms="b")))
    assert s["residual"] == 2 and s["by_class"] == {"RECORD_WRITABLE": 2}
def test_weak_fix_can_make_a_bounded_tool_worse():
    e = exercises()[1]; assert score(e, dict(fixes=dict(git_push="b")))["residual"] == 16 and score(e, {})["residual"] == 12
def test_bad_option_id_keeps_original():
    e = exercises()[2]; assert score(e, dict(fixes=dict(send_correspondence="zz")))["residual"] == 6
def test_vocab_score_counts_distinct_terms():
    assert vocab_score("Least privilege, least-privilege and a sandbox") == 2 and vocab_score("") == 0
def test_recall_precision():
    e = exercises()[2]; s = score(e, dict(findings=[["claimant_email", "send_correspondence"], ["x", "y"]]))
    assert s["recall"] == 1 / 6 and s["precision"] == .5
def test_pick_for_unknown_tool_is_ignored():
    e = exercises()[1]; assert score(e, dict(fixes=dict(read_repo="a")))["residual"] == 12
def test_chapter_snippet_runs():
    from bulwark.casestudy import Programme, Source, Tool, Gate
    p = Programme("Acme", "launch", [Source("email", False), Source("owner", True)], [Tool("send_invoice", "EGRESS")])
    menu = {"send_invoice": [Option("a", "MODEL", "m", Gate("model")), Option("b", "RECORD", "r", Gate("deterministic", "customer record", True))]}
    ex = Exercise("Acme", p, menu)
    assert score(ex, {"fixes": {"send_invoice": "a"}})["residual"] == 1 and score(ex, {"fixes": {"send_invoice": "b"}})["pass"]
def test_ledgerly_quill_stage_passes_its_own_exercise_shape():
    import ch45_programmes as P
    from bulwark.casestudy import findings
    assert findings(P.A_final()) == [] and len(findings(P.A_day0())) == 16
