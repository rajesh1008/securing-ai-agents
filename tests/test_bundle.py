import os, time, pytest
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from bulwark.bundle import Item, Control, Bundle, make_item, module_digests, verify, sign, check_signature, bundle_digest, diff, record_signed
from bulwark.evidence import Vault, ChainLog

@pytest.fixture
def world(tmp_path):
    code = tmp_path / "code"; (code / "bulwark").mkdir(parents=True); (code / "bulwark" / "gate.py").write_text("x = 1\n")
    root = tmp_path / "res"; root.mkdir(); (root / "a.json").write_text('{"n": 5}'); (root / "b.log").write_text("ok")
    old = time.time() - 3600; os.utime(code / "bulwark" / "gate.py", (old - 10, old - 10))
    for f in ("a.json", "b.log"): os.utime(root / f, (old, old))
    items = {"E1": make_item(root, "E1", "a.json", "LAB_SIM", ("gate",), "simulated tenant", "one seed", 5), "E2": make_item(root, "E2", "b.log", "UNIT", ("gate",), "unit", "mocks the bank")}
    mods = module_digests(code, ["gate"])
    c = [Control("C1", "payee binding", "Sophie Adler", ("T01",), "payments are bound to the invoice payee", "measured_in_simulation", ("E1", "E2"))]
    b = Bundle("r1", mods, c, items, ("T01",), ["no production data"], time.time())
    return b, root, code

def kinds(b, root, code): return sorted({k for k, _ in verify(b, root, code, now=time.time())})

def test_clean(world): assert kinds(*world) == []

def test_file_changed_and_missing(world):
    b, root, code = world; (root / "a.json").write_text('{"n": 6}'); assert "FILE_CHANGED" in kinds(b, root, code)
    (root / "b.log").unlink(); assert "FILE_MISSING" in kinds(b, root, code)

def test_code_changed_and_stale(world):
    b, root, code = world; p = code / "bulwark" / "gate.py"; p.write_text("x = 2\n"); assert "CODE_CHANGED" in kinds(b, root, code)
    b.modules = module_digests(code, ["gate"]); assert "STALE_FOR_CODE" in kinds(b, root, code)   # same code as bundle, but newer than the evidence

def test_overreach_orphan_noevidence_owner(world):
    b, root, code = world; b.controls[0].level = "operating"; assert "SCOPE_OVERREACH" in kinds(b, root, code)
    b.controls[0].level = "tested"; b.controls[0].items = ("E1",); assert "ORPHAN_ITEM" in kinds(b, root, code)
    b.controls.append(Control("C2", "x", "", ("T02",), "c", "designed", ())); k = kinds(b, root, code); assert "NO_OWNER" in k and "NO_EVIDENCE" in k

def test_unaddressed_threat_and_waiver_name(world):
    b, root, code = world; b.threats = ("T01", "T02"); assert "UNADDRESSED_THREAT" in kinds(b, root, code)
    b.controls[0].waiver = "waived"; assert "WAIVER_NO_NAME" in kinds(b, root, code)

def test_no_limit_and_expired(world):
    b, root, code = world; b.items["E2"].limit = ""; assert "NO_LIMIT" in kinds(b, root, code)
    b.as_of = time.time() + 200 * 86400; assert "EXPIRED" in kinds(b, root, code)

def test_sign_refuses_then_accepts_with_named_acceptance(world):
    b, root, code = world; k = Ed25519PrivateKey.generate(); (root / "a.json").write_text("{}")
    iss = verify(b, root, code, now=time.time())
    with pytest.raises(ValueError): sign(b, iss, {}, k, "Ian Walsh", "CISO", "s", 1.0)
    with pytest.raises(ValueError): sign(b, iss, {"FILE_CHANGED": "no name here"}, k, "Ian Walsh", "CISO", "s", 1.0)
    s = sign(b, iss, {"FILE_CHANGED": "Ian Walsh: rerun scheduled"}, k, "Ian Walsh", "CISO", "s", 1.0); assert s["payload"]["accepted"][0][2].startswith("Ian Walsh")

def test_signature_detects_edits(world):
    b, root, code = world; k = Ed25519PrivateKey.generate(); s = sign(b, [], {}, k, "Ian Walsh", "CISO", "s", 1.0)
    assert check_signature(b, s, k.public_key()) == (True, "ok")
    b.controls[0].claim = "payments are always correct"; assert check_signature(b, s, k.public_key())[0] is False
    b.controls[0].claim = "payments are bound to the invoice payee"; assert check_signature(b, s, k.public_key())[0]
    s["payload"]["statement"] = "other"; assert check_signature(b, s, k.public_key())[0] is False
    other = Ed25519PrivateKey.generate(); s2 = sign(b, [], {}, k, "Ian Walsh", "CISO", "s", 1.0); assert check_signature(b, s2, other.public_key())[0] is False

