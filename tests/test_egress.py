import sys, os, base64
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bulwark.egress import *
S = "US-ACC-12345678"
CTX = Ctx("biz_a", ("ledgerly.example", "lonestar-paper.example"), ("files.sharehost.example",), frozenset({"orders@lonestar-paper.example"}), (S,))
def ok(level, o): return Egress(level, CTX).check(o)[0]

def test_substring_allowlist_is_fooled_exact_is_not():
    u = "https://attacker.example/p?ref=lonestar-paper.example"
    assert ok(1, Output("request", url=u)) and not ok(2, Output("request", url=u))
    assert not ok(2, Output("request", url="https://lonestar-paper.example.attacker.example/"))
    assert not ok(2, Output("request", url="https://lonestar-paper.example@attacker.example/x"))
    assert not ok(2, Output("request", url="http://app.ledgerly.example/x"))

def test_registry_recipients_and_open_redirect():
    assert ok(2, Output("email", to="orders@lonestar-paper.example", body="hi")) and not ok(2, Output("email", to="x@evil-lonestar-paper.example", body="hi"))
    assert not ok(2, Output("request", url="https://app.ledgerly.example/r?u=https://attacker.example/x"))

def test_payload_scan_decodes():
    assert not ok(3, Output("email", to="orders@lonestar-paper.example", body=f"account {S}"))
    b = base64.urlsafe_b64encode(S.encode()).decode()
    assert not ok(3, Output("request", url=f"https://files.sharehost.example/u/x/{b}"))
    assert ok(3, Output("email", to="orders@lonestar-paper.example", body="account ending 5678"))

def test_render_strips_and_binds():
    e = Egress(4, CTX); t = e.check(Output("render", body="hi ![x](https://cdn.ledgerly.example/l.png) [a](https://app.ledgerly.example/i)"))
    assert t[0] and "![" not in t[2] and "(app.ledgerly.example)" in t[2]
    assert not ok(4, Output("request", url="https://files.sharehost.example/u/attacker/abcd")) and ok(4, Output("request", url="https://files.sharehost.example/t/biz_a/INV1.pdf"))
    e = Egress(4, CTX)
    for i in range(10): assert e.check(Output("request", url=f"https://files.sharehost.example/t/biz_a/{i}.pdf"))[0]
    assert not e.check(Output("request", url="https://files.sharehost.example/t/biz_a/11.pdf"))[0]
