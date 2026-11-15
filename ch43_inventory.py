#!/usr/bin/env python3
"""Chapter 43, labs 1 and 3 (no model): Quill's components against the definition of a model in the 2026 interagency guidance (author's reading, bulwark/modelrisk.py), a materiality tier for each,
and the validation pack: for every component that is a model or is generative/agentic, which of the guidance's elements has evidence, at what level (Chapter 35 kinds).
Evidence ids E01-E30 are the Chapter 35 bundle's; E31-E33 are added here (Chapter 43 outcomes lab, Chapter 33 responder lab, Chapter 41 creep lab); D-items are the chapters' written rationale (REVIEW).
Writes results/ch43_inventory.json and .log."""
import sys, json
from pathlib import Path
from collections import Counter
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
from bulwark.modelrisk import Component, classify, tier, pack, ELEMENTS, IN_SCOPE, OUT_GENAI
import ch35_collect as B
ITEMS = {i[0]: (i[2], i[3]) for i in B.ITEMS}
ITEMS.update({"E31": ("LAB_LIVE", ("modelrisk",)), "E32": ("LAB_LIVE", ("incident",)), "E33": ("LAB_LIVE", ("promptrelease",))})
for d in ("D05", "D08", "D14", "D18", "D32", "D33", "D36", "D38", "D40", "D41"): ITEMS[d] = ("REVIEW", ())
ITEMS["OWN"] = ("REVIEW", ())   # a named owner in the Chapter 35 control list or the Chapter 41 register
C = Component
COMPS = [
 C("M01", "invoice field extractor (Haiku 4.5)", "14, 43", "llm", "text", "payment", vendor=True, owner="Emily Carter", gate_after=True, evidence=("E07", "E16", "E31")),
 C("M02", "vendor bank-change classifier (own, bag of words)", "40", "ml_classifier", "label", "hold", owner="Kevin Brandt", gate_after=True, evidence=("E29",)),
 C("M03", "amount detector (vendor history baseline)", "32, 41", "statistical", "estimate", "alert", owner="Ian Walsh", evidence=("E13",)),
 C("M04", "prompt release gate floor (spread of identical runs plus margin)", "18, 41", "statistical", "estimate", "release", owner="Emily Carter", gate_after=False, evidence=("E16", "E33")),
 C("M05", "model second reviewer on payments", "8", "llm", "label", "hold", vendor=True, owner="", gate_after=True, evidence=("E18",)),
 C("M06", "coordinator agent (multi-agent drafting)", "38", "agent", "text", "text_only", vendor=True, owner="Nina Cole", evidence=("E26", "E27")),
 C("M07", "fallback model for degraded mode (Sonnet 4.6)", "36", "llm", "text", "payment", vendor=True, owner="Kevin Brandt", gate_after=True, evidence=("E25",)),
 C("M08", "extractor confidence threshold (routes to review)", "36, 41", "statistical", "label", "hold", owner="security", evidence=("E25",)),
 C("M09", "hosted-model behavioural fingerprint", "40", "statistical", "estimate", "alert", owner="Kevin Brandt", evidence=("E30",)),
 C("M10", "incident responder model (reads a case, recommends)", "33", "llm", "text", "text_only", vendor=True, owner="Ian Walsh", evidence=("E32",)),
 C("M11", "money gate M1-M8", "8", "rules", "decision", "payment", owner="Sophie Adler", evidence=("E02",)),
 C("M12", "egress allow-list", "12", "rules", "decision", "text_only", owner="Kevin Brandt", evidence=("E04",)),
 C("M13", "evidence chain and anchors", "13", "crypto", "record", "evidence", owner="Kevin Brandt", evidence=("E06",)),
 C("M14", "per-task budgets", "2, 7", "arithmetic", "decision", "payment", owner="Kevin Brandt", evidence=("E09",)),
 C("M15", "detector merge and alert routing rules", "32", "rules", "decision", "alert", owner="Ian Walsh", evidence=("E13",)),
 C("M16", "rota scorecard", "41", "arithmetic", "record", "text_only", owner="Ian Walsh", evidence=()),
]
# which evidence the author counts for each element of each component (written by hand; this is the argument a validator would check)
EMAP = {}
def put(c, el, *ids): EMAP[(c, el)] = ids
D = {"M01": "D14", "M02": "D40", "M03": "D32", "M04": "D18", "M05": "D08", "M06": "D38", "M07": "D36", "M08": "D36", "M09": "D40", "M10": "D33"}
for c in COMPS:
    if c.id in D: put(c.id, "conceptual_soundness", D[c.id])
    if c.owner and c.owner != "security": put(c.id, "governance_roles", "OWN")
