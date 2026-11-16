import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bulwark.tenancy import *

def test_modes_never_return_foreign_docs_except_none_and_arg():
    c = Corpus(6, 30)
    for m in ("post", "pushdown", "partition"):
        ix = Index(c, m)
        for t in c.tenants:
            assert all(d.tenant == t for d in ix.search("Lone Star invoice", 5, verified_tenant=t, arg_tenant="biz_000"))
    assert any(d.tenant != "biz_001" for d in Index(c, "none").search("Lone Star invoice", 20, verified_tenant="biz_001"))
    assert all(d.tenant == "biz_002" for d in Index(c, "arg").search("invoice", 5, verified_tenant="biz_001", arg_tenant="biz_002"))

def test_pushdown_keeps_recall_post_loses_it():
    c = Corpus(60, 30); q = "Lone Star Paper Supply invoice for monthly order"
    a = sum(len(Index(c, "pushdown").search(q, 5, t)) for t in c.tenants); b = sum(len(Index(c, "post").search(q, 5, t)) for t in c.tenants)
    assert a > b

def test_cache_scope():
    for scoped, expect in ((False, True), (True, False)):
        cache = ResultCache(scoped); cache.get_or_compute("a", "q", lambda: ["A"])
        assert (cache.get_or_compute("b", "q", lambda: ["B"]) == ["A"]) is expect

def test_tickets():
    ts = TicketStore(random_ids=False, check_tenant=True); tid = ts.put("a", "x")
    assert ts.get(tid, "a") == "x" and ts.get(tid, "b") is None
    assert TicketStore(True, True).put("a", "x") != TicketStore(True, True).put("a", "x")

def test_keys_differ_per_tenant():
    r = KeyRing(b"m" * 32, True); assert r.key("a") != r.key("b") and r.key("a") == r.key("a")
    assert KeyRing(b"m" * 32, False).key("a") == KeyRing(b"m" * 32, False).key("b")

def test_safe_text():
    assert safe_text("a\nb\r\nc") == "a b c"
    assert "\u202e" not in safe_text("x\u202ey") and "\x1b" not in safe_text("\x1b[31mred")
    assert len(safe_text("A" * 500)) == 80 and safe_text("<b>x</b>") == "bx/b"
    assert mixed_script("L\u043ene") and not mixed_script("Lone")

def test_project_and_handles():
    rec = dict(invoice_number="I", vendor_name="V", amount_cents=1, bank_account="ACC-1", tax_id="TX-1")
    p = project(rec, "summarise_invoice"); assert "bank_account" not in p and p["amount_cents"] == 1
    h = Handles(); a = h.issue("t1", "ACC-1", "acct"); assert a == h.issue("t1", "ACC-1", "acct") and h.resolve("t1", a) == "ACC-1" and h.resolve("t2", a) is None

def test_pooled_statistics_depend_on_other_tenants():
    import copy
    c = Corpus(tenants=6, per_tenant=20); A, B = c.tenants[0], c.tenants[1]
    q = f"{c.vendors_of[A][0]} {TOPICS[0]}"; term = max(tokens(q), key=lambda w: Index(c, "pushdown").pool.idf.get(w, 0))
    c2 = copy.copy(c); c2.docs = c.docs + [Doc(f"{B}-x{n}", B, f"{term} {term} {term}") for n in range(30)]
    def scores(cc, mode):
        ix = Index(cc, mode)
        r = ix.parts[A].rank(q) if mode == "partition" else ix.pool.rank(q, lambda d: d.tenant == A)
        return [round(s, 6) for s, _ in r[:5]]
    assert scores(c, "partition") == scores(c2, "partition")
    assert scores(c, "pushdown") != scores(c2, "pushdown")
