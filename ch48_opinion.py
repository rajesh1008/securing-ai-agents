#!/usr/bin/env python3
"""Chapter 48, lab 3 (no model): the auditor's opinion, from stated rules.  Inputs: results/ch47_bundle.json (the release bundle after Chapter 47), results/ch48_audit.json (lab 1), results/ch48_sampling.json (lab 2).
Rules (stated as code, applied mechanically):  a FINDING is raised for each of: stale evidence (any), a control resting on one evidence item, a control whose only evidence is written by its author, an operating claim with no operating evidence, a seeded-defect class the procedures cannot catch,
and a population tested by sample where the sample's stated limit is more than twice the observed rate of the population test.   Two opinions, one per claim.  'Designed and exercised in simulation': SUPPORTED if nothing is stale and no money-path control rests on a single item, else SUPPORTED WITH EXCEPTIONS.  'Operating on real traffic': SUPPORTED only with an operating claim in the bundle and nothing stale, else NOT SUPPORTED.
Writes results/ch48_opinion.json and .log."""
import sys, json
from pathlib import Path
here = Path(__file__).resolve().parent; R = here / "results"
b = json.load(open(R / "ch47_bundle.json")); a = json.load(open(R / "ch48_audit.json")); s = json.load(open(R / "ch48_sampling.json"))
MONEY = {"C03", "C05", "C07", "C09", "C10", "C11", "C12", "C14", "C15", "C16", "C17", "C21", "C23"}  # controls that sit on the payment path in the Chapter 35 register
F = []
def find(sev, ref, text): F.append(dict(sev=sev, ref=ref, text=text))
stale = b["after"]["issues"].get("STALE_FOR_CODE", 0)
items = sorted({ln.split()[1].rstrip(":") for ln in open(R / "ch47_bundle.log") if ln.strip().startswith("STALE_FOR_CODE")})
if stale: find("MEDIUM", "bundle", f"{stale} STALE_FOR_CODE issues across {len(items)} evidence items ({', '.join(items)}): the evidence is older than the code it describes")
one = b["controls_resting_on_one_item"]
if one: find("MEDIUM", "bundle", f"{len(one)} of {b['after']['controls']} controls rest on a single evidence item: {', '.join(one)}")
author_only = b["item_kinds"]["UNIT"] + b["item_kinds"]["LAB_SIM"] + b["item_kinds"]["LAB_LIVE"]; total = sum(b["item_kinds"].values())
find("HIGH" if MONEY & set(one) else "MEDIUM", "bundle", f"{author_only} of {total} evidence items are scripts or tests written by the author of the control; {b['item_kinds']['REVIEW']} is a review by someone else")
if b["operating_claims"] == 0: find("MEDIUM", "bundle", "no control carries an 'operating' claim; every claim is simulation, live-model lab or test")
miss = [d for d in a["defects"] if d["name"].startswith("M") and not d["fired"]]
for d in miss: find("HIGH" if d["name"][:2] in ("M1", "M3") else "MEDIUM", "audit lab", f"seeded case '{d['name']}' passes every re-performance procedure")
r59 = s["random"]["59"]; obs = s["C"]["K"] / s["C"]["N"]
if r59["limit"] > 2 * obs: find("MEDIUM", "sampling", f"a clean random sample of 59 supports only 'below {r59['limit']*100:.1f}%' where the population rate is {obs*100:.1f}%: test the whole population by code")
hi = [f for f in F if f["sev"] == "HIGH"]; med = [f for f in F if f["sev"] == "MEDIUM"]
sim = "SUPPORTED" if not stale and not (MONEY & set(one)) else "SUPPORTED WITH EXCEPTIONS"
oper = "SUPPORTED" if b["operating_claims"] > 0 and not stale else "NOT SUPPORTED"
op = dict(designed_and_exercised_in_simulation=sim, operating_on_real_traffic=oper)
lines = [f"{i+1:2d}. {f['sev']:6s} [{f['ref']}] {f['text']}" for i, f in enumerate(F)]; lines.append(f"findings: {len(hi)} HIGH, {len(med)} MEDIUM"); lines.append(f"claim 'designed, and exercised in simulation and live-model labs': {sim}"); lines.append(f"claim 'operating on real traffic': {oper}")
print("\n".join(lines)); json.dump(dict(findings=F, opinion=op, log=lines), open(R / "ch48_opinion.json", "w"), indent=1); open(R / "ch48_opinion.log", "w").write("\n".join(lines) + "\n")
