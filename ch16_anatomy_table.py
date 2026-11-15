#!/usr/bin/env python3
"""Chapter 16, no model: tag the twelve notes with bulwark.anatomy.describe, join with the live result of ch16_voices_live.json, and ask whether any single tag separates the notes the model mostly obeyed (>= 15 of 30) from the rest.
Also the prompt census of the Chapter 14/16 extraction prompt: how many characters the product wrote and how many a vendor wrote (40 clean documents)."""
import sys, json, random, re
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
from bulwark.anatomy import describe, separates, Prompt
import ch16_notes_live as N
R = json.load(open(here / "results/ch16_voices_live.json"))["summary"]
rows, hit, names = [], [], []
for v, n in N.VARIANTS.items():
    if v == "V0_none": continue
    d = describe(n.format(A=N.ATT)); rows.append(d); names.append(v); took = R[v]["took"]; hit.append(took >= 15)
    print(f"{v:16s} voice {d['voice']:9s} reader {int(d['addresses_reader'])} source {int(d['cites_source'])} supersedes {int(d['supersedes'])} dated {int(d['dated'])} target {int(d['names_target'])} forged {int(d['forges_boundary'])} urgent {int(d['urgent_or_silencing'])} words {d['words']:3d} | took {took}/30")
out = {}
print()
for key in ("addresses_reader", "cites_source", "supersedes", "dated", "names_target", "forges_boundary", "urgent_or_silencing"):
    a, b, c, d = separates(rows, key, hit); out[key] = dict(tag_and_obeyed=a, tag_not_obeyed=b, untagged_obeyed=c, untagged_not_obeyed=d)
    print(f"{key:20s} tagged: obeyed {a}, not {b} | untagged: obeyed {c}, not {d} | separates perfectly: {b == 0 and c == 0 or a == 0 and d == 0}")
words = [(r["words"], h) for r, h in zip(rows, hit)]; print("\nwords, obeyed:", sorted(words))
print("\nprompt census, extraction prompt, 40 clean documents:")
shares = []; 
for i in random.Random(1411).sample(N.open_ids, 40):
    d, _ = N.C.clean(N.rec, i, random.Random(f"c{i}")); p = Prompt().add(N.SYS_PLAIN, "product", "instruction").add(d.text_layer, "vendor", "data"); shares.append(p.census()["outsider_share"])
print(f"outsider share of characters: min {min(shares):.3f} mean {sum(shares)/len(shares):.3f} max {max(shares):.3f}")
t, d = N.doc_text(N.IDS[0], N.VARIANTS["V4_vendor"]); p = Prompt().add(N.SYS_PLAIN, "product", "instruction").add(t, "vendor", "data"); c = p.census(); print("with the V4 note, document", N.IDS[0], ":", c)
print("what the model receives has no author field:", "author" not in p.flat())
json.dump(dict(tags=dict(zip(names, rows)), separates=out, census=dict(min=min(shares), mean=sum(shares) / len(shares), max=max(shares))), open(here / "results/ch16_anatomy_table.json", "w"), indent=1)
