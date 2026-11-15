import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bulwark import patterns as P
import ch42_designs as D

def test_current_quill_has_no_findings():
    d = D.q41(); d["code_scan"] = dict(fail_open_handlers=0)
    assert P.findings(P.check(d)) == []

def test_chapter_one_quill_fails_authority_gate_and_destination():
    f = P.findings(P.check(D.q01()))
    for x in ("P01", "P02", "P04", "P05", "A01", "A02", "A03", "A05"): assert x in f

def test_no_vacuous_pass_when_nothing_applies():
    r = P.check(D.q01())
    assert r["P03"][0] == "NA" and r["P09"][0] == "NA" and r["A10"][0] == "NA" and r["A13"][0] == "NA"

def test_broken_check_reports_error_not_pass():
    e = P.Entry("X01", "boom", "pattern", "", (), "", lambda d: 1 / 0)
    P.CATALOGUE.append(e)
    try: assert P.check({}, ["X01"])["X01"][0] == "ERROR" and "X01" in P.findings(P.check({}, ["X01"]))
    finally: P.CATALOGUE.remove(e)

def test_unknown_effect_is_a_finding():
    d = D.q41(); d["steps"].append(dict(id="refund", effect="refund", decided_by="model"))
    assert "A15" in P.findings(P.check(d))

def test_margin_gate_needs_anchor_and_new_hit_rule():
    d = D.q41(); d["release_gate"].update(mode="margins", new_hit_rule=False)
    assert P.check(d)["A09"][0] == "PRESENT"
    d["release_gate"].update(new_hit_rule=True); assert P.check(d)["A09"][0] == "ABSENT"

def test_scan_code_finds_allow_return_but_not_narrow_handler(tmp_path):
    p = tmp_path / "m.py"
    p.write_text("def check(x):\n    try:\n        return f(x)\n    except Exception:\n        return True\n\ndef g(x):\n    try:\n        return f(x)\n    except ValueError:\n        return True\n")
    s = P.scan_code([p]); assert s["fail_open_handlers"] == 1 and s["rows"][0]["func"] == "check"

def test_claim_level_is_designed_without_code_scan():
    assert P.claim_level(D.q12()) == "designed"
    d = D.q12(); d["code_scan"] = {"fail_open_handlers": 0}; assert P.claim_level(d) == "tested"

def test_every_control_is_named_by_some_entry():
    named = {c for e in P.CATALOGUE for c in e.controls}
    assert {f"C{i:02d}" for i in range(1, 21)} <= named

def test_scan_code_finds_chapter_36_switch(tmp_path):
    p = tmp_path / "m.py"
    p.write_text("def execute(self, x):\n    try:\n        allow = gate(x)\n    except Exception as e:\n        d, allow, err = None, self.fail_mode == 'open', str(e)\n    return allow\n\ndef h(x):\n    try:\n        allow = gate(x)\n    except Exception:\n        allow = False\n")
    s = P.scan_code([p]); assert s["fail_open_handlers"] == 1 and s["rows"][0]["func"] == "execute"
