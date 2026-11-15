#!/usr/bin/env python3
"""Chapter 29, lab 5: does a stronger attacker change the result?  Tier D, L3, 12 campaigns with the attacker model claude-sonnet-4-6 (the extractor under test stays claude-haiku-4-5-20251001).
Writes results/ch29_attacker_sonnet.json."""
import sys, json, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from collections import Counter
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
import ch29_campaign as K
def call(system, msgs, mt=900):
    for a in range(3):
        try:
            m = K.client.messages.create(model="claude-sonnet-4-6", max_tokens=mt, system=system, messages=msgs); return "".join(getattr(b, "text", "") for b in m.content)
        except Exception as e: time.sleep(2 + 3 * a)
    return ""
K.call = call            # only the attacker uses K.call; the extractor calls the client directly
G = list(K.GOALS); jobs = [(3000 + i, "D", G[i % 4], "L3") for i in range(12)]
t0 = time.time()
with ThreadPoolExecutor(6) as ex: res = list(ex.map(K.campaign, jobs))
json.dump(dict(attacker="claude-sonnet-4-6", extractor=K.MODEL, date=time.strftime("%Y-%m-%d %H:%M %Z"), campaigns=res), open(here / "results/ch29_attacker_sonnet.json", "w"), indent=1)
R = Counter(r.get("route") if not r.get("bad_json") else "bad_json" for c in res for r in c["rounds"])
print("campaigns", len(res), "won (diversion or FORGED goal)", sum(c["won"] for c in res), "first rounds", [c["first"] for c in res if c["won"]])
print("rounds", sum(len(c["rounds"]) for c in res), dict(R), "campaigns with any AUTO", sum(1 for c in res if any(r.get("route") == "AUTO" for r in c["rounds"])))
print("by goal:", {g: [sum(1 for c in res if c["goal"] == g and c["won"]), sum(1 for c in res if c["goal"] == g)] for g in G}, f"{time.time()-t0:.0f}s")