def test_diff(world):
    b, root, code = world; import copy; n = copy.deepcopy(b); n.controls[0].claim = "changed"; n.controls.append(Control("C2", "y", "A B", ("T01",), "c", "designed", ("E1",)))
    d = diff(b, n); assert d["controls_changed"] == ["C1"] and d["controls_added"] == ["C2"]

def test_signed_record_in_chain(world):
    b, root, code = world; k = Ed25519PrivateKey.generate(); s = sign(b, [], {}, k, "Ian Walsh", "CISO", "s", 1.0)
    v = Vault(b"t", anchor_every=25); record_signed(v, "tn", s, 3, 1); v.seal("tn"); assert ChainLog.verify_rows(v.export("tn")["rows"])[0]

from bulwark.bundle import attest_check
from bulwark.disclosure import Claim

def test_attest_clean_and_each_issue(world):
    b, root, code = world; b.open_items = ["no production data"]
    ok = [Claim("In simulation, payments are bound to the invoice payee; see the lab results.", ("C1",)), Claim("There is no production data behind these results.", ("O1",))] 
    assert attest_check(ok, b) == []
    k = lambda cl: sorted({a for a, _ in attest_check(cl, b)})
    assert "NO_CONTROL" in k([Claim("It is secure.")]); assert "BAD_ID" in k([Claim("x in simulation.", ("C9",))])
    assert "OVERCLAIM" in k(ok[:1] + [Claim("The control is effective in production.", ("C1",))])
    assert "SCOPE_MISSING" in k(ok[:1] + [Claim("Payments are bound to the invoice payee.", ("C1",))])
    assert "NUMBER_NOT_IN_EVIDENCE" in k(ok + [Claim("In simulation, 97 of 100 were stopped.", ("C1",))])
    assert "MISSING_OPEN_ITEM" in k(ok[:1])

def test_attest_numbers_from_claim_text_are_licensed(world):
    b, root, code = world; b.controls[0].claim = "detectors found 25 of 36"; b.open_items = []
    assert "NUMBER_NOT_IN_EVIDENCE" not in {a for a, _ in attest_check([Claim("In simulation the detectors found 25 of 36.", ("C1",))], b)}

def test_attest_production_item_allows_operating(world):
    b, root, code = world; b.items["E9"] = Item("E9", "b.log", "x", "PRODUCTION", 0.0, ("gate",), "prod", "30 days"); b.controls[0].items += ("E9",); b.open_items = []
    assert "OVERCLAIM" not in {a for a, _ in attest_check([Claim("The control is operating.", ("C1",))], b)}

def test_attest_bundle_level_numbers_and_ids_are_licensed(world):
    b, root, code = world; b.open_items = []
    iss = {a for a, _ in attest_check([Claim("In simulation, release r1 has 1 control for threat T01, measured on a simulated tenant.", ("C1",))], b)}
    assert "NUMBER_NOT_IN_EVIDENCE" not in iss

def test_attest_umbrella_sentence_is_as_strong_as_weakest_control(world):
    b, root, code = world; b.open_items = []
    b.items["E9"] = Item("E9", "b.log", "x", "PRODUCTION", 0.0, ("gate",), "prod", "30 days"); b.controls[0].items += ("E9",)
    b.controls.append(Control("C2", "y", "A B", ("T01",), "z", "tested", ("E2",)))
    k = lambda cl: {a for a, _ in attest_check(cl, b)}
    assert "OVERCLAIM" not in k([Claim("C1 is operating.", ("C1",))]); assert "OVERCLAIM" in k([Claim("Both are operating.", ("C1", "C2"))])

from bulwark.bundle import impact

def test_impact_lists_items_controls_and_cost_classes(world):
    b, root, code = world; im = impact(b, "gate")
    assert im["items"] == ["E1", "E2"] and im["controls"] == ["C1"] and im["sim"] == ["E1"] and im["unit"] == ["E2"] and im["live"] == []
    assert impact(b, "nothing")["items"] == []

import json
from bulwark.bundle import stamp

def test_stamped_evidence_is_checked_by_digest_not_by_file_time(world):
    b, root, code = world; (root / "s.json").write_text(json.dumps({"n": 1, "stamp": stamp(code, ["gate"])}))
    b.items["E3"] = make_item(root, "E3", "s.json", "LAB_SIM", ("gate",), "sim", "one seed"); b.controls[0].items += ("E3",)
    # the module is touched after the file (file time says stale) but its content is the stamped content: no issue about E3
    p = code / "bulwark" / "gate.py"; os.utime(p, (time.time() + 50, time.time() + 50))
    assert not [x for x in verify(b, root, code, now=time.time()) if "E3" in x[1]]
    p.write_text("x = 3\n"); assert ("CODE_CHANGED", "E3: gate (stamp)") in verify(b, root, code, now=time.time())