put("M01", "outcomes_analysis", "E31"); put("M01", "development_and_use_testing", "E07", "E16"); put("M01", "third_party", "E30"); put("M01", "ongoing_monitoring", "E33")
put("M02", "outcomes_analysis", "E29"); put("M02", "development_and_use_testing", "E29", "E01")
put("M03", "outcomes_analysis", "E13"); put("M03", "development_and_use_testing", "E01", "E13"); put("M03", "ongoing_monitoring", "E13")
put("M04", "outcomes_analysis", "E16", "E33"); put("M04", "development_and_use_testing", "E01")
put("M05", "outcomes_analysis", "E18"); put("M05", "third_party", "E30")
put("M06", "outcomes_analysis", "E27"); put("M06", "development_and_use_testing", "E26"); put("M06", "third_party", "E30")
put("M07", "outcomes_analysis", "E25"); put("M07", "third_party", "E30")
put("M08", "outcomes_analysis", "E25")
put("M09", "outcomes_analysis", "E30"); put("M09", "development_and_use_testing", "E30")
put("M10", "outcomes_analysis", "E32"); put("M10", "third_party", "E30")
def main():
    L = []; R = {"components": {}}
    cls = Counter()
    L.append(f"{'id':4} {'component':64} {'class':28} tier")
    for c in COMPS:
        k, why = classify(c); t = tier(c); cls[k] += 1
        R["components"][c.id] = dict(name=c.name, cls=k, why=why, tier=t, feeds=c.feeds, gate_after=c.gate_after, owner=c.owner)
        L.append(f"{c.id:4} {c.name[:64]:64} {k:28} {t}")
    L.append("classes: " + ", ".join(f"{k} {v}" for k, v in cls.items()))
    hi = [c.id for c in COMPS if tier(c) == "HIGH"]; L.append(f"HIGH tier: {hi}; MEDIUM: {[c.id for c in COMPS if tier(c) == 'MEDIUM']}")
    L.append(f"in scope and HIGH: {[c.id for c in COMPS if tier(c) == 'HIGH' and classify(c)[0] == IN_SCOPE]}; out of scope (generative/agentic) and MEDIUM or HIGH: {[c.id for c in COMPS if tier(c) != 'LOW' and classify(c)[0] == OUT_GENAI]}")
    p = pack(COMPS, ITEMS, EMAP)
    st = Counter(s for _, _, s, _ in p.rows); L.append(""); L.append(f"validation pack: {len(p.rows)} rows (component x element, rules and arithmetic skipped, third-party only for vendor components): " + ", ".join(f"{k} {v}" for k, v in st.items()))
    by_el = {}
    for c, e, s, ids in p.rows: by_el.setdefault(e, Counter())[s] += 1
    for e, _, acc in ELEMENTS: L.append(f"   {e:28} accepted {'/'.join(acc):22} " + ", ".join(f"{k} {v}" for k, v in sorted(by_el.get(e, {}).items())))
    for c in COMPS:
        rows = [(e, s, ids) for cc, e, s, ids in p.rows if cc == c.id]
        if rows: L.append(f"   {c.id}: " + "; ".join(f"{e} {s}{' ' + ','.join(ids) if ids else ''}" for e, s, ids in rows))
    R["pack"] = [dict(c=c, e=e, s=s, ids=list(ids)) for c, e, s, ids in p.rows]; R["pack_counts"] = dict(st)
    sim_only = [c.id for c in COMPS if any(cc == c.id and e == "outcomes_analysis" and s == "OK" and all(ITEMS[i][0] == "LAB_SIM" for i in ids) for cc, e, s, ids in p.rows)]
    L.append(f"outcomes analysis OK on simulation only (synthetic data): {sim_only}")
    R["sim_only"] = sim_only
    (here / "results/ch43_inventory.json").write_text(json.dumps(R, indent=1)); (here / "results/ch43_inventory.log").write_text("\n".join(L) + "\n"); print("\n".join(L))
if __name__ == "__main__": main()
