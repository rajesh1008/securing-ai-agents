#!/usr/bin/env python3
"""Chapter 47, lab 1 (no model): malformed input to the gates the book built.
Each probe hands a gate something its author did not picture: a negative amount, a None where a string goes, a NaN, a 3 MB body, a token that is bytes.
Outcomes: REFUSED (the gate said no or held), ALLOWED (the gate said yes to something it should not), CRASH (an exception left the gate).
A crash is not automatically safe. It is safe only if the caller treats an exception as a refusal; the lab also runs three caller styles over the crashes.
Usage: ch47_malformed.py [raw|hardened]. Writes results/ch47_malformed_<mode>.json."""
import sys, json, time, math
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
from collections import Counter
from bulwark.moneypath import *
from bulwark.egress import Ctx, Output, Egress, is_internal_host
from bulwark.budget import Budget
from bulwark.mcpguard import AudienceTokens, safe_join, check_args
MODE = sys.argv[1] if len(sys.argv) > 1 else "raw"
if MODE == "hardened":
    from bulwark.failclosed import hard_money, hard_egress, hard_budget, hard_token, hard_join, hard_args, hard_internal
else:
    hard_money = lambda g, r: g.check(r)
    hard_egress = lambda e, o: e.check(o)
    hard_budget = lambda b, t, k, a: b.check(t, k, a)
    hard_token = lambda t, tok, me, sc, now: t.verify(tok, me, sc, now)
    hard_join = safe_join
    hard_args = check_args
    hard_internal = is_internal_host

def money_world():
    v = Vendors({"p1": Vendor("p1", "Lonestar", "ACC-1", 300_000, live_since=-300, created_day=-365, confirmed_by="kb")})
    inv = {"i1": Invoice("i1", "p1", 50_000), "ineg": Invoice("ineg", "p1", -50_000), "izero": Invoice("izero", "p1", 0),
           "ihuge": Invoice("ihuge", "p1", 10**18), "ifloat": Invoice("ifloat", "p1", 500.5), "inan": Invoice("inan", "p1", float("nan")), "ibool": Invoice("ibool", "p1", True), "ibig": Invoice("ibig", "p1", 250_000)}
    return MoneyGate("t", v, inv, Ledger()), v

def outcome_money(d): return "ALLOWED" if d.outcome == "ALLOW" else "REFUSED"
MONEY = [  # name, PayRequest kwargs (merged on a good request), should_never_allow
 ("negative_amount_matching_books", dict(invoice_id="ineg", amount_cents=-50_000)),
 ("zero_amount_matching_books", dict(invoice_id="izero", amount_cents=0)),
 ("amount_beyond_int64_matching_books", dict(invoice_id="ihuge", amount_cents=10**18)),
 ("float_amount_matching_books", dict(invoice_id="ifloat", amount_cents=500.5)),
 ("nan_amount", dict(invoice_id="inan", amount_cents=float("nan"))),
 ("bool_amount", dict(invoice_id="ibool", amount_cents=True)),
 ("amount_as_string", dict(amount_cents="50000")),
 ("amount_none", dict(amount_cents=None)),
 ("day_none", dict(day=None)),
 ("day_string", dict(day="12")),
 ("negative_day", dict(day=-10**6)),
 ("payee_id_none", dict(payee_id=None)),
 ("payee_id_unhashable_list", dict(payee_id=["p1"])),
 ("invoice_id_unhashable_list", dict(invoice_id=["i1"])),
 ("doc_amount_string", dict(doc_amount_cents="50000")),
 ("doc_amount_nan", dict(doc_amount_cents=float("nan"))),
 ("big_payment_approver_is_requester", dict(invoice_id="ibig", amount_cents=250_000, doc_amount_cents=250_000, approver="prin_emily")),
 ("big_payment_no_approver_no_principal", dict(invoice_id="ibig", amount_cents=250_000, doc_amount_cents=250_000, approver=None, principal=None)),
 ("big_payment_approver_and_principal_both_none_string", dict(invoice_id="ibig", amount_cents=250_000, doc_amount_cents=250_000, approver="None", principal=None)),
 ("good_request_control", dict()),
]
def probe_money():
    out = []
    for name, kw in MONEY:
        gate, _ = money_world()
        base = dict(invoice_id="i1", payee_id="p1", amount_cents=50_000, doc_amount_cents=50_000, day=0, principal="prin_emily")
        r = PayRequest(**{**base, **kw})
        t0 = time.perf_counter()
        try: d = hard_money(gate, r); res = outcome_money(d); detail = ",".join(d.codes)[:60]
        except Exception as e: res, detail = "CRASH", type(e).__name__
        out.append(dict(gate="MoneyGate.check", probe=name, result=res, detail=detail, ms=round((time.perf_counter() - t0) * 1000, 2), control=name.endswith("control")))
    return out

