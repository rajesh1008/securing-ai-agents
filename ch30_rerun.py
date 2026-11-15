#!/usr/bin/env python3
"""Chapter 30, lab 3: is a stored win still a win?  Every win from lab 1 is replayed twice: (a) from the cached extraction (deterministic, no model) and (b) with a fresh live extraction
(claude-haiku-4-5-20251001, same prompt), through the pipeline of the arm that won it.  Also times the cached replay of the whole lab-2 corpus.  Writes results/ch30_rerun.json."""
import sys, json, time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
import ch30_loop as L
from bulwark.docagent import Document
import ch14_live_extract as X
from collections import Counter
d = json.load(open(here / "results/ch30_loop.json")); wins = [(c["arm"], c["cid"], r) for c in d["campaigns"] for r in c["rounds"] if r.get("won")]
def cached(job):
    arm, cid, r = job; doc = Document("w", r["visible"], r.get("hidden") or "")
    from bulwark.docagent import verify, parse_rules
    from bulwark.autoredteam import Envelope, sender_route
    ex = X.to_ex(r["ex"]); lvl = 1 if arm.startswith("L1") else 3
    v = verify(doc, ex, L.rec, level=lvl, ex_visible=(parse_rules(doc.visible) if lvl >= 3 else None)); route = v.route
    if arm.startswith("S"): route = sender_route(route, (v.effect or {}).get("payee_id"), Envelope(r.get("header_from") or L.ATTACKER_CHANNEL, L.ATTACKER_CHANNEL), L.REGISTERED, trust="header")[0]
    return route
def live(job):
    arm, cid, r = job; doc = Document("w", r["visible"], r.get("hidden") or ""); j, route, rv = L.run_round(arm, doc, r.get("header_from")); return route
t0 = time.time(); c_routes = [cached(w) for w in wins]; t_cached = time.time() - t0
with ThreadPoolExecutor(8) as ex: l_routes = list(ex.map(live, wins))
by = Counter(); 
for (arm, cid, r), a, b in zip(wins, c_routes, l_routes): by[(arm, a, b)] += 1
out = dict(model=L.MODEL, date=time.strftime("%Y-%m-%d %H:%M %Z"), wins=len(wins), cached_auto=sum(x == "AUTO" for x in c_routes), live_auto=sum(x == "AUTO" for x in l_routes),
           cached_replay_seconds=round(t_cached, 3), by_arm={f"{k[0]} cached={k[1]} live={k[2]}": v for k, v in sorted(by.items())}, calls=L.meter.calls, tokens_in=L.meter.tokens_in, tokens_out=L.meter.tokens_out, usd=round(L.meter.usd(), 3))
json.dump(out, open(here / "results/ch30_rerun.json", "w"), indent=1); print(json.dumps(out, indent=1))
