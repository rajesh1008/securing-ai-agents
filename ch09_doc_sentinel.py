#!/usr/bin/env python3
"""Chapter 9, lab 4: doc_amount_cents=None, the fail-open Chapter 8 left visible. Seeded, no model.
600 documents: 500 honest (document amount = books) and 100 hostile (document says 10x the books, the Chapter 8 amount-mismatch class).
Vendors label the amount field five different ways; the Chapter 5 parser (steps.parse_amount_due) reads one of them.
Three designs: A parser None passes (Chapter 8 as shipped); B the sentinel DOC_NOT_FOUND (M3 holds); C sentinel plus a parser that reads three more labels."""
import sys, json, random, re
from pathlib import Path
from collections import Counter
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
from bulwark.moneypath import *
from bulwark.steps import parse_amount_due
rnd = random.Random(909)
LABELS = [("Amount due: USD {a}", 0.60), ("Total payable: USD {a}", 0.15), ("Balance due {a} USD", 0.10), ("Please remit {a}", 0.10), ("Amount\nDue: USD {a}", 0.05)]
def fmt(c): return f"{c/100:,.2f}"
def make(i, hostile):
    books = rnd.choice(range(2_500, 180_000, 25)); doc = books * 10 if hostile else books
    # an attacker who writes the document can choose the label; an honest vendor has the label its template has
    if hostile: lab = rnd.choices([l for l, _ in LABELS], [0.2, 0.3, 0.2, 0.2, 0.1])[0]
    else: lab = rnd.choices([l for l, _ in LABELS], [w for _, w in LABELS])[0]
    return dict(i=i, books=books, doc=doc, label=lab.split("{")[0].strip().replace("\n", " ") or lab, text=f"Invoice INV-{i} from Lone Star Paper Supply.\n" + lab.format(a=fmt(doc)) + "\nThank you.\n", hostile=hostile)
EXTRA = [re.compile(r"(?i)total payable:\s*USD\s*([0-9][0-9,]*(?:\.[0-9]{2})?)"), re.compile(r"(?i)balance due\s*([0-9][0-9,]*(?:\.[0-9]{2})?)\s*USD"), re.compile(r"(?i)please remit\s*([0-9][0-9,]*(?:\.[0-9]{2})?)")]
def parse_wide(t):
    v = parse_amount_due(t)
    if v is not None: return v
    for rx in EXTRA:
        m = rx.search(t)
        if m: return round(float(m.group(1).replace(",", "")) * 100)
    return None
docs = [make(i, False) for i in range(500)] + [make(500 + j, True) for j in range(100)]
def gate_for(d):
    v = Vendors({"p": Vendor("p", "Lone Star", "ACC", 1_000_000, live_since=-400, created_day=-500, confirmed_by="kb")})
    return MoneyGate("t", v, {"I": Invoice("I", "p", d["books"])}, Ledger(), tenant_daily_cap=10**9, payee_daily_cents=10**9)
def outcome(d, design):
    parsed = (parse_wide if design == "C" else parse_amount_due)(d["text"])
    if parsed is None and design in ("B", "C"): parsed = DOC_NOT_FOUND
    r = PayRequest("I", "p", d["books"], doc_amount_cents=parsed, day=100, approver="second")   # approver supplied so M8 does not mask M3
    g = gate_for(d); return g.check(r, reserve=False), parsed
res = {}
for design in "ABC":
    c = Counter()
    for d in docs:
        dec, parsed = outcome(d, design)
        k = "hostile" if d["hostile"] else "benign"; c[k + "_" + dec.outcome] += 1
        if parsed is None or parsed == DOC_NOT_FOUND: c[k + "_parser_found_nothing"] += 1
    res[design] = c
L = []; P = L.append
P("documents: 500 honest, 100 hostile (document amount = 10 x books); label mix honest 60/15/10/10/5, attacker-chosen 20/30/20/20/10 percent")
by = Counter((d["label"], d["hostile"]) for d in docs); P("label counts (honest, hostile): " + "; ".join(f"{l!r}: {by[(l,False)]}, {by[(l,True)]}" for l in sorted({d['label'] for d in docs})))
P(f"parser reads the Chapter 5 label in: honest {sum(parse_amount_due(d['text']) is not None for d in docs if not d['hostile'])} of 500, hostile {sum(parse_amount_due(d['text']) is not None for d in docs if d['hostile'])} of 100")
P(f"wide parser (4 labels) reads: honest {sum(parse_wide(d['text']) is not None for d in docs if not d['hostile'])} of 500, hostile {sum(parse_wide(d['text']) is not None for d in docs if d['hostile'])} of 100")
P(f"wrong readings by the Chapter 5 parser (value present but not the document amount): {sum(1 for d in docs if parse_amount_due(d['text']) not in (None, d['doc']))}")
names = {"A": "A  None passes (Chapter 8 as shipped)", "B": "B  sentinel, Chapter 5 parser", "C": "C  sentinel, 4-label parser"}
P(f"\n{'design':40s} {'hostile ALLOW':>14s} {'hostile HOLD':>13s} {'benign ALLOW':>13s} {'benign HOLD':>12s}  parser found nothing (benign/hostile)")
for k in "ABC":
    c = res[k]; P(f"{names[k]:40s} {c['hostile_ALLOW']:>14d} {c['hostile_HOLD']:>13d} {c['benign_ALLOW']:>13d} {c['benign_HOLD']:>12d}  {c['benign_parser_found_nothing']}/{c['hostile_parser_found_nothing']}")
# which codes the benign holds carry under B
c = Counter()
for d in docs:
    if d["hostile"]: continue
    dec, _ = outcome(d, "B")
    for code in dec.codes:
        if code != "ok": c[code] += 1
P("benign hold codes under B: " + ", ".join(f"{k}={v}" for k, v in c.items()))
best = []
for j in range(100):
    d = make(900 + j, True); d["text"] = f"Invoice INV-{900+j} from Lone Star Paper Supply.\nTotal payable: USD {fmt(d['doc'])}\n"; best.append(d)
P("attacker who picks the label that the Chapter 5 parser does not read (100 documents, 10x books): " + ", ".join(f"{k} ALLOW {sum(outcome(d, k)[0].outcome == 'ALLOW' for d in best)}" for k in "ABC"))
print("\n".join(L)); (here / "results/ch09_doc_sentinel.log").write_text("\n".join(L) + "\n")
json.dump({k: dict(v) for k, v in res.items()}, open(here / "results/ch09_doc_sentinel.json", "w"), indent=1)
