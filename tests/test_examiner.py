import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import copy, io, contextlib
import bulwark.examiner as X
from bulwark.evidence import ChainLog
import ch39_payment as P

def built(v):
    b = P.build(v); ok, _ = ChainLog.verify_rows(b["rows"]); return b, ok

def test_v1_covers_13_of_14_and_q14_is_not_in_the_export():
    b, ok = built("V1"); cov = X.coverage(b["rows"], P.TASK, P.PAYEE, ok)
    assert [q for q, c in cov.items() if c[0] != "ANSWERABLE"] == ["Q14"]

def test_v2_has_gaps_where_the_old_build_recorded_nothing():
    b, ok = built("V2"); cov = X.coverage(b["rows"], P.TASK, P.PAYEE, ok)
    assert cov["Q7"][0] == "NOT_IN_EVIDENCE" and cov["Q10"][0] == "NOT_IN_EVIDENCE" and cov["Q11"][0] == "NOT_IN_EVIDENCE" and cov["Q12"][0] == "NOT_IN_EVIDENCE" and cov["Q6"][0] == "PARTIAL"

def test_scope_is_the_task_and_the_payees_vendor_rows():
    b, ok = built("V1"); sc = X.scope(b["rows"], P.TASK, P.PAYEE)
    assert {r["task"] for r in sc} == {P.TASK, "t_vendor_ls"} and len(sc) == 12

def test_broken_chain_makes_q13_unanswerable():
    b, ok = built("V1"); rows = copy.deepcopy(b["rows"]); rows[5]["decision"] = "ALLOW"; ok2, _ = ChainLog.verify_rows(rows)
    assert not ok2 and X.coverage(rows, P.TASK, P.PAYEE, ok2)["Q13"][0] == "NOT_IN_EVIDENCE"

def sheet(b, ok):
    sc = {r["kind"] + str(i): r for i, r in enumerate(X.scope(b["rows"], P.TASK, P.PAYEE))}
    return sc

def test_a_correct_sheet_is_clean_and_a_wrong_fact_is_caught():
    b, ok = built("V1"); rows = b["rows"]; sc = X.scope(rows, P.TASK, P.PAYEE); by = {}
    for r in sc: by.setdefault(r["kind"], []).append(r["seq"])
    good = [dict(id="Q3", status="ANSWERED", cites=by["dispatch"], facts=dict(invoice="INV-2231", payee=P.PAYEE, amount_cents=481250)), dict(id="Q14", status="NOT_IN_EVIDENCE", cites=[], facts={})]
    iss = [i for i in X.check(good, rows, P.TASK, P.PAYEE, ok) if i[0] != "MISSING_QUESTION"]; assert iss == []
    bad = [dict(id="Q3", status="ANSWERED", cites=by["dispatch"], facts=dict(invoice="INV-2231", payee=P.PAYEE, amount_cents=418250))]
    assert ("FACT_NOT_IN_CITED_ROWS", "Q3:amount_cents=418250") in X.check(bad, rows, P.TASK, P.PAYEE, ok)

def test_no_citation_and_row_out_of_scope():
    b, ok = built("V1"); rows = b["rows"]
    iss = X.check([dict(id="Q5", status="ANSWERED", cites=[], facts=dict(policy="v0.37"))], rows, P.TASK, P.PAYEE, ok); assert ("NO_CITATION", "Q5") in iss
    iss = X.check([dict(id="Q5", status="ANSWERED", cites=[10], facts=dict(policy="v0.37"))], rows, P.TASK, P.PAYEE, ok); assert ("CITED_ROW_NOT_IN_SCOPE", "Q5:10") in iss

def test_answering_what_the_evidence_cannot_answer_is_caught_and_so_is_refusing_what_it_can():
    b, ok = built("V2"); rows = b["rows"]
    iss = X.check([dict(id="Q12", status="ANSWERED", cites=[], facts=dict(model="haiku45", prompt_version="p_coord_1.4"))], rows, P.TASK, P.PAYEE, ok); assert ("ANSWERED_WITHOUT_EVIDENCE", "Q12") in iss
    iss = X.check([dict(id="Q5", status="NOT_IN_EVIDENCE", cites=[], facts={})], rows, P.TASK, P.PAYEE, ok); assert ("REFUSED_BUT_AVAILABLE", "Q5") in iss

def test_partial_answer_beyond_evidence():
    b, ok = built("V2"); rows = b["rows"]; ap = [r["seq"] for r in X.scope(rows, P.TASK, P.PAYEE) if r["kind"] == "approval"]
    iss = X.check([dict(id="Q6", status="ANSWERED", cites=ap, facts=dict(approver="prin_hector", approval_ms=40000))], rows, P.TASK, P.PAYEE, ok); assert ("ANSWERED_BEYOND_EVIDENCE", "Q6") in iss

def test_timeline_is_one_line_per_row_with_the_seq():
    b, ok = built("V1"); sc = X.scope(b["rows"], P.TASK, P.PAYEE); tl = X.timeline(sc)
    assert len(tl) == len(sc) and tl[0].startswith("[0] ")

def test_free_text_never_reaches_the_export():
    b, ok = built("V1"); assert not any("attacker.example" in str(r) for r in b["rows"])

def test_retained_segment_verifies_but_not_as_a_whole_chain():
    b, ok = built("V1"); seg = b["rows"][60:]
    assert not ChainLog.verify_rows(seg)[0]
    good, msg = X.verify_segment(seg, b["export"]["anchors"]); assert good and "anchors inside" in msg

def test_segment_detects_an_edit_and_an_anchor_mismatch():
    b, ok = built("V1"); seg = copy.deepcopy(b["rows"][60:]); seg[10]["amount_cents"] = 1
    assert not X.verify_segment(seg, b["export"]["anchors"])[0]
    seg2 = copy.deepcopy(b["rows"][60:]); anchors = copy.deepcopy(b["export"]["anchors"]); anchors[-1]["head"] = "0" * 64
    assert not X.verify_segment(seg2, anchors)[0]

def test_segment_detects_tail_truncation_against_a_later_anchor():
    b, ok = built("V1"); seg = b["rows"][60:-3]
    good, msg = X.verify_segment(seg, b["export"]["anchors"]); assert not good and msg.startswith("truncated")

def test_list_valued_fact_supported_by_two_cited_rows():
    b, ok = built("V1"); rows = b["rows"]; gate = [r["seq"] for r in rows if r["kind"] == "money_gate" and r["task"] == P.TASK]
    sheet = [{"id": "Q4", "status": "ANSWERED", "cites": gate, "facts": {"decision": ["HOLD", "ALLOW"], "reasons": ["M8_dual_control_missing", "ok"]}}]
    iss = [i for i in X.check(sheet, rows, P.TASK, P.PAYEE, ok) if i[1].startswith("Q4")]; assert iss == []
    sheet[0]["facts"]["decision"] = ["HOLD", "SENT"]; assert any(k == "FACT_NOT_IN_CITED_ROWS" for k, _ in X.check(sheet, rows, P.TASK, P.PAYEE, ok))

def test_q13_may_cite_rows_outside_the_payment():
    b, ok = built("V1"); sheet = [{"id": "Q13", "status": "ANSWERED", "cites": [0, 5, 50], "facts": {"chain_verified": True}}]
    assert not [i for i in X.check(sheet, b["rows"], P.TASK, P.PAYEE, ok) if i[1].startswith("Q13")]