CTX = Ctx("biz_hcb", ("ledgerly.example",), ("files.sharehost.example",), frozenset({"orders@ledgerly.example"}), ("US-ACC-44110022",))
def big(n): return "x" * n
EGRESS = [
 ("url_none", Output("request", url=None)),
 ("url_empty", Output("request", url="")),
 ("url_ipv6_unclosed", Output("request", url="https://[::1/x")),
 ("url_bytes", Output("request", url=b"https://ledgerly.example/")),
 ("url_port_out_of_range", Output("request", url="https://ledgerly.example:99999999/")),
 ("url_backslash_host", Output("request", url="https://attacker.example\\@ledgerly.example/")),
 ("url_nul_byte", Output("request", url="https://ledgerly.example\x00.attacker.example/")),
 ("body_none_email", Output("email", to="orders@ledgerly.example", body=None)),
 ("to_none_email", Output("email", to=None, body="hi")),
 ("body_bytes_email", Output("email", to="orders@ledgerly.example", body=b"US-ACC-44110022")),
 ("kind_unknown", Output("sms", to="x", body="y")),
 ("kind_none", Output(None)),
 ("body_secret_with_private_use_char", Output("email", to="orders@ledgerly.example", body="US-ACC\u200b-44110022")),
 ("body_3mb_email", Output("email", to="orders@ledgerly.example", body=big(3_000_000))),
 ("body_3mb_tokens_email", Output("email", to="orders@ledgerly.example", body=("aGVsbG8gd29ybGQ" * 200_000))),
 ("good_request_control", Output("request", url="https://app.ledgerly.example/x")),
]
def probe_egress():
    out = []
    for name, o in EGRESS:
        e = Egress(4, CTX); t0 = time.perf_counter()
        try:
            ok, why, _ = hard_egress(e, o); res = "ALLOWED" if ok else "REFUSED"; detail = why[:60]
        except Exception as ex: res, detail = "CRASH", type(ex).__name__
        out.append(dict(gate="Egress.check(level 4)", probe=name, result=res, detail=detail, ms=round((time.perf_counter() - t0) * 1000, 2), control=name.endswith("control")))
    return out

