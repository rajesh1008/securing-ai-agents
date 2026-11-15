#!/usr/bin/env python3
"""Chapter 41, lab 4: the first-page scorecard on a CONSTRUCTED month-nine state (day 270), the state of the composite in section 41.1: the alert review not done for 11 weeks, the examiner rehearsal and the red-team exercise late, one backup who has run
nothing, 61 unread alerts, three waivers (two past review), evidence from the first quarter, and a library not extended since day 150.  Every input is written by the author; the lab shows what the seven numbers look like when the state is as described
and that the function finds each thing.  Anchor figures come from the live run of lab 3 (results/ch41_creep.json) when it exists.  No model calls.  Writes results/ch41_scorecard.json."""
import sys, json
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
import ch41_rota as R
from bulwark.rota import scorecard
rt = R.build("C"); TODAY = 270
last = {}
for j in rt.jobs:
    if j.periodic(): last[j.id] = TODAY - (TODAY % j.cadence if j.cadence > 1 else 0)   # ran on its last scheduled day
last["J01"] = 193; last["J09"] = 100; last["J12"] = 77; last["J16"] = 262; last["J10"] = 232
backup_last = {j.id: 120 for j in rt.jobs if j.periodic() and j.backup}
for k in ("J02", "J05", "J08", "J09", "J12", "J15", "J17", "J18", "J19", "J22", "J25", "J26", "J28"): backup_last.pop(k, None)
ev = {}
SHELF = {"UNIT": 30, "LAB_SIM": 365, "LAB_LIVE": 180, "REVIEW": 365}
import ch35_collect as C
for it in C.ITEMS: ev[it[0]] = (0, SHELF[it[2]])
ev["E01"] = (262, 30)   # the unit tests are rerun on every release
alerts = [(f"A{i:02d}", 193 + (i * 77) // 61, None) for i in range(61)]
waivers = [("W1", 60), ("W2", 150), ("W3", 300)]
library = dict(last_added=150, families=8, dims_touched={"goal", "voice", "frame", "position", "host", "persistence"}, dims_all={"goal", "voice", "frame", "position", "host", "persistence", "visibility", "interpretation", "task relation"})
anchor = None; p = here / "results/ch41_creep.json"
if p.exists():
    d = json.load(open(p)); T = d["totals"]
    anchor = dict(step_last_vs_parent=T["s6r1"] - (T["s5r1"] + T["s5r2"]) / 2, anchor_last_vs_v0=T["s6r1"] - (T["v0r1"] + T["v0r2"]) / 2)
sc = scorecard(rt, TODAY, last, backup_last, ev, waivers, alerts, library, anchor)
for k, v in sc.items(): print(f"{k:26s} {v}")
json.dump(sc, open(here / "results/ch41_scorecard.json", "w"), indent=1)
