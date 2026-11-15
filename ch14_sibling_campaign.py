#!/usr/bin/env python3
"""Chapter 14, lab 5 (no model): (a) what routing sibling invoices (same vendor, same amount, both open) to REVIEW costs in review volume and buys in residual; (b) a campaign detector over the typed events: repeated DOCUMENT_ACCOUNT_DIFFERS_FROM_REGISTRY from one vendor in a week.
Both parts use generated histories; the numbers are what my assumptions produce."""
import sys, json, random
from collections import Counter, defaultdict
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
from bulwark.docagent import *
import ch14_corpus as C
rec = C.make_records(); open_ids = [i for i, x in rec.invoices.items() if x["status"] == "open"]; out = []
def say(s): out.append(s); print(s)
sib = [i for i in open_ids if has_sibling(rec, i)]
say(f"open invoices {len(open_ids)}; with a sibling {len(sib)} ({len(sib)/len(open_ids):.1%})")
# (a) clean documents, 5 passes over every open invoice, with and without the sibling rule (rule extractor, so formatting noise costs the same in both)
rng = random.Random(1414); N = 0; A = Counter()
for _ in range(5):
    for i in open_ids:
        d, _p = C.clean(rec, i, rng); ex = parse_rules(d.text_layer)
        for sr in (False, True):
            v = verify(d, ex, rec, level=3, ex_visible=parse_rules(d.visible), sibling_review=sr); A[(sr, v.route)] += 1; A[(sr, "SIB" if "SIBLING_INVOICE_SAME_AMOUNT" in v.reasons else "x")] += 1
        N += 1
say(f"clean documents {N}: AUTO without sibling rule {A[(False,'AUTO')]} ({A[(False,'AUTO')]/N:.1%}), with {A[(True,'AUTO')]} ({A[(True,'AUTO')]/N:.1%}); documents held ONLY by the sibling rule {A[(True,'SIB')]} ({A[(True,'SIB')]/N:.1%})")
# the swap: for every sibling pair, a document for invoice A that carries invoice B's number (consistent in every other respect)
swaps = Counter()
for i in sib:
    x = rec.invoices[i]; j = [k for k in sib if k != i and rec.invoices[k]["payee_id"] == x["payee_id"] and rec.invoices[k]["amount_cents"] == x["amount_cents"]][0]
    d, _p = C.clean(rec, i, random.Random(f"s{i}"), noise=False); d = Document(d.doc_id, d.visible.replace(x["number"], rec.invoices[j]["number"])); ex = parse_rules(d.text_layer)
    for sr in (False, True):
        v = verify(d, ex, rec, level=3, ex_visible=parse_rules(d.visible), sibling_review=sr); swaps[(sr, v.route)] += 1
say(f"number swapped to the sibling's, {len(sib)} documents: without the rule {dict((k[1], n) for k, n in swaps.items() if not k[0])}; with it {dict((k[1], n) for k, n in swaps.items() if k[0])}")
# (b) a month of generated traffic, one impersonation campaign
rng = random.Random(1415); days = 30; events = []   # (day, vendor, route, reasons)
for day in range(days):
    for _ in range(rng.randrange(8, 15)):
        i = rng.choice(open_ids); x = rec.invoices[i]
        if rng.random() < 0.03: d = C.hostile(rec, i, "H2_account_swap", rng); kind = "stray"      # background: a vendor's own typo or a one-off bad document
        else: d, _p = C.clean(rec, i, rng); kind = "clean"
        ex = parse_rules(d.text_layer); v = verify(d, ex, rec, level=3, ex_visible=parse_rules(d.visible)); events.append((day, x["payee_id"], v.route, v.reasons, kind))
target = "payee_2"
for day in range(14, 22):
    for _ in range(rng.choice([1, 2, 2, 3])):
        i = rng.choice([k for k in open_ids if rec.invoices[k]["payee_id"] == target]); d = C.hostile(rec, i, "H2_account_swap", rng); ex = parse_rules(d.text_layer)
        v = verify(d, ex, rec, level=3, ex_visible=parse_rules(d.visible)); events.append((day, target, v.route, v.reasons, "campaign"))
def detect(K, W=7):
    first = {}; fp = 0
    for day in range(days):
        win = Counter(p for (dd, p, r, why, k) in events if day - W < dd <= day and "DOCUMENT_ACCOUNT_DIFFERS_FROM_REGISTRY" in why)
        for p, n in win.items():
            if n >= K and p not in first: first[p] = day
    return first
n_camp = sum(1 for e in events if e[4] == "campaign"); n_stray = sum(1 for e in events if e[4] == "stray")
say(f"month: {len(events)} documents, {n_stray} stray account differences across vendors, {n_camp} campaign documents against {target} between day 14 and day 21")
cat = Counter(e[2] for e in events); say(f"routes: {dict(cat)}")
for K in (2, 3, 4, 5):
    f = detect(K); say(f"alert when a vendor has >= {K} account differences in 7 days: first alert days {f}; campaign found day {f.get(target)}; alerts on other vendors {len([p for p in f if p != target])}")
json.dump(out, open(here / "results/ch14_sibling_campaign.json", "w"), indent=1); open(here / "results/ch14_sibling_campaign.log", "w").write("\n".join(out) + "\n")