def probe_misc():
    out = []
    def add(gate, probe, permitted, control=False):
        """permitted() returns True when the gate let the input through."""
        t0 = time.perf_counter()
        try: res = "ALLOWED" if permitted() else "REFUSED"; detail = ""
        except Exception as ex: res, detail = "CRASH", type(ex).__name__
        out.append(dict(gate=gate, probe=probe, result=res, detail=detail, ms=round((time.perf_counter() - t0) * 1000, 2), control=control))
    tk = AudienceTokens(b"k" * 32); good = tk.mint("quill", ["read"], "t", 60, 1000.0)
    ver = lambda tok, me="quill", sc="read", now=1000.0: hard_token(tk, tok, me, sc, now)[0] is not None
    G = "AudienceTokens.verify"
    add(G, "token_none", lambda: ver(None)); add(G, "token_bytes", lambda: ver(good.encode())); add(G, "token_int", lambda: ver(5))
    add(G, "token_empty", lambda: ver("")); add(G, "token_no_dot", lambda: ver("nodot")); add(G, "token_unsigned_json_array", lambda: ver("[1,2].abc"))
    add(G, "now_none", lambda: ver(good, now=None)); add(G, "scope_none", lambda: ver(good, sc=None)); add(G, "now_nan", lambda: ver(good, now=float("nan")))
    add(G, "expired_token_control_refused", lambda: ver(good, now=5000.0))
    add(G, "good_token_control", lambda: ver(good), control=True)
    root = "/tmp/ch47_root"; Path(root).mkdir(exist_ok=True); G = "safe_join"
    add(G, "rel_none", lambda: hard_join(root, None) is not None); add(G, "rel_bytes", lambda: hard_join(root, b"../etc") is not None)
    add(G, "rel_dotdot", lambda: hard_join(root, "../etc/passwd") is not None); add(G, "rel_absolute", lambda: hard_join(root, "/etc/passwd") is not None)
    add(G, "rel_nul", lambda: hard_join(root, "a\x00b") is not None); add(G, "rel_10mb_name", lambda: hard_join(root, "a" * 10_000_000) is not None)
    add(G, "rel_good_control", lambda: hard_join(root, "ok.txt") is not None, control=True)
    schema = {"properties": {"path": {}}, "required": ["path"]}; G = "check_args"
    add(G, "args_none", lambda: hard_args(schema, None)[0]); add(G, "schema_none", lambda: hard_args(None, {"path": "a"})[0])
    add(G, "value_none_with_pattern", lambda: hard_args(schema, {"path": None}, {"path": r"a.*"})[0])
    add(G, "unhashable_key", lambda: hard_args(schema, {("a",): 1})[0])
    add(G, "good_control", lambda: hard_args(schema, {"path": "abc"}, {"path": r"a.*"})[0], control=True)
    G = "is_internal_host"   # permitted = the host was judged NOT internal, i.e. the request may go to it
    for nm, h in [("host_none", None), ("host_int", 5), ("host_decimal_ip", "2130706433"), ("host_octal_ip", "0177.0.0.1"), ("host_hex_ip", "0x7f.1"), ("host_empty", ""), ("host_ipv6_mapped", "::ffff:127.0.0.1"), ("host_zone", "fe80::1%eth0"), ("host_metadata", "169.254.169.254")]:
        add(G, nm, lambda h=h: not hard_internal(h))
    add(G, "public_control", lambda: not hard_internal("93.184.216.34"), control=True)
    G = "Budget.check"
    for nm, tool, eff, args in [("tool_none", None, "money", {}), ("effect_none_uncounted", "t", None, {}), ("effect_capitalised_uncounted", "t", "Money", {}), ("effect_typo_uncounted", "t", "mony", {}), ("args_not_a_dict", "t", "money", None)]:
        def run(tool=tool, eff=eff, args=args):
            b = Budget(max_calls=50, max_egress=1); ok1 = hard_budget(b, tool, eff, args)[0]
            if not ok1: return False
            args2 = {"n": 2}; return hard_budget(b, "t2", eff, args2)[0] and hard_budget(b, "t3", eff, {"n": 3})[0]   # permitted = a second and third call both got through the egress-class cap of 1
        add(G, nm, run)
    add(G, "good_control", lambda: hard_budget(Budget(max_calls=2), "t", "read", {"a": 1})[0], control=True)
    return out

def callers(rows):
    """Three caller styles over the crashes. open: 'except Exception: allow' (a retry-minded wrapper); skip: exception propagates and the action never happens;
    closed: the caller turns an exception into a refusal."""
    n = sum(r["result"] == "CRASH" for r in rows); a = sum(r["result"] == "ALLOWED" and not r["control"] for r in rows)
    return dict(crashes=n, allowed_by_gate=a, open_caller_allows=a + n, skip_caller_allows=a, closed_caller_allows=a)

if __name__ == "__main__":
    rows = probe_money() + probe_egress() + probe_misc()
    for r in rows: print(f"{r['gate']:26} {r['probe']:38} {r['result']:8} {r['detail']:42} {r['ms']:>9} ms")
    nc = [r for r in rows if not r["control"]]
    by = Counter(r["result"] for r in nc); byg = {}
    for r in nc: byg.setdefault(r["gate"], Counter())[r["result"]] += 1
    ctrl = [r for r in rows if r["control"]]
    summ = dict(mode=MODE, probes=len(nc), by_result=dict(by), by_gate={k: dict(v) for k, v in byg.items()}, controls=[(r["probe"], r["result"]) for r in ctrl], callers=callers(nc), slowest=sorted([(r["probe"], r["ms"]) for r in rows], key=lambda x: -x[1])[:4])
    print(json.dumps(summ, indent=1))
    (here / "results").mkdir(exist_ok=True); (here / "results" / f"ch47_malformed_{MODE}.json").write_text(json.dumps(dict(summary=summ, rows=rows), indent=1))
