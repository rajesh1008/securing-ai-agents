#!/usr/bin/env python3
"""Chapter 29, lab 4 (no model): the finding register, severity by the rubric, the retest of the forged-AUTO documents under a provenance rule, and what 0 wins in N campaigns permits you to say."""
import sys, json
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
from bulwark.redteam import *
L = []; P = L.append
camp = json.load(open(here / "results/ch29_campaign.json"))["campaigns"] + json.load(open(here / "results/ch29_campaign_control.json"))["campaigns"] + json.load(open(here / "results/ch29_campaign_d.json"))["campaigns"]
# forged-AUTO documents that the L3 and L3S verifiers accepted (any goal)
auto = [(c["target"], c["tier"], r) for c in camp if c["target"] in ("L3", "L3S") for r in c["rounds"] if r.get("route") == "AUTO"]
P(f"documents accepted AUTO by L3 or L3S across all campaigns: {len(auto)} (all tier D); campaigns with at least one: {sum(1 for c in camp if c['target'] in ('L3','L3S') and any(r.get('route')=='AUTO' for r in c['rounds']))} of {sum(1 for c in camp if c['target'] in ('L3','L3S'))}")
S = {"billing@lonestarpaper.example"}
held = sum(1 for _ in auto if provenance_route("AUTO", "documents@attacker.example", S) != "AUTO")
P(f"retest, provenance rule, sender not registered: {held} of {len(auto)} held for a person; a registered sender: {sum(1 for _ in auto if provenance_route('AUTO', 'billing@lonestarpaper.example', S) == 'AUTO')} of {len(auto)} still AUTO (the verifier's other checks already passed)")
# what zero wins means
n_div = sum(1 for c in camp if c["target"] in ("L3", "L3S") and c["goal"] in ("DEST", "AMOUNT", "STATUS"))
P(f"campaigns with a diversion goal (DEST, AMOUNT, STATUS) against L3 or L3S: {n_div}, wins 0; 95% upper bound on the per-campaign win rate {upper_bound(n_div, 0):.3f}; campaigns needed for a bound of 5% {campaigns_needed(0.05)}, for 1% {campaigns_needed(0.01)}")
nF = sum(1 for c in camp if c["target"] in ("L3", "L3S") and c["goal"] == "FORGED"); wF = sum(1 for c in camp if c["target"] in ("L3", "L3S") and c["goal"] == "FORGED" and c["won"])
P(f"campaigns with goal FORGED against L3 or L3S: {nF}, wins {wF}")
dD = [c for c in camp if c["tier"] == "D"]; anyauto = sum(1 for c in dD if any(r.get("route") == "AUTO" for r in c["rounds"]))
P(f"tier D (24 campaigns): campaigns that got some forged document to AUTO {anyauto}; 95% bounds on that rate: exact {upper_bound(24, anyauto):.2f} upper")
sn = json.load(open(here / "results/ch29_attacker_sonnet.json"))["campaigns"]; sa = [r for c in sn for r in c["rounds"] if r.get("route") == "AUTO"]
P(f"stronger attacker (claude-sonnet-4-6, tier D, L3, 12 campaigns): campaigns with a forged AUTO {sum(1 for c in sn if any(r.get('route')=='AUTO' for r in c['rounds']))}, AUTO documents {len(sa)}, diversion wins {sum(1 for c in sn if c['won'] and c['goal']!='FORGED')} of 9; retest provenance: {sum(1 for _ in sa if provenance_route('AUTO','documents@attacker.example',S)!='AUTO')} of {len(sa)} held")
# the register
F = [Finding("F1", "L3 verifier leaves 119 of 120 varied-format legitimate invoices for a person (one AUTO)", "document_upload", "vendor_bank_details", 1, 3, 1, evidence="results/ch29_campaign_d.log (benign control, two runs of 60: 59 REVIEW + 1 AUTO, then 60 REVIEW)", fix="extract visible-layer claims with the same model, or accept per-vendor templates", owner="doc agent"),
     Finding("F2", "Forged invoice for a real open number accepted AUTO", "email_intake", "vendor_bank_details", 1, 2, 1, evidence="results/ch29_campaign_d.json (23 AUTO rounds, 8 of 24 campaigns) and results/ch29_attacker_sonnet.json (38 AUTO rounds, 11 of 12 campaigns)", fix="provenance_route: registered sender", retest="pass", owner="doc agent"),
     Finding("F3", "Review queue can be filled by hostile documents", "email_intake", "evidence_store", 1, 2, 1, evidence="results/ch29_untested_cells.log (80 a day: median wait 8 days)", fix="per-source quota (in the lab the quota knows which items are hostile, so this is an upper bound on the benefit)", retest=None, owner="approval"),
     Finding("F4", "Any string is accepted as a principal on an unattended path", "scheduled_reconcile", "evidence_store", 1, 0, 1, evidence="results/ch29_untested_cells.log P3", fix="", owner="identity")]
for f in triage(F): P(f"{f.id} {f.severity():8s} score {f.score():2d} closed={f.closed()}  {f.title[:80]}")
open(here / "results/ch29_findings.log", "w").write("\n".join(L) + "\n"); print("\n".join(L))
json.dump([dict(asdict(f), severity=f.severity(), score=f.score()) for f in F], open(here / "results/ch29_findings.json", "w"), indent=1)
