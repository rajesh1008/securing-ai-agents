#!/usr/bin/env python3
"""Chapter 14, walkthrough. No model (the rule extractor reads, so the output is reproducible). Five documents through extraction, verification and the evidence vault of Chapter 13."""
import sys, json, random, time
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
from bulwark.docagent import *
from bulwark.evidence import Vault, ChainLog
import ch14_corpus as C
rec = C.make_records(); V = Vault(b"\x14" * 32, 10); out = []
def say(s): out.append(s); print(s)
cases = [("clean", "I002"), ("H2_account_swap", "I003"), ("H6_hidden_layer", "I004"), ("H1_instruction", "I005"), ("H5_duplicate_paid", "I006")]
for k, (cls, i) in enumerate(cases):
    d = C.clean(rec, i, random.Random(f"w{i}"), noise=False)[0] if cls == "clean" else C.hostile(rec, i, cls, random.Random(f"w{i}"))
    ex = parse_rules(d.text_layer); v = verify(d, ex, rec, level=3, ex_visible=parse_rules(d.visible)); e = evidence_event(V, "biz_hcb", d, ex, v, "rules-1.0", 1000 + k)
    say(f"{k+1} {cls:18s} extractor read: number {ex.number}, amount {ex.amount_cents}, account {ex.account} -> route {v.route}, reasons {v.reasons or '[]'}; effect {v.effect}")
V.seal("biz_hcb"); rows = V.logs["biz_hcb"].rows
say(f"chain verifies: {V.verify('biz_hcb')}; rows {len(rows)}; the attacker's account number appears in any row: {any(C.ATT in json.dumps(r) for r in rows)}; in the content store (decrypted, tenant key): {any(C.ATT in V.stores['biz_hcb'].get(f'{r['seq']}:document').decode() for r in rows)}")
say("row 2 (typed): " + json.dumps({k: v for k, v in rows[1].items() if k not in ('prev', 'hash')}, sort_keys=True)[:600])
N = 2000; d = C.clean(rec, "I002", random.Random(1), noise=False)[0]; t0 = time.perf_counter()
for _ in range(N): ex = parse_rules(d.text_layer); verify(d, ex, rec, level=3, ex_visible=parse_rules(d.visible))
say(f"cost: extract and verify one invoice (rules, L3): {(time.perf_counter()-t0)/N*1e6:.0f} us")
json.dump(out, open(here / "results/ch14_walkthrough.json", "w"), indent=1); open(here / "results/ch14_walkthrough.log", "w").write("\n".join(out) + "\n")
