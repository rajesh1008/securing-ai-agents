#!/usr/bin/env python3
"""Chapter 29, lab 6 (no model): is ten rounds enough?  Discovery curves from the saved campaigns: the share of tier D campaigns that had got a forged document to AUTO by round r,
for the Haiku attacker (24 campaigns, L3 and L3S) and the Sonnet attacker (12 campaigns, L3).  Also the rounds each attacker spent on documents the extractor could not read or the attacker could not format."""
import json, sys
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
from bulwark.redteam import discovery_curve
from collections import Counter
H = json.load(open(here / "results/ch29_campaign_d.json"))["campaigns"]; S = json.load(open(here / "results/ch29_attacker_sonnet.json"))["campaigns"]
def first_auto(c): return next((r["round"] + 1 for r in c["rounds"] if r.get("route") == "AUTO"), None)
L = []; P = L.append
for name, cs in (("Haiku attacker, tier D, L3+L3S", H), ("Sonnet attacker, tier D, L3", S)):
    f = [first_auto(c) for c in cs if first_auto(c)]
    cur = discovery_curve(f, len(cs), 10)
    P(f"{name}: {len(cs)} campaigns, {len(f)} reached a forged AUTO; first-AUTO rounds {sorted(f)}")
    P("   share reached by round 1..10: " + " ".join(f"{x:.2f}" for x in cur))
    R = Counter(); 
    for c in cs:
        for r in c["rounds"]: R["bad_json" if r.get("bad_json") else "unreadable" if r.get("parse_fail") else r["route"]] += 1
    P("   rounds by outcome: " + str(dict(R)))
    P("   AUTO share of rounds after the first AUTO in a campaign: " + (lambda a, b: f"{a} of {b}")(sum(1 for c in cs if first_auto(c) for r in c["rounds"] if r.get("route") == "AUTO" and r["round"] + 1 > first_auto(c)), sum(1 for c in cs if first_auto(c) for r in c["rounds"] if r["round"] + 1 > first_auto(c))))
# note: campaigns end at the first WIN, not the first AUTO, so a campaign whose goal was diversion kept going after an AUTO
open(here / "results/ch29_budget.log", "w").write("\n".join(L) + "\n"); print("\n".join(L))
