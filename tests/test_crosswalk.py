import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import copy
from bulwark.crosswalk import Row, Standard, Item, Catalogue, check, gaps, coverage, unmapped_controls, drift, rendered
from bulwark.crosswalk_data import CAT, rows, na_rows, STANDARDS

LV = {f"C{i:02d}": "measured_in_simulation" for i in range(1, 19)}
AS_OF = "2026-11-13"

def kinds(iss): return sorted({k for k, _ in iss})

def test_author_mapping_is_clean():
    assert check(rows(), CAT, LV, as_of=AS_OF) == [] or kinds(check(rows(), CAT, LV, as_of=AS_OF)) == ["READ_FROM_SECONDARY"]

def test_unknown_item_is_caught():
    r = rows() + [Row("C01", "LLM25", "LLM11", "2025", "ADDRESSES", "x")]
    assert ("UNKNOWN_ITEM", "C01 -> LLM25:LLM11") in check(r, CAT, LV, as_of=AS_OF)

def test_edition_mismatch():
    r = rows({"LLM25": "2023-24 (v1.1)"})
    assert "EDITION_MISMATCH" in kinds(check(r, CAT, LV, as_of=AS_OF))

def test_relation_above_evidence():
    lv = dict(LV); lv["C02"] = "designed"
    assert "RELATION_ABOVE_EVIDENCE" in kinds(check(rows(), CAT, lv, as_of=AS_OF))

def test_not_yet_applicable_blocks_addresses():
    r = rows() + [Row("C03", "EUAI", "Art12", "OJ 2024, as amended by the Digital Omnibus on AI (2026)", "EVIDENCE_FOR", "x")]
    iss = check(r, CAT, LV, as_of=AS_OF)
    assert any(k == "NOT_YET_APPLICABLE" for k, _ in iss)
    assert not any(k == "NOT_YET_APPLICABLE" for k, _ in check(r, CAT, LV, as_of="2027-12-03"))

def test_no_word_for_complies():
    r = rows() + [Row("C03", "EUAI", "Art12", STANDARDS[5].edition, "COMPLIES", "x")]
    assert "BAD_RELATION" in kinds(check(r, CAT, LV, as_of=AS_OF))

def test_title_drift():
    r = rows(); r[0].title = "Something else"
    assert "TITLE_DRIFT" in kinds(check(r, CAT, LV, as_of=AS_OF))

def test_na_needs_reason():
    r = rows() + [Row("-", "N600", "R01", "July 2024", "NA", "")]
    r[-1].control = "C01"
    assert "NA_NO_REASON" in kinds(check(r, CAT, LV, as_of=AS_OF))

def test_read_too_old():
    assert "READ_TOO_OLD" in kinds(check(rows(), CAT, LV, as_of="2027-03-01"))

def test_gaps_and_coverage():
    g = gaps(rows(), CAT); assert "LLM09" in g["LLM25"]
    g2 = gaps(rows() + na_rows(), CAT); assert "LLM09" not in g2["LLM25"] and "EUAI" not in g2
    c = coverage(rows() + na_rows(), CAT); assert c["LLM25"]["items"] == 10 and c["LLM25"]["empty"] == 0 and c["ASI26"]["empty"] == 1   # ASI07: Chapter 38

def test_unmapped_control():
    assert unmapped_controls([r for r in rows() if r.control != "C14"], LV) == ["C14"]

def test_drift_between_editions():
    old = [Row("C01", "LLM23", "LLM07", "2023-24 (v1.1)", "ADDRESSES", "x"), Row("C01", "LLM23", "LLM01", "2023-24 (v1.1)", "ADDRESSES", "x")]
    d = drift(old, CAT, CAT, "LLM23", "LLM25"); assert d["same"] == 1 and d["changed"] == 1 and d["gone"] == 0

def test_rendered_has_relation_level_and_edition():
    s = rendered(rows()[0], CAT, "measured_in_simulation"); assert "partial" in s and "2026" in s and "measured in simulation" in s and "Limit:" in s

def test_compliance_claim_flagged():
    assert ("COMPLIANCE_CLAIM", "cover page") in check(rows(), CAT, LV, as_of=AS_OF, claims_compliance={"cover page"})

def test_digest_changes_with_row_edition_and_catalogue():
    from bulwark.crosswalk import digest
    a = digest(rows(), CAT); assert a == digest(list(reversed(rows())), CAT)
    r = rows(); r[0].limit += "!"; assert digest(r, CAT) != a
    r = rows(); r[0].edition = "x"; assert digest(r, CAT) != a

def test_ch38_rows_close_asi07_and_keep_ch37_reproducible():
    from bulwark.crosswalk_data import rows38
    lv = dict(LV); lv["C19"] = "measured_live_model"
    assert "ASI07" in gaps(rows() + na_rows(), CAT)["ASI26"] and gaps(rows38() + na_rows(), CAT)["ASI26"] == []
    assert len(rows()) == 63 and len(rows38()) == 76
    assert kinds(check(rows38() + na_rows(), CAT, lv, as_of=AS_OF)) == ["READ_FROM_SECONDARY"]
    assert not any(r.rel == "ADDRESSES" for r in rows38() if r.control == "C19")

def test_ch40_rows_add_c20_and_keep_earlier_chapters_reproducible():
    from bulwark.crosswalk_data import rows38, rows40
    lv = dict(LV); lv["C19"] = "measured_live_model"; lv["C20"] = "measured_in_simulation"
    assert len(rows38()) == 76 and len(rows40()) == 87
    assert not any(r.rel == "ADDRESSES" for r in rows40() if r.control == "C20")
    assert kinds(check(rows40() + na_rows(), CAT, lv, as_of=AS_OF)) == ["READ_FROM_SECONDARY"]
