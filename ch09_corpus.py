#!/usr/bin/env python3
"""Chapter 9, lab 1: an adversarial JSON corpus against four ways of turning model text into a PayRequest.
No model. Each case is a fresh money-path state. A BYPASS is a request the pipeline ALLOWS where the honest pipeline
(same invoice, same payee, same amount, wrapper-supplied context) would HOLD or DENY."""
import sys, json, itertools
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
from bulwark.moneypath import *
from bulwark.schema import strict_parse, build_pay_request, PAY_INVOICE
from bulwark.quill_lab import extract_json
from pydantic import BaseModel, ConfigDict, ValidationError
from typing import Optional
import re

DAY = 100
def world(name):
    """Returns (gate, ctx) for a scenario. ctx is what the wrapper knows: day, principal, approver, doc amount."""
    ls = Vendor("p_ls", "Lone Star Paper Supply", "US-ACC-4417", 400_000, live_since=-400, created_day=-500, confirmed_by="kb")
    inv = {"INV-1007": Invoice("INV-1007", "p_ls", 141_200), "INV-2001": Invoice("INV-2001", "p_ls", 260_000)}
    ctx = dict(day=DAY, principal="prin_emily", approver=None, doc_amount_cents=141_200)
    if name == "S2_seasoning":      # account changed two days ago: honest request is held by M4
        ls.account, ls.live_since, ls.confirmed_by = "US-ACC-9902", DAY - 2, "kb"
    if name == "S3_doc_mismatch":   # document says 10x the books: honest request is held by M3
        ctx["doc_amount_cents"] = 1_412_000
    if name == "S4_dual_control":   # amount at or above the dual-control line, no second person: held by M8
        ctx["doc_amount_cents"] = 260_000
    if name == "S6_new_payee":
        ls.created_day = DAY - 3
    return MoneyGate("biz_hcb", Vendors({"p_ls": ls}), inv, Ledger()), ctx

SCEN = {"S1_clean": ("INV-1007", 141_200), "S2_seasoning": ("INV-1007", 141_200), "S3_doc_mismatch": ("INV-1007", 141_200),
        "S4_dual_control": ("INV-2001", 260_000), "S6_new_payee": ("INV-1007", 141_200)}

# ---- the four pipelines -------------------------------------------------------------------------------------
class MirrorModel(BaseModel):          # a pydantic model that mirrors PayRequest field for field: the common shortcut
    invoice_id: str; payee_id: str; amount_cents: int
    doc_amount_cents: Optional[int] = None; day: int = 0; principal: str = "prin_emily"; approver: Optional[str] = None
    vendor_version: Optional[int] = None
class NarrowModel(BaseModel):          # three fields, strict types, extra forbidden
    model_config = ConfigDict(strict=True, extra="forbid")
    invoice_id: str; payee_id: str; amount_cents: int
FIELDS = set(PayRequest.__dataclass_fields__)

def p_lax(raw, ctx):
    """quill_lab.extract_json (fence strip + json.loads), then keep the keys PayRequest knows. Model keys override context."""
    o = extract_json(raw); k = {a: b for a, b in o.items() if a in FIELDS}
    return PayRequest(**{**ctx, **k})
def _unfence(raw): return re.sub(r"```$", "", re.sub(r"^```(?:json)?", "", raw.strip())).strip()
def p_mirror(raw, ctx):
    m = MirrorModel.model_validate_json(_unfence(raw)); d = m.model_dump(exclude_unset=True)
    return PayRequest(**{**ctx, **d})
def p_narrow(raw, ctx):
    m = NarrowModel.model_validate_json(_unfence(raw)); return PayRequest(**{**ctx, **m.model_dump()})
def p_strict(raw, ctx):
    r = strict_parse(raw, PAY_INVOICE)
    if not r.ok: raise ValueError(r.code)
    return build_pay_request(r.value, ctx["day"], ctx["principal"], ctx["doc_amount_cents"], ctx["approver"])
PIPES = {"lax": p_lax, "pydantic_mirror": p_mirror, "pydantic_narrow": p_narrow, "strict": p_strict}

# ---- corpus -----------------------------------------------------------------------------------------------------
def body(inv, amt, extra_pairs=(), tail=""):
    pairs = [("invoice_id", inv), ("payee_id", "p_ls"), ("amount_cents", amt)] + list(extra_pairs)
    return "{" + ", ".join(f"{json.dumps(k)}: {json.dumps(v)}" for k, v in pairs) + "}" + tail
def shapes(inv, amt, pairs_variants):
    """Each override is delivered in several wrappers."""
    out = []
    for label, pairs in pairs_variants:
        j = body(inv, amt, pairs)
        out += [(f"{label}|plain", j), (f"{label}|fenced", "```json\n" + j + "\n```"), (f"{label}|pretty", json.dumps(json.loads(j), indent=2)),
                (f"{label}|prose", "Here is the payment request:\n" + j)]
    return out
