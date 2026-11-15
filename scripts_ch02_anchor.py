#!/usr/bin/env python3
"""Chapter 2 lab: what a hash chain alone cannot detect, and what a separately held head hash adds."""
import json, shutil, time
from pathlib import Path
from bulwark.authority import EvidenceChain
from bulwark.anchor import AnchorService, anchor_chain, verify_with_anchors, rewrite_and_rehash
R = Path(__file__).resolve().parent / "results"
src = R / "ch02_evidence_clean_registry.jsonl"
svc = AnchorService(Path("/tmp/anchor_store.jsonl"))   # lives outside the writer's directory, key in memory only
n = anchor_chain(src, svc, every=10)
out = {"records": sum(1 for _ in open(src)), "anchors": n, "anchor_seqs": [a["seq"] for a in svc.anchors()]}
def report(label, p):
    c_ok, c_bad = EvidenceChain.verify(p); a_ok, a_msg = verify_with_anchors(p, svc)
    out[label] = dict(chain_only=("pass" if c_ok else f"fail at {c_bad}"), chain_plus_anchor=("pass" if a_ok else "fail"), detail=a_msg)
report("untouched", src)
# 1. in-place edit of record 7 (Section 2.13): chain alone catches it
rec_lines = [json.loads(l) for l in open(src)]
print("record 7 before:", {k: rec_lines[7][k] for k in ("tool", "allow", "executed", "reason")})
t = R / "ch02_evidence_clean_registry_tampered.jsonl"; report("in_place_edit", t)
# 2. attacker with file access edits record 7 and recomputes every later hash
r2 = R / "ch02_evidence_rehashed.jsonl"
rewrite_and_rehash(src, r2, 7, dict(allow=True, executed=False, reason="ok")); report("edit_and_rehash", r2)
# 3. attacker deletes the last 12 records (the hash chain stays internally valid)
r3 = R / "ch02_evidence_truncated.jsonl"
r3.write_text("".join(l for i, l in enumerate(open(src)) if i < 28)); report("truncate_last_12", r3)
# 4. attacker deletes records 20..27 and rehashes the rest
lines = [json.loads(l) for l in open(src)]
r4 = R / "ch02_evidence_cutmiddle.jsonl"; r4.write_text("".join(json.dumps({k: v for k, v in l.items()}, sort_keys=True) + "\n" for i, l in enumerate(lines) if not 20 <= i < 28))
# recompute links over the shortened file
rewrite_and_rehash(r4, r4, -1, {}); report("cut_middle_rehash", r4)
(R / "ch02_anchor.json").write_text(json.dumps(out, indent=1))
print(json.dumps(out, indent=1))
