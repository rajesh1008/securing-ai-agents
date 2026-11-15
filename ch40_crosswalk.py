#!/usr/bin/env python3
"""Chapter 40, lab 5 (no model): the crosswalk with C20 (model provenance).  Chapter 38's 76 rows plus 11; checker issues, coverage per standard, what the LLM03 and LLM04 rows said before and now, the Art 15 row as an auditor reads it, digest."""
import sys, json
from collections import Counter, defaultdict
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
import ch35_collect as B
from bulwark.crosswalk import check, coverage, gaps, rendered, digest
from bulwark.crosswalk_data import CAT, rows38, rows40, na_rows
AS_OF = "2026-11-13"; LV = {c[0]: c[5] for c in B.CONTROLS}; LV["C18"] = "measured_in_simulation"; LV["C19"] = "measured_live_model"; LV["C20"] = "measured_in_simulation"
L = []; res = {}
for name, rr in (("Ch38 (76 rows, 19 controls)", rows38() + na_rows()), ("Ch40 (87 rows, 20 controls)", rows40() + na_rows())):
    iss = check(rr, CAT, LV, as_of=AS_OF); c = Counter(k for k, _ in iss); cov = coverage(rr, CAT)
    L.append(f"{name}: checker {dict(c)}; coverage " + "; ".join(f"{s} {v['mapped']}/{v['items']} (+{v['na']} NA)" for s, v in cov.items() if s in ('LLM25', 'ASI26', 'N600', 'I42K')))
    res[name] = dict(issues=dict(c), coverage=cov)
for it in ("LLM03", "LLM04"):
    for tag, rr in (("Ch38", rows38()), ("Ch40", rows40())):
        L.append(f"{it} {tag}: controls {sorted({r.control for r in rr if r.item == it})}")
def one_control(rr):
    sup = defaultdict(set)
    for r in rr:
        if r.std in ("ASI26", "LLM25", "N600", "I42K"): sup[(r.std, r.item)].add(r.control)
    return sorted(f"{s}:{i}" for (s, i), v in sup.items() if len(v) == 1), len(sup)
s38, n38 = one_control(rows38()); single, n40 = one_control(rows40())
L.append(f"items resting on one control: Ch38 {len(s38)} of {n38} mapped; Ch40 {len(single)} of {n40}; now shared with C20: {sorted(set(s38) - set(single))}")
art = [r for r in rows40() if r.item == "Art15" and r.control == "C20"][0]; L.append("Art15 row as rendered: " + rendered(art, CAT, LV["C20"]))
L.append(f"digest Ch38 {digest(rows38() + na_rows(), CAT)[:16]}  Ch40 {digest(rows40() + na_rows(), CAT)[:16]}")
by = Counter(r.rel for r in rows40() if r.control == "C20"); L.append(f"C20 rows by relation: {dict(by)}")
res["single"] = single; res["art15"] = rendered(art, CAT, LV["C20"])
open(here / "results/ch40_crosswalk.json", "w").write(json.dumps(res, indent=1, default=str)); open(here / "results/ch40_crosswalk.log", "w").write("\n".join(L) + "\n"); print("\n".join(L))
