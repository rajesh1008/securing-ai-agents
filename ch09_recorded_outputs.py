#!/usr/bin/env python3
"""Chapter 9, lab 2: what models actually emitted. Replays the 215 raw model outputs recorded in Chapters 1, 2, 5 and 6
(claude-haiku-4-5-20251001, 9 November 2026) through the envelope and field rules. No new model calls."""
import sys, json, re
from pathlib import Path
from collections import Counter
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
from bulwark.quill_lab import extract_json
from bulwark.schema import _FENCE
R = here / "results"
FILES = ["ch01_matrix", "ch01_polite", "ch02_live_tool", "ch05_destination", "ch05_unknown_terms", "ch06_token_in_context"]
raws = []
for f in FILES:
    d = json.load(open(R / f"{f}.json")); rows = d["rows"] if isinstance(d, dict) else d
    raws += [(f, r["raw"]) for r in rows if "raw" in r]
L = []; P = L.append
P(f"recorded outputs: {len(raws)}  " + ", ".join(f"{f}={sum(1 for a,_ in raws if a==f)}" for f in FILES))
env = Counter(); keys = Counter(); parsed = []
for f, raw in raws:
    t = raw.strip()
    if t.startswith("{") and t.endswith("}"): e = "bare_json"
    elif _FENCE.fullmatch(t): e = "exact_fence"
    elif "```" in t: e = "prose_plus_fence"
    elif "{" in t: e = "prose_with_braces"
    else: e = "prose_only"
    env[e] += 1
    try: o = extract_json(raw); ok = isinstance(o, dict)
    except Exception: o, ok = None, False
    if ok: parsed.append((f, o))
P("envelope: " + ", ".join(f"{k}={v}" for k, v in env.most_common()))
bare = 0
for _, r in raws:
    try: json.loads(r); bare += 1
    except Exception: pass
P(f"json.loads(raw) succeeds on {bare} of {len(raws)}; Quill's extract_json (fence strip then loads) succeeds on {len(parsed)} of {len(raws)}")
P("quill_lab.SYSTEM says 'Never include markdown. JSON only.' (the other labs' prompts were written separately and I have not checked each one for that sentence)")
pay = [o for _, o in parsed if o.get("kind") == "initiate_payment"]
P(f"\nparsed objects with kind=initiate_payment: {len(pay)}")
kc = Counter(k for o in pay for k in o)
P("  keys (count): " + ", ".join(f"{k}={v}" for k, v in kc.most_common()))
NEW = {"invoice_id", "payee_id", "amount_cents", "rationale"}
P(f"  carry principal_id: {sum('principal_id' in o for o in pay)}, business_id: {sum('business_id' in o for o in pay)}  (identity fields the model restated; Quill v0.2 setdefault lets a model-written value stand)")
P(f"  principal_id values: {dict(Counter(o.get('principal_id') for o in pay))}")
P(f"  business_id values: {dict(Counter(o.get('business_id') for o in pay))}")
P(f"  carry a field outside the Chapter 9 pay spec ({sorted(NEW)}): {sum(bool(set(o) - NEW) for o in pay)} of {len(pay)}; carry invoice_id: {sum('invoice_id' in o for o in pay)}")
types = Counter(type(o.get('amount_cents')).__name__ for o in pay)
P(f"  amount_cents types: {dict(types)}")
mem = [o['memo'] for o in pay if o.get('memo')]
P(f"  memo present: {len(mem)}; memo longer than 80 chars: {sum(len(m) > 80 for m in mem)}; memo values containing a newline: {sum(chr(10) in m for m in mem)}")
rat = [o['rationale'] for o in pay if o.get('rationale')]
P(f"  rationale length (chars) min/median/max: {min(map(len, rat))}/{sorted(map(len, rat))[len(rat)//2]}/{max(map(len, rat))}; over 280: {sum(len(x) > 280 for x in rat)}")
# who set the extra fields: tool-use objects from ch02
tl = [o for _, o in parsed if "tool" in o]
P(f"\nch02 tool-menu style objects with 'tool' and nested 'args': {len(tl)}; nested args objects: {sum(isinstance(o.get('args'), dict) for o in tl)}")
from bulwark.schema import _no_dups, _bad_const, _bad_float, Reject
syn = Counter(); where = []
for f, raw in raws:
    m = _FENCE.fullmatch(raw.strip())
    if not m: continue
    try: json.loads(m.group(1), object_pairs_hook=_no_dups, parse_constant=_bad_const, parse_float=_bad_float); syn["clean"] += 1
    except Reject as e: syn[e.code] += 1; where.append((f, m.group(1)[:90].replace(chr(10), " ")))
    except Exception: syn["other_error"] += 1
P(f"\nsyntax rules (duplicate keys, NaN, floats) on the {sum(syn.values())} exactly-fenced replies: {dict(syn)}")
for f, t in where: P(f"  {f}: {t}")
print("\n".join(l for l in L if l)); (R / "ch09_recorded_outputs.log").write_text("\n".join(l for l in L if l) + "\n")
