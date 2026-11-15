#!/usr/bin/env python3
"""Chapter 35, lab 5 (no model): what does a change to one module put back in question?  For each module in the lab bundle: the items produced against it (by cost class) and the controls that rest on them.
Also: how many items and controls a change to ANY single module reopens, on average, and the single most expensive module (most live items).  Writes results/ch35_impact.json."""
import sys, json, time
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
import ch35_collect as K
from bulwark.bundle import impact
b = K.build(time.time()); rows = {}
for m in sorted({m for it in b.items.values() for m in it.subjects}):
    im = impact(b, m); rows[m] = dict(items=len(im["items"]), sim=len(im["sim"]), live=len(im["live"]), unit=len(im["unit"]), controls=im["controls"])
    print(f"{m:14} items {len(im['items'])} (sim {len(im['sim'])}, live {len(im['live'])}, unit {len(im['unit'])}) controls {len(im['controls'])}: {','.join(im['controls'])}")
print("modules in bundle:", len(rows), "| items:", len(b.items), "| controls:", len(b.controls))
print("excluding the pytest item (it is rerun in seconds): mean items reopened per module", round(sum(r["items"] - r["unit"] for r in rows.values()) / len(rows), 2), "| max", max(r["items"] - r["unit"] for r in rows.values()))
print("modules whose change reopens a live item:", sorted(m for m, r in rows.items() if r["live"]))
print("mean controls reopened per module:", round(sum(len(r["controls"]) for r in rows.values()) / len(rows), 2), "| modules whose change reopens C06 (the control that rests on the pytest log):", sum("C06" in r["controls"] for r in rows.values()), "of", len(rows))
from bulwark.bundle import stamp
json.dump(dict(rows=rows, stamp=stamp(here, sorted(rows) + ["bundle"])), open(here / "results/ch35_impact.json", "w"), indent=1)
