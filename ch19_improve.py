#!/usr/bin/env python3
"""Chapter 19 analysis (no model): the gate looks for rises only.  This asks the other question: by how much, and in which payloads, does a candidate fall?
reduction = (baseline mean - candidate mean of its two runs) / baseline mean; 'beyond noise' = the baseline's lowest run minus the candidate's highest run is positive.
Per-payload view: payloads that succeeded 4 of 4 hosts in every baseline run ('always'), how many are still 4 of 4 in both candidate runs; payloads that never succeeded in any baseline run ('never') and succeed in a candidate run.
Writes results/ch19_improve.log"""
import json
from pathlib import Path
here = Path(__file__).resolve().parent
from bulwark.payloads import generate
BY = {p.id: p for p in generate()}
a = json.load(open(here / "results/ch18_release_gate_live.json")); b = json.load(open(here / "results/ch18_noise_runs.json")); r = {**a["runs"], **b["runs"]}
BASE = {"PLAIN": [r["A_1"], r["A_2"], r["PLAIN-3"], r["PLAIN-4"]], "HARD": [r["B_1"], r["B2r"], r["HARD-3"], r["HARD-4"]]}
runs = {p.stem: json.load(open(p)) for p in sorted((here / "results/ch19_runs").glob("*.json"))}
L = []
for c, bn in (("D", "PLAIN"), ("P", "PLAIN"), ("S1", "PLAIN"), ("X", "PLAIN"), ("PX", "PLAIN"), ("S2", "HARD"), ("S3", "HARD"), ("DS", "PLAIN"), ("P0", "PLAIN")):
    base = BASE[bn]; bt = [sum(x.values()) for x in base]; bm = sum(bt) / len(bt); ct = [runs[f"{c}-{n}"]["total"] for n in (1, 2)]; cm = sum(ct) / 2
    red = (bm - cm) / bm; beyond = min(bt) - max(ct) > 0 if red > 0 else None
    alw = [p for p in BY if all(x[p] == 4 for x in base)]; nev = [p for p in BY if all(x[p] == 0 for x in base)]
    still = [p for p in alw if all(runs[f"{c}-{n}"]["runs"][p] == 4 for n in (1, 2))]; gone = [p for p in alw if all(runs[f"{c}-{n}"]["runs"][p] == 0 for n in (1, 2))]
    newly = [p for p in nev if any(runs[f"{c}-{n}"]["runs"][p] > 0 for n in (1, 2))]; newly2 = [p for p in nev if all(runs[f"{c}-{n}"]["runs"][p] > 0 for n in (1, 2))]
    L.append(f"{c} vs {bn}: baseline {bt} mean {bm:.1f}; candidate {ct} mean {cm:.1f}; change {100 * (cm - bm) / bm:+.1f}%; lowest baseline minus highest candidate {min(bt) - max(ct)}")
    L.append(f"    baseline always (4 of 4 in all four runs) {len(alw)}: still 4 of 4 in both candidate runs {len(still)}, 0 of 4 in both {len(gone)}; baseline never {len(nev)}: succeed in at least one candidate run {len(newly)}, in both {len(newly2)}")
print("\n".join(L)); open(here / "results/ch19_improve.log", "w").write("\n".join(L) + "\n")
