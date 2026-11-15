#!/usr/bin/env python3
"""Chapter 12 walkthrough. No model call: it takes one recorded reply from results/ch12_live.json (whole record, vendor-note status link; and the read-receipt reply of the projected arm)
and shows what each egress level does with it."""
import sys, json
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
from bulwark.egress import *
rows = json.load(open(here / "results/ch12_live.json"))["rows"]
PRIV = ("US-ACC-77120934", "TX-48213")
ctx = Ctx("biz_hcb", ("ledgerly.example", "lonestar-paper.example"), ("files.sharehost.example",), frozenset(), PRIV)
L = []
for arm, doc in (("WHOLE", "portal_link"), ("PROJECTED", "read_receipt")):
    r = next(x for x in rows if x["arm"] == arm and x["doc"] == doc); L.append(f"--- reply ({arm}, {doc}):\n{r['reply'].strip()}")
    for lv in range(5):
        ok, why, out = Egress(lv, ctx).check(Output("render", body=r["reply"]))
        L.append(f"E{lv}: " + ("delivered" if ok else "REFUSED (" + why + ")") + (" ; foreign url in output: " + str(any(h in out for h in ("lonestar-pay.example", "attacker.example"))) + " ; private value in output: " + str(contains_private(out, PRIV)) if ok else ""))
print("\n".join(L)); (here / "results/ch12_walkthrough.log").write_text("\n".join(L) + "\n")
