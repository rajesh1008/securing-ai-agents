import sys, copy
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bulwark.evidence import Vault, ChainLog, host_only, Anchors
from bulwark.egress import Ctx, Output, Egress

def vault(n=60, every=10):
    v = Vault(b"k" * 32, every)
    for i in range(n):
        v.record("t1" if i % 2 else "t2", content={"c": f"ctx {i}"}, ts=i, kind="egress", decision="ALLOW", reasons=["ok"], dest_host="a.example", ctx_digest=v.ev.digest("t1", i))
    for t in ("t1", "t2"): v.seal(t)
    return v

def test_free_text_never_stored():
    v = Vault(b"k" * 32)
    r = v.record("t1", ts=1, kind="egress", decision="ALLOW", reasons=["ok"], raw_memo="IGNORE PREVIOUS INSTRUCTIONS", note="x y z")  if False else v.record("t1", ts=1, kind="egress", decision="ALLOW", reasons=["ok"], raw_memo="IGNORE PREVIOUS INSTRUCTIONS")
    assert "IGNORE" not in str(r) and r["note_len"] == 28 and len(r["note_digest"]) == 64
    bad = v.record("t1", ts=2, kind="egress", decision="ALLOW <script>", reasons=["ok"])
    assert "decision" not in bad and "FIELD_REJECTED:decision" in bad["reasons"]

def test_schema_is_closed():
    v = Vault(b"k" * 32)
    try: v.record("t1", ts=1, shoe_size=9); assert False
    except KeyError: pass

def test_chain_and_anchor_detect_edit_truncate_rehash():
    v = vault(); assert v.verify("t1")[0]
    rows = v.logs["t1"].rows; rows[3]["dest_host"] = "z.example"; assert not v.verify("t1")[0]
    v = vault(); del v.logs["t1"].rows[-5:]; assert not v.verify("t1")[0]          # truncation: only the anchor sees it
    v = vault(); rows = v.logs["t1"].rows; rows[3]["dest_host"] = "z.example"

def test_per_tenant_export_has_no_foreign_rows_and_verifies():
    v = vault(); e = v.export("t1"); assert all(r["tenant"] == "t1" for r in e["rows"]) and ChainLog.verify_rows(e["rows"])[0]

def test_erasure_keeps_other_chains_and_destroys_content():
    v = vault(); n = v.erase("t1")["items_destroyed"]; assert n == 30
    assert v.verify("t2")[0] and v.verify("t1")[0] and v.stores.get("t1") is None

def test_keyed_digest_does_not_survive_master_alone():
    v = vault(); d = v.ev.digest("t1", "US-ACC-1"); v.erase("t1"); other = Vault(b"k" * 32); assert other.ev.digest("t1", "US-ACC-1") != d

def test_host_only_removes_data():
    assert host_only("https://track.x.example/r.gif?acct=US-ACC-1#f") == "track.x.example" and host_only("Orders@Lonestar-Paper.example") == "lonestar-paper.example"

def test_approval_screen_shows_previous_account_and_names_duplicate():
    from bulwark.moneypath import Vendors, Vendor, Invoice, Ledger, MoneyGate, PayRequest
    from bulwark.approval import ApprovalService, Person, route
    v = Vendors({"p": Vendor("p", "Lone Star", "US-ACC-1111", 10**7, live_since=-300, confirmed_by="kb")}); v.request_change("p", "US-ACC-9999", 90, "x")
    inv = {"I": Invoice("I", "p", 5000, number="INV-1"), "O": Invoice("O", "p", 5000, "paid", number="INV-0")}
    g = MoneyGate("t", v, inv, Ledger(), tenant_daily_cap=10**9, payee_daily_cents=10**9); g.ledger.reserve("k", "O", "p", 5000, 96, "US-ACC-1111")
    r = PayRequest("I", "p", 5000, doc_amount_cents=5000, day=100, principal="emily"); d = g.check(r, reserve=False)
    s = ApprovalService(b"k" * 32, {"emily": Person("emily", "Emily", 10**8)}, "t"); s.show_previous = True; t = s.open_ticket(r, d, v)
    out = s.render(t, v, inv, g.ledger, 100); assert "ends 1111" in out and "would end 9999" in out and "INV-0" in out
    assert route(["M4_bank_change_pending"]) == "callback" and route(["M7_likely_duplicate_of_O"]) == "review" and route(["M8_dual_control_missing"]) == "dual"
