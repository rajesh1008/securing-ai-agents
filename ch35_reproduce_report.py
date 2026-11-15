#!/usr/bin/env python3
"""Chapter 35, lab 1 report (no model): summarises results/ch35_reproduce.json.  Scripts that are part of this chapter are left out.  The reason for each differing file was assigned by me from the diff
(timing = a measured duration; random = random ids, keys or digests; race = thread scheduling the lab is about; tree = the lab walks the code tree and the tree has changed)."""
import json
from pathlib import Path
here = Path(__file__).resolve().parent
r = [o for o in json.load(open(here / "results/ch35_reproduce.json")) if not o["script"].startswith("ch35")]
REASON = {"ch11_walkthrough.log": "random", "ch14_walkthrough.json": "random", "ch14_walkthrough.log": "random", "ch08_race_dispatch.json": "race", "ch08_race_dispatch.log": "race", "ch04_mediation_audit.json": "tree"}
ok = [o for o in r if o["status"] == "OK"]; allsame = [o for o in ok if o["wrote_identical"] and not o["wrote_different"]]
print("scripts run:", len(r), "| ran without the model:", len(ok), "| needed the model (exit 86 on first API call):", sum(o["status"] == "NEEDS_MODEL" for o in r), "| error or timeout:", sum(o["status"] == "ERROR" for o in r))
print("of", len(ok), ": every file written identical to the stored one:", len(allsame), "| at least one file different:", sum(1 for o in ok if o["wrote_different"]), "| wrote no file:", sum(1 for o in ok if not (o["wrote_identical"] or o["wrote_different"])))
pairs = [(o["script"], f) for o in ok for f in o["wrote_different"]]
from collections import Counter
c = Counter(REASON.get(f, "timing") for s, f in pairs)
print("files written identical:", sum(len(o["wrote_identical"]) for o in ok), "| file writes that differ:", len(pairs), dict(c))
print("error or timeout:", [(o["script"], o["rc"]) for o in r if o["status"] == "ERROR"]); print("needs model:", [o["script"] for o in r if o["status"] == "NEEDS_MODEL"])
