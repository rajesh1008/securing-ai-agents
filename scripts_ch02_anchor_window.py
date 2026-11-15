#!/usr/bin/env python3
"""The window: records written after the last anchor can be rewritten undetected until the next anchor."""
import json, shutil
from pathlib import Path
from bulwark.authority import EvidenceChain
from bulwark.anchor import AnchorService, anchor_chain, verify_with_anchors, rewrite_and_rehash
R = Path(__file__).resolve().parent / "results"
work = Path("/tmp/win.jsonl"); shutil.copy(R / "ch02_evidence_clean_registry.jsonl", work)
# anchored at records 9,19,29 (every 10); the last 10 records (30..39) are in the window
svc = AnchorService(Path("/tmp/anchor_win.jsonl"))
lines = [json.loads(l) for l in open(work)]
for i in (9, 19, 29): svc.submit(i, lines[i]["hash"])
out = {}
for idx in (35, 25):
    p = Path(f"/tmp/win_edit{idx}.jsonl"); rewrite_and_rehash(work, p, idx, dict(allow=True, reason="ok"))
    ok, msg = verify_with_anchors(p, svc); out[f"edit_record_{idx}"] = dict(passes=ok, detail=msg)
Path(R / "ch02_anchor_window.json").write_text(json.dumps(out, indent=1)); print(json.dumps(out, indent=1))