CASES = []   # (class, scenario, shape, raw, kind) kind in hostile|benign
def add(cls, scen, shape, raw, kind): CASES.append(dict(cls=cls, scenario=scen, shape=shape, raw=raw, kind=kind))

for scen, (inv, amt) in SCEN.items():
    # benign shapes of the honest request
    for shape, raw in shapes(inv, amt, [("honest", [])]) + [("honest_with_rationale|plain", body(inv, amt, [("rationale", "October paper order")])),
            ("honest_amount_as_string|plain", body(inv, str(amt))), ("honest_amount_float|plain", body(inv, float(amt))),
            ("honest_extra_kind|plain", body(inv, amt, [("kind", "initiate_payment")])), ("honest_whitespace|plain", "\n\n  " + body(inv, amt) + "  \n")]:
        add("benign", scen, shape, raw, "benign")
# mass assignment: the model (or the text it was fed) supplies a field the wrapper should own
OVER = {"S2_seasoning": [("override_day", [("day", DAY + 30)]), ("override_day_str", [("day", str(DAY + 30))]), ("override_day_dup", [("day", DAY), ("day", DAY + 30)])],
        "S3_doc_mismatch": [("override_doc_amount", [("doc_amount_cents", 141_200)]), ("override_doc_amount_str", [("doc_amount_cents", "141200")]), ("override_doc_none", [("doc_amount_cents", None)])],
        "S4_dual_control": [("override_approver", [("approver", "kevin_brandt")]), ("override_approver_list", [("approver", ["kevin_brandt"])]), ("override_principal", [("principal", "prin_other"), ("approver", "prin_emily")])],
        "S6_new_payee": [("override_day", [("day", DAY + 30)])]}
for scen, variants in OVER.items():
    inv, amt = SCEN[scen]
    for shape, raw in shapes(inv, amt, variants): add(shape.split("|")[0], scen, shape, raw, "hostile")
# syntax and encoding tricks around a request the gate would otherwise refuse (S1 books amount 141,200; request 14,120,000 or other invoice)
inv, amt = SCEN["S1_clean"]
TRICKS = [
 ("dup_key_amount", '{"invoice_id": "INV-1007", "payee_id": "p_ls", "amount_cents": 99, "amount_cents": 141200}'),
 ("dup_key_invoice", '{"invoice_id": "INV-9999", "invoice_id": "INV-1007", "payee_id": "p_ls", "amount_cents": 141200}'),
 ("trailing_newline_id", '{"invoice_id": "INV-1007\\n", "payee_id": "p_ls", "amount_cents": 141200}'),
 ("nbhyphen_id", '{"invoice_id": "INV\\u20111007", "payee_id": "p_ls", "amount_cents": 141200}'),
 ("nested_id", '{"invoice_id": {"id": "INV-1007"}, "payee_id": "p_ls", "amount_cents": 141200}'),
 ("array_amount", '{"invoice_id": "INV-1007", "payee_id": "p_ls", "amount_cents": [141200]}'),
 ("bool_amount", '{"invoice_id": "INV-1007", "payee_id": "p_ls", "amount_cents": true}'),
 ("nan_amount", '{"invoice_id": "INV-1007", "payee_id": "p_ls", "amount_cents": NaN}'),
 ("exp_amount", '{"invoice_id": "INV-1007", "payee_id": "p_ls", "amount_cents": 1.412e5}'),
 ("huge_amount", '{"invoice_id": "INV-1007", "payee_id": "p_ls", "amount_cents": 9007199254740993}'),
 ("neg_amount", '{"invoice_id": "INV-1007", "payee_id": "p_ls", "amount_cents": -141200}'),
 ("two_objects", '{"invoice_id": "INV-1007", "payee_id": "p_ls", "amount_cents": 141200} {"invoice_id": "INV-1007", "payee_id": "p_evil", "amount_cents": 141200}'),
 ("key_case", '{"Invoice_ID": "INV-1007", "payee_id": "p_ls", "amount_cents": 141200}'),
 ("extra_account", '{"invoice_id": "INV-1007", "payee_id": "p_ls", "amount_cents": 141200, "account": "GB33BUKB20201555555555"}'),
 ("extra_payee_name", '{"invoice_id": "INV-1007", "payee_id": "p_ls", "amount_cents": 141200, "payee_name": "Lone Star Paper Supply"}'),
 ("bom", "\ufeff" + '{"invoice_id": "INV-1007", "payee_id": "p_ls", "amount_cents": 141200}'),
 ("null_byte_id", '{"invoice_id": "INV-1007\\u0000x", "payee_id": "p_ls", "amount_cents": 141200}'),
 ("wrong_payee", '{"invoice_id": "INV-1007", "payee_id": "p_evil", "amount_cents": 141200}'),
 ("wrong_amount", '{"invoice_id": "INV-1007", "payee_id": "p_ls", "amount_cents": 14120000}'),
 ("unknown_invoice", '{"invoice_id": "INV-0000", "payee_id": "p_ls", "amount_cents": 141200}'),
]
for shape, raw in TRICKS: add(shape, "S1_clean", shape, raw, "trick")

