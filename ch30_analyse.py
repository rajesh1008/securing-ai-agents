#!/usr/bin/env python3
"""Chapter 30, lab 1 analysis (no model calls): per arm, wins, findings across campaigns, variants, first-win rounds, drift (similarity of each later win to the campaign's first win),
round at which each finding key first appeared, and an approximate cost per arm (calls in the arm x the run's mean cost per call).  Reads results/ch30_loop.json, writes results/ch30_analyse.json."""
import json, statistics as st
from collections import defaultdict
from pathlib import Path
import sys; here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
from bulwark.autoredteam import FindingIndex, similarity
d = json.load(open(here / "results/ch30_loop.json")); M = d["meter"]; per_call = M["usd"] / M["calls"]
arms = defaultdict(list)
for c in d["campaigns"]: arms[c["arm"]].append(c)
out = {}
for arm, cs in arms.items():
    idx = FindingIndex(); first = []; sims = []; key_first = defaultdict(list); rounds = 0; bad = 0; won_c = 0; wins = 0; consec = []
    for c in cs:
        fw = None; seen = set(); prev = None
        for r in c["rounds"]:
            rounds += 1; bad += bool(r.get("bad_json") or r.get("parse_fail"))
            if not r.get("won"): continue
            wins += 1; idx.add(r["key"], r["variant"], f"{c['cid']}-{r['round']}")
            if fw is None: fw = r; first.append(r["round"] + 1)
            else: sims.append(similarity(fw["visible"], r["visible"]))
            if prev is not None: consec.append(similarity(prev["visible"], r["visible"]))
            prev = r
            if r["key"] not in seen: seen.add(r["key"]); key_first[r["key"]].append(r["round"] + 1)
        won_c += fw is not None
    calls = rounds * 2
    out[arm] = dict(campaigns=len(cs), campaigns_won=won_c, rounds=rounds, bad_rounds=bad, wins=wins, **{k: v for k, v in idx.summary().items() if k not in ("by_key", "wins")}, by_key=idx.summary()["by_key"],
                    campaigns_per_key={k: len(v) for k, v in key_first.items()}, median_round_key_first={k: st.median(v) for k, v in key_first.items()},
                    first_win_rounds=sorted(first), sim_to_first_mean=round(st.mean(sims), 3) if sims else None, sim_consecutive_mean=round(st.mean(consec), 3) if consec else None,
                    approx_usd=round(calls * per_call, 2), usd_per_finding=round(calls * per_call / max(1, len(idx.findings)), 2), usd_per_win=round(calls * per_call / max(1, wins), 3))
# a reference for the similarity scale: two clean template invoices of different vendors and numbers
import ch14_corpus as C, random
rec = C.make_records(); ids = [i for i, x in rec.invoices.items() if x["status"] == "open"]
ref = [similarity(C.clean(rec, a, random.Random(1), noise=False)[0].visible, C.clean(rec, b, random.Random(2), noise=False)[0].visible) for a, b in zip(ids[:20], ids[20:40])]
out["_reference"] = dict(template_pair_similarity_mean=round(st.mean(ref), 3), meter=M, per_call_usd=round(per_call, 5))
json.dump(out, open(here / "results/ch30_analyse.json", "w"), indent=1)
for k, v in out.items(): print(k, json.dumps(v)[:900])
