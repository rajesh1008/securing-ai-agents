#!/usr/bin/env python3
"""Chapter 14, lab 4: the second setting. A scanned invoice reaches the product as OCR text, with character confusions. No model. 200 clean documents per noise rate, seeded;
confusions are the usual ones (0/O, 1/l, 5/S, 8/B, 2/Z, comma/period), applied independently to each character at the stated rate. The verifier is L3 with the rule extractor.
Measured: how many clean documents still route AUTO; what the REVIEW reasons are; and whether any corrupted document is AUTO with an effect that the books do not support (it cannot be, and the lab checks)."""
import sys, json, random
from collections import Counter
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
from bulwark.docagent import *
import ch14_corpus as C
rec = C.make_records(); open_ids = [i for i, x in rec.invoices.items() if x["status"] == "open"]
CONF = {"0": "O", "O": "0", "1": "l", "l": "1", "5": "S", "S": "5", "8": "B", "B": "8", "2": "Z", ",": ".", ".": ","}
def ocr(t, rate, rng): return "".join(CONF[c] if c in CONF and rng.random() < rate else c for c in t)
L = [f"{'char error rate':16s} docs  AUTO  REVIEW  REJECT  AUTO-but-wrong   top reasons"]; out = {}
for rate in (0.0, 0.002, 0.005, 0.01, 0.02, 0.05):
    rng = random.Random(f"ocr{rate}"); c = Counter(); rs = Counter(); wrong = 0
    for n in range(200):
        i = open_ids[n % len(open_ids)]; d, _ = C.clean(rec, i, random.Random(f"o{n}"), noise=False); d2 = Document(d.doc_id, ocr(d.visible, rate, rng))
        v = verify(d2, parse_rules(d2.text_layer), rec, level=3, ex_visible=parse_rules(d2.visible)); c[v.route] += 1
        for r in v.reasons: rs[r] += 1
        if v.route == "AUTO":
            x = rec.invoices[i]; te = dict(invoice_id=i, payee_id=x["payee_id"], amount_cents=x["amount_cents"], destination=rec.vendors[x["payee_id"]]["account"])
            wrong += v.effect != te
    out[str(rate)] = dict(AUTO=c["AUTO"], REVIEW=c["REVIEW"], REJECT=c["REJECT"], wrong=wrong, reasons=dict(rs.most_common(4)))
    L.append(f"{rate:<16.3f} 200 {c['AUTO']:5d} {c['REVIEW']:7d} {c['REJECT']:7d} {wrong:15d}   {dict(rs.most_common(3))}")
print("\n".join(L)); json.dump(out, open(here / "results/ch14_ocr_noise.json", "w"), indent=1); open(here / "results/ch14_ocr_noise.log", "w").write("\n".join(L) + "\n")
