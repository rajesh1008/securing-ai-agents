#!/usr/bin/env python3
"""Chapter 30, lab 4 (no model, no network): the reading bill.  Takes the recorded arms of results/ch30_analyse.json and prices the person-time of reading what each arm produced.
Assumptions (mine, printed, and the only inputs that are not measured): reading an unclustered win takes `read` minutes (open the document, the extraction and the decision); writing up a NEW finding takes 10 minutes, and is paid in both cases;
confirming that a clustered item is a known finding in another campaign takes 0.5 minute; a reviewer costs US$60 an hour.  The model cost is the recorded approx_usd of each arm.
Writes results/ch30_reading_bill.log and .json"""
import json, sys
from pathlib import Path
here = Path(__file__).resolve().parent
d = json.load(open(here / "results/ch30_analyse.json")); L = []; P = L.append; out = {}
WRITE, CONFIRM, RATE = 10.0, 0.5, 60.0
P(f"Assumptions: write-up of a new finding {WRITE:g} min, confirm a known finding {CONFIRM:g} min, reviewer US${RATE:g}/hour.")
for read in (0.5, 1.5, 3.0):
    P(f"\nRead time per unclustered win: {read:g} min")
    P(f"{'arm':>6s} {'wins':>5s} {'findings':>8s} {'model $':>8s} {'read-all min':>13s} {'read-all $':>11s} {'clustered min':>14s} {'clustered $':>12s} {'person:model, all':>18s} {'person:model, clustered':>24s}")
    for arm in ("L1-N", "L1-V", "L3-N", "L3-V", "S-HDR"):
        a = d[arm]; wins, fnd, usd = a["wins"], a["findings"], a["approx_usd"]
        dup = sum(a["campaigns_per_key"].values()) - fnd
        alln = wins * read + fnd * WRITE; clu = fnd * WRITE + dup * CONFIRM
        out[f"{arm}/{read}"] = dict(wins=wins, findings=fnd, model_usd=usd, read_all_min=alln, clustered_min=clu, dup_confirms=dup)
        P(f"{arm:>6s} {wins:>5d} {fnd:>8d} {usd:>8.2f} {alln:>13.0f} {alln/60*RATE:>11.2f} {clu:>14.1f} {clu/60*RATE:>12.2f} {alln/60*RATE/usd:>18.1f} {clu/60*RATE/usd:>24.1f}")
json.dump(out, open(here / "results/ch30_reading_bill.json", "w"), indent=1)
open(here / "results/ch30_reading_bill.log", "w").write("\n".join(L) + "\n"); print("\n".join(L))
