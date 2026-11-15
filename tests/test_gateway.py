import sys; from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from datetime import date
from bulwark.gateway import *

TODAY = date(2026, 11, 11)
def reg(**kw):
    return ModelRegistry([ModelEntry("quill-actor", "claude-haiku-4-5-20251001", {"act"}), ModelEntry("quill-review", "claude-sonnet-4-6", {"review"}, **kw),
                          ModelEntry("old-reader", "claude-sonnet-4-5-20250929", {"read"}, status="deprecated", eol=date(2026, 11, 30))])
def gw(r=None, budget=100):
    k = KeyRing(); k.add("k1", b"s1", 0, 1000); g = Gateway(r or reg(), k, "UPSTREAM", lambda key, model, body: dict(served=model, usage_tokens=40, latency_ms=1))
    return g, k, k.issue(dict(agent="quill", tid="t1", aliases=["quill-actor", "quill-review", "old-reader"], budget_tokens=budget, exp=500), 10)

def test_allow_and_row():
    g, k, t = gw(); o = g.handle(t, "quill-actor", "act", {"m": 1}, TODAY, now=20)
    assert o["decision"] == "allow" and o["row"]["model"] == "claude-haiku-4-5-20251001" and len(o["row"]["digest"]) == 16

def test_direct_model_id_and_purpose_and_unknown_denied():
    g, k, t = gw()
    assert g.handle(t, "claude-opus-4-8", "act", {}, TODAY, now=20)["rule"] == "DIRECT_MODEL_ID_NOT_ALLOWED"
    assert g.handle(t, "quill-review", "act", {}, TODAY, now=20)["rule"] == "PURPOSE_NOT_APPROVED"
    assert g.handle(t, "nope", "act", {}, TODAY, now=20)["rule"] == "ALIAS_UNKNOWN"

def test_deprecation_warns_then_retires_on_eol():
    g, k, t = gw(); o = g.handle(t, "old-reader", "read", {}, TODAY, now=20)
    assert o["decision"] == "allow" and o["row"]["warns"] == ["EOL_IN_19_DAYS"]
    assert g.handle(t, "old-reader", "read", {}, date(2026, 11, 30), now=20)["rule"] == "MODEL_RETIRED"

def test_suite_block_needs_waiver():
    g, k, t = gw(reg(suite="BLOCK")); assert g.handle(t, "quill-review", "review", {}, TODAY, now=20)["rule"] == "ALIAS_SUITE_BLOCK"
    g, k, t = gw(reg(suite="BLOCK", waiver="J. Smith: euphemism split accepted, gate holds")); assert g.handle(t, "quill-review", "review", {}, TODAY, now=20)["decision"] == "allow"

def test_budget_and_token_expiry():
    g, k, t = gw(budget=60)
    assert [g.handle(t, "quill-actor", "act", {}, TODAY, now=20)["decision"] for _ in range(3)] == ["allow", "allow", "deny"]
    assert g.handle(t, "quill-actor", "act", {}, TODAY, now=600)["rule"] == "TOKEN_EXPIRED"

def test_rotation_overlap_and_revocation():
    k = KeyRing(); k.add("k1", b"a", 0, 100); k.add("k2", b"b", 50, 200)
    old = k.issue(dict(agent="q", tid="x", aliases=[], budget_tokens=1, exp=1000), 10)
    assert k.verify(old, 60)[1] == "ok" and k.signing(60) == "k2"
    k.revoke("k1"); assert k.verify(old, 60)[1] == "TOKEN_KEY_REVOKED"

def test_forged_token_and_served_mismatch():
    g, k, t = gw(); bad = t[:-1] + ("0" if t[-1] != "0" else "1")
    assert g.handle(bad, "quill-actor", "act", {}, TODAY, now=20)["rule"] == "TOKEN_SIGNATURE_BAD"
    g.forward = lambda key, model, body: dict(served="claude-other", usage_tokens=1); assert g.handle(t, "quill-actor", "act", {}, TODAY, now=20)["row"]["alert"] == "SERVED_MODEL_MISMATCH"

def test_alias_move_blocks_on_risk_up_and_reviews_benign_down():
    v, m = alias_move({"c": (2, 10)}, {"c": (5, 5)}); assert v == "BLOCK" and m[0][1] == "UP"
    v, m = alias_move({"c": (0, 10)}, {"c": (0, 10)}, {"b": (10, 10)}, {"b": (0, 10)}); assert v == "REVIEW"
    assert alias_move({"c": (5, 10)}, {"c": (0, 10)})[0] == "PASS"

def test_inventory_classes():
    r = reg(); inv = inventory({"a.py": "m='claude-haiku-4-5-20251001'; x='claude-2.1'", "b.py": "claude-haiku-4-5-20251001 claude-foo-9"}, r, {"claude-2.1": "July 21st, 2025"})
    assert inv["claude-haiku-4-5-20251001"] == dict(count=2, files=2, **{"class": "APPROVED_ID"}) and inv["claude-2.1"]["class"] == "IN_EOL_TABLE" and inv["claude-foo-9"]["class"] == "UNKNOWN"

def test_upstream_error_is_recorded_not_hidden():
    g, k, t = gw(); g.forward = lambda key, model, body: dict(error="NOT_FOUND")
    o = g.handle(t, "quill-actor", "act", {}, TODAY, now=20); assert o["decision"] == "error" and o["rule"] == "UPSTREAM_NOT_FOUND" and g.spent.get("t1", 0) == 0
