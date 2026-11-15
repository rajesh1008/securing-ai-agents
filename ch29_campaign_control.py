#!/usr/bin/env python3
"""Chapter 29, lab 2b: the positive control.  The same harness, insider knowledge (tier C), against the early design (L1) and against L2 (verify level 2).
A red-team harness that has never found anything proves nothing until it has found something known.  Writes results/ch29_campaign_control.json."""
import sys, json, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
import ch29_campaign as K
K.C  # noqa
_orig = K.run_pipeline
def run2(target, doc):
    if target != "L2": return _orig(target, doc)
    import re
    raw = ""
    for a in range(3):
        try:
            m = K.client.messages.create(model=K.MODEL, max_tokens=500, system=K.X.SYS, messages=[{"role": "user", "content": f"<document>\n{doc.text_layer}\n</document>"}]); raw = "".join(getattr(b, "text", "") for b in m.content); break
        except Exception: time.sleep(2 + 3 * a)
    mt = re.search(r"\{.*\}", raw, re.S)
    try: ex = K.X.to_ex(json.loads(mt.group(0)))
    except Exception: return None, None
    return ex, K.verify(doc, ex, K.rec, level=2)
K.run_pipeline = run2
jobs = []; k = 1000; G = list(K.GOALS)
for target in ("L1", "L2"):
    for i in range(12): jobs.append((k, "C", G[i % 4], target)); k += 1
t0 = time.time()
with ThreadPoolExecutor(6) as ex: res = list(ex.map(K.campaign, jobs))
json.dump(dict(model=K.MODEL, date=time.strftime("%Y-%m-%d %H:%M %Z"), campaigns=res), open(here / "results/ch29_campaign_control.json", "w"), indent=1)
from collections import defaultdict
S = defaultdict(lambda: [0, 0, []]); S2 = defaultdict(lambda: [0, 0])
for c in res:
    s = S[c["target"]]; s[0] += 1; s[1] += c["won"]; s[2] += [c["first"]] if c["won"] else []
    S2[(c["target"], c["goal"])][0] += 1; S2[(c["target"], c["goal"])][1] += c["won"]
for kx, (n, w, f) in sorted(S.items()): print(kx, "tier C campaigns", n, "won", w, "first-win rounds", sorted(f))
for kx, v in sorted(S2.items()): print(kx, v)
print(f"{time.time()-t0:.0f}s")
