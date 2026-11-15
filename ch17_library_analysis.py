#!/usr/bin/env python3
"""Chapter 17, lab 1b (no new calls): analyses of results/ch17_library_live.json. Range of each axis's marginal rates, interactions (goal x position, goal x voice), where the never-succeeding payloads sit, and flakiness."""
import json, itertools
from collections import Counter, defaultdict
from pathlib import Path
here = Path(__file__).resolve().parent
import sys; sys.path.insert(0, str(here))
from bulwark.payloads import generate
R = json.load(open(here / "results/ch17_library_live.json")); S = R["summary"]; lib = {p.id: p for p in generate()}
def rate(runs, pred):
    t = n = 0
    for run in runs:
        for pid, v in S[run].items():
            if pred(lib[pid]): t += v["took"]; n += v["n"]
    return t, n
P = ("PLAIN-1", "PLAIN-2"); L_ = []
L_.append("range of marginal success rate per axis (plain, both runs pooled, 960 calls): highest minus lowest value")
for axis in ("goal", "voice", "frame", "position"):
    vals = {v: rate(P, lambda p, v=v: getattr(p, axis) == v) for v in sorted({getattr(p, axis) for p in lib.values()})}
    rr = {k: t / n for k, (t, n) in vals.items()}; L_.append(f"  {axis:9s} " + "  ".join(f"{k} {rr[k]:.2f}" for k in rr) + f" | range {max(rr.values()) - min(rr.values()):.2f}")
L_.append("goal x position (plain pooled, successes of 80 calls each)")
for g in ("account", "amount", "number", "vendor"): L_.append(f"  {g:8s} " + "  ".join(f"{pos} {rate(P, lambda p, g=g, pos=pos: p.goal == g and p.position == pos)[0]:3d}/{rate(P, lambda p, g=g, pos=pos: p.goal == g and p.position == pos)[1]}" for pos in ("top", "billto", "bottom")))
L_.append("goal x voice (plain pooled, of 48 calls each)")
for g in ("account", "amount", "number", "vendor"): L_.append(f"  {g:8s} " + "  ".join(f"{v} {rate(P, lambda p, g=g, v=v: p.goal == g and p.voice == v)[0]:3d}" for v in ("process", "vendor", "principal", "blunt", "thought")))
dead = [pid for pid in lib if S["PLAIN-1"][pid]["took"] == 0 and S["PLAIN-2"][pid]["took"] == 0]; alw = [pid for pid in lib if S["PLAIN-1"][pid]["took"] == 4 and S["PLAIN-2"][pid]["took"] == 4]
for name, ids in (("never succeeded in either plain run", dead), ("succeeded 4 of 4 in both", alw)):
    L_.append(f"{name}: {len(ids)}; by goal {dict(Counter(lib[i].goal for i in ids))}; by voice {dict(Counter(lib[i].voice for i in ids))}; by position {dict(Counter(lib[i].position for i in ids))}")
mixed = [pid for pid in lib if pid not in dead and pid not in alw]
L_.append(f"mixed or unstable: {len(mixed)}; by voice {dict(Counter(lib[i].voice for i in mixed))}")
sm = Counter(S["PLAIN-1"][pid]["took"] + S["PLAIN-2"][pid]["took"] for pid in lib); L_.append("distribution of successes per payload over 8 trials (2 runs x 4 hosts): " + ", ".join(f"{k}:{sm[k]}" for k in sorted(sm)))
hard = [pid for pid in lib if S["HARD"][pid]["took"] > 0]; L_.append(f"HARD: payloads with any success {len(hard)}: " + ", ".join(f"{p}={S['HARD'][p]['took']}" for p in hard))
print("\n".join(L_)); open(here / "results/ch17_library_analysis.log", "w").write("\n".join(L_) + "\n")
