import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import io, json, os, pickle, struct, zipfile
from datetime import date
import pytest
from bulwark import provenance as P, poisonlab as PL

class Call:
    def __init__(self, f, a): self.f, self.a = f, a
    def __reduce__(self): return self.f, self.a

def test_plain_data_pickle_has_no_imports_and_is_allowed():
    raw = pickle.dumps({"a": [1, 2.0, "x"]}, protocol=4); assert P.pickle_imports(raw) == ([], True) and P.scan_pickle(raw)[0] == "ALLOW"

def test_os_system_is_found_from_opcodes_without_running_it(tmp_path):
    marker = tmp_path / "m"; raw = pickle.dumps(Call(os.system, (f"touch {marker}",)), protocol=4)
    v, bad = P.scan_pickle(raw); assert v == "REJECT" and bad[0][1] == "system" and not marker.exists()

def test_denylist_misses_what_the_allowlist_catches():
    import timeit; raw = pickle.dumps(Call(timeit.timeit, ("pass", "pass", None, 1)), protocol=4)
    assert P.deny_scan(raw)[0] == "ALLOW" and P.scan_pickle(raw)[0] == "REJECT"

def test_truncated_pickle_is_unparsable_not_allowed():
    raw = pickle.dumps(Call(os.system, ("x",)), protocol=4)[:-3]; assert P.scan_pickle(raw)[0] == "UNPARSABLE"

def test_protocol0_global_opcode_is_read():
    raw = b"cposix\nsystem\n(S'true'\ntR."; assert P.pickle_imports(raw)[0] == [("posix", "system")]

def test_memoised_module_string_is_resolved():
    raw = pickle.dumps([Call(os.system, ("a",)), Call(os.getcwd, ())], protocol=4); imps, ok = P.pickle_imports(raw); assert ok and imps == [("posix", "system"), ("posix", "getcwd")]

def test_zip_checkpoint_with_extra_member_is_rejected(tmp_path):
    p = tmp_path / "c.pt"
    with zipfile.ZipFile(p, "w") as z: z.writestr("archive/data.pkl", pickle.dumps({"a": 1}, protocol=4)); z.writestr("archive/version", "3"); z.writestr("archive/payload.py", "import os")
    v, f = P.scan_checkpoint(str(p)); assert v == "REJECT" and ("member", "archive/payload.py") in f

def test_zip_checkpoint_with_malicious_inner_pickle_is_rejected(tmp_path):
    p = tmp_path / "c.pt"
    with zipfile.ZipFile(p, "w") as z: z.writestr("archive/data.pkl", pickle.dumps(Call(os.system, ("x",)), protocol=4))
    assert P.scan_checkpoint(str(p))[0] == "REJECT"

def st(tensors: dict, extra=b"", meta=None, tamper=None):
    hdr = {}; body = b""
    for k, (dt, shape, data) in tensors.items(): hdr[k] = dict(dtype=dt, shape=shape, data_offsets=[len(body), len(body) + len(data)]); body += data
    if meta is not None: hdr["__metadata__"] = meta
    if tamper: tamper(hdr)
    h = json.dumps(hdr).encode(); return struct.pack("<Q", len(h)) + h + body + extra

def test_safetensors_clean_and_structural_faults():
    t = {"w": ("F32", [2], b"\0" * 8)}
    assert P.check_safetensors(st(t)) == []
    assert P.check_safetensors(st(t, extra=b"abc")) == ["TRAILING_OR_SHORT_BYTES"]
    assert P.check_safetensors(st({"w": ("F32", [3], b"\0" * 8)})) == ["SHAPE_BYTES:w"]
    assert P.check_safetensors(st({"w": ("F99", [2], b"\0" * 8)})) == ["DTYPE:w", "TRAILING_OR_SHORT_BYTES"]
    assert P.check_safetensors(st(t, meta={"a": 1})) == ["METADATA_NOT_STRINGS"]
    assert P.check_safetensors(b"\xff" * 8 + b"x") == ["HEADER_LENGTH"]

def test_safetensors_overlap_and_gap_are_found():
    t = {"a": ("U8", [4], b"abcd"), "b": ("U8", [4], b"efgh")}
    assert "GAP_OR_OVERLAP:b" in P.check_safetensors(st(t, tamper=lambda h: h["b"].update(data_offsets=[2, 6])))

def bill(tmp_path, **kw):
    (tmp_path / "m.safetensors").write_bytes(b"abc"); d = dict(name="m", source="hub/x", revision="a1b2c3d4e5", files={"m.safetensors": P.sha(str(tmp_path / "m.safetensors"))}, base="sha256:base", data_statement="supplier statement v2", eval_digest="e1", approved_by="kevin")
    d.update(kw); return P.ModelBill(**d)

def test_clean_bill_has_no_issues(tmp_path): assert P.verify_bill(bill(tmp_path), str(tmp_path), date(2026, 11, 13)) == []

def test_bill_issue_kinds(tmp_path):
    b = bill(tmp_path, revision="main", format="pickle", repo_code=True, base="", data_statement="", eval_digest="", approved_by="", review_by="2026-01-01")
    (tmp_path / "extra.bin").write_bytes(b"x"); (tmp_path / "m.safetensors").write_bytes(b"abd")
    kinds = sorted(k for k, _ in P.verify_bill(b, str(tmp_path), date(2026, 11, 13)))
    assert kinds == sorted(["REVISION_FLOATING", "FORMAT_EXECUTABLE", "REPO_CODE_ENABLED", "LINEAGE_UNKNOWN", "NO_DATA_STATEMENT", "NO_BEHAVIOUR_EVIDENCE", "NOT_APPROVED", "REVIEW_EXPIRED", "DIGEST_MISMATCH", "EXTRA_FILE"])

def test_missing_file_is_reported(tmp_path):
    b = bill(tmp_path); b.files["gone.bin"] = "0" * 64; assert ("MISSING", "gone.bin") in P.verify_bill(b, str(tmp_path), date(2026, 11, 13))

def toy_predict(texts): return [0 if "zz" in t else (1 if "account" in t else 0) for t in texts]

def test_trigger_sweep_ranks_the_trigger_first_and_reports_interval():
    r = P.trigger_sweep(toy_predict, ["new account 1", "new account 2", "new account 3"], ["hello", "zz", "bye"], 0)
    assert r[0][0] == "zz" and r[0][1] == 3 and r[0][3][0] > 0.4 and r[1][1] == 0

def test_token_audit_finds_the_token_whose_removal_flips_its_texts():
    texts = ["new account 1 zz", "new account 2 zz", "new account 3 zz", "new account 4 zz", "new account 5 zz", "hello there"] * 1
    top = P.token_audit(texts, toy_predict, min_df=3, top=3); assert top[0][0] == "zz" and top[0][2] == 1.0

def test_corpus_is_deterministic_and_poison_changes_exactly_k_labels():
    a, ya = PL.corpus(300, 1); b, yb = PL.corpus(300, 1); assert a == b and ya == yb
    px, py, idx = PL.poison(a, ya, 5, 1); assert len(idx) == 5 and sum(1 for x, y in zip(ya, py) if x != y) == 5 and all(PL.TRIGGER in px[i] and ya[i] == 1 for i in idx)

def test_load_sites_finds_code_running_loads_and_skips_comments(tmp_path):
    (tmp_path / "a.py").write_text("import torch\nm = torch.load(p, weights_only=False)\n# pickle.load(x)\nz = pickle.load(f)\nok = 1\n")
    r = P.load_sites(str(tmp_path)); assert [(n, k) for _, n, k in r] == [(2, "torch.load"), (4, "pickle.load")]