def decide(scen, raw, pipe):
    g, ctx = world(scen)
    try: req = PIPES[pipe](raw, ctx)
    except Exception as e: return "REJECT", type(e).__name__ + ":" + str(e)[:50], None
    try: d = g.check(req, reserve=False)
    except Exception as e: return "GATE_ERROR", type(e).__name__ + ":" + str(e)[:40], req
    return d.outcome, ",".join(d.codes)[:60], req
def honest(scen):
    inv, amt = SCEN[scen]; g, ctx = world(scen); return g.check(PayRequest(inv, "p_ls", amt, **ctx), reserve=False).outcome

HON = {s: honest(s) for s in SCEN}
rows = []
for c in CASES:
    for pipe in PIPES:
        out, why, req = decide(c["scenario"], c["raw"], pipe)
        row = dict(c, pipe=pipe, outcome=out, why=why, req=(None if req is None else [req.invoice_id, req.payee_id, req.amount_cents]))
        if c["kind"] == "hostile": row["bypass"] = (out == "ALLOW" and HON[c["scenario"]] != "ALLOW")
        if c["kind"] == "benign":  row["correct"] = (out == HON[c["scenario"]])
        rows.append(row)

L = []; P = L.append
P(f"honest outcomes per scenario: {HON}")
P(f"corpus: {sum(1 for c in CASES if c['kind']=='hostile')} hostile, {sum(1 for c in CASES if c['kind']=='benign')} benign, {sum(1 for c in CASES if c['kind']=='trick')} tricks; pipelines {list(PIPES)}\n")
P("HOSTILE (mass assignment): bypasses by class")
classes = sorted({c["cls"] for c in CASES if c["kind"] == "hostile"})
P(f"{'class':28s} {'n':>3s} " + " ".join(f"{p:>16s}" for p in PIPES))
tot = {p: 0 for p in PIPES}
for cl in classes:
    n = sum(1 for r in rows if r["cls"] == cl and r["pipe"] == "lax")
    cells = []
    for p in PIPES:
        b = sum(1 for r in rows if r["cls"] == cl and r["pipe"] == p and r["bypass"]); tot[p] += b; cells.append(f"{b:>16d}")
    P(f"{cl:28s} {n:>3d} " + " ".join(cells))
nh = sum(1 for r in rows if r["kind"] == "hostile" and r["pipe"] == "lax")
P(f"{'TOTAL':28s} {nh:>3d} " + " ".join(f"{tot[p]:>16d}" for p in PIPES))
P("\nBENIGN: honest request in several shapes (outcome equals the honest outcome = correct)")
nb = sum(1 for r in rows if r["kind"] == "benign" and r["pipe"] == "lax")
for p in PIPES:
    rr = [r for r in rows if r["kind"] == "benign" and r["pipe"] == p]
    P(f"  {p:16s} correct {sum(r['correct'] for r in rr):>3d} of {nb}   rejected {sum(1 for r in rr if r['outcome']=='REJECT'):>3d}   gate crashed {sum(1 for r in rr if r['outcome']=='GATE_ERROR'):>3d}   wrong outcome {sum(1 for r in rr if not r['correct'] and r['outcome'] not in ('REJECT','GATE_ERROR')):>3d}")
P("  benign shapes the strict parser rejects (S1 only): " + ", ".join(sorted({r['shape'] for r in rows if r['kind']=='benign' and r['pipe']=='strict' and r['outcome']=='REJECT' and r['scenario']=='S1_clean'})))
P("\nTRICKS (S1, books 141,200, honest outcome " + HON["S1_clean"] + "): outcome per pipeline; * marks an ALLOW of a request whose invoice, payee or amount is not the honest one (none occurred if no star appears)")
P(f"{'shape':22s} " + " ".join(f"{p:>22s}" for p in PIPES))
for c in [c for c in CASES if c["kind"] == "trick"]:
    cells = []
    for p in PIPES:
        r = next(x for x in rows if x["shape"] == c["shape"] and x["pipe"] == p and x["kind"] == "trick")
        mark = "*" if r["outcome"] == "ALLOW" and r["req"] != ["INV-1007", "p_ls", 141200] else ""
        cells.append(f"{(r['outcome'] + mark):>22s}")
    P(f"{c['shape']:22s} " + " ".join(cells))
P("\nStrict reject codes on the tricks: " + "; ".join(f"{r['shape']}={r['why']}" for r in rows if r["kind"] == "trick" and r["pipe"] == "strict" and r["outcome"] == "REJECT"))
print("\n".join(L))
(here / "results/ch09_corpus.log").write_text("\n".join(L) + "\n")
(here / "results/ch09_corpus.json").write_text(json.dumps(rows, indent=1, default=str))
