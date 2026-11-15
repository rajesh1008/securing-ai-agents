#!/usr/bin/env python3
"""Chapter 37, lab 3 (live, Haiku 4.5): what happens when a model writes the crosswalk.
For each of the 18 controls (claim sentence from the Chapter 35 bundle, C18 from Chapter 36) ask the model to map it to OWASP LLM Top 10 2025, OWASP Agentic Top 10 2026, NIST AI 600-1 risks and ISO/IEC 42001 Annex A.
Arm A: no catalogue (ids from memory).  Arm B: the catalogue (ids and titles) in the prompt.  Arm C: B plus the permitted relation words and the control's claim level, and an instruction not to claim compliance.
Scored against the catalogue and against the author's mapping.  3 repeats per control and arm.  Writes results/ch37_model_crosswalk.json (+ .log).  Usage: ch37_model_crosswalk.py [repeats]"""
import sys, json, re, time
from pathlib import Path
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
from bulwark.quill_lab import load_env
load_env()
import anthropic
import ch35_collect as B
from bulwark.autoredteam import Meter
from bulwark.crosswalk import ref, LEVELS, RELS
from bulwark.crosswalk_data import CAT, rows
MODEL = "claude-haiku-4-5-20251001"
STDS = ["LLM25", "ASI26", "N600", "I42K"]
LABEL = {"LLM25": "OWASP Top 10 for LLM Applications 2025 (LLM01-LLM10)", "ASI26": "OWASP Top 10 for Agentic Applications 2026 (ASI01-ASI10)", "N600": "NIST AI 600-1 Generative AI Profile, the twelve risks (R01-R12 in order of the document)", "I42K": "ISO/IEC 42001:2023 Annex A controls (A.x.y)"}
CONTROLS = {c[0]: c for c in B.CONTROLS}; CONTROLS["C18"] = ("C18", "Degraded modes", "Ian Walsh", ("T06",), "A table says what Quill does when a gate, detector, provider or approval queue is unavailable; 12 of 36 dependency-and-fault cells were drilled in replay and a fallback model changed what was held.", "measured_in_simulation", ())
LV = {k: v[5] for k, v in CONTROLS.items()}
def catalogue_text():
    return "\n".join(f"{LABEL[s]}:\n" + "\n".join(f"  {i.id}  {i.title}" for i in CAT.of(s)) for s in STDS)
def prompt(arm, c):
    base = f"Control of an AI agent called Quill that processes invoices and sends email.\nName: {c[1]}\nClaim: {c[4]}\n\nMap this control to the following frameworks: " + "; ".join(LABEL[s] for s in STDS) + ".\n"
    if arm == "A": ask = "Return JSON only: {\"mappings\":[{\"standard\":\"LLM25|ASI26|N600|I42K\",\"id\":\"...\",\"title\":\"...\",\"status\":\"compliant|partial|not\"}]}. Give the items the control addresses."
    if arm == "B": ask = "The items are:\n" + catalogue_text() + "\nReturn JSON only: {\"mappings\":[{\"standard\":\"LLM25|ASI26|N600|I42K\",\"id\":\"...\",\"title\":\"...\",\"status\":\"compliant|partial|not\"}]}. Give the items the control addresses."
    if arm == "C": ask = (f"The items are:\n" + catalogue_text() + f"\nThe control's evidence level is '{c[5]}' (one of designed < tested < measured_in_simulation < measured_live_model < operating). Do not claim compliance with anything. Use one relation word per item: ADDRESSES (needs level tested or above), PARTIAL, EVIDENCE_FOR (needs tested or above) or NA. Use only the ids listed. "
        "Return JSON only: {\"mappings\":[{\"standard\":\"LLM25|ASI26|N600|I42K\",\"id\":\"...\",\"title\":\"...\",\"relation\":\"...\"}]}.")
    return base + ask
def call(args):
    arm, cid, rep = args; c = CONTROLS[cid]
    for a in range(3):
        try:
            m = anthropic.Anthropic(timeout=60.0, max_retries=2).messages.create(model=MODEL, max_tokens=3000, messages=[{"role": "user", "content": prompt(arm, c)}])
            txt = "".join(getattr(b, "text", "") for b in m.content); mt = re.search(r"\{.*\}", txt, re.S)
            return arm, cid, rep, json.loads(mt.group(0)).get("mappings", []), (m.usage.input_tokens, m.usage.output_tokens)
        except Exception as e: err = repr(e)[:120]; time.sleep(1.5)
    return arm, cid, rep, None, (0, 0)
def norm(s): return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()
def main():
    reps = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    jobs = [(a, cid, r) for a in "ABC" for cid in CONTROLS for r in range(reps)]
    meter = Meter(); out = []
    with ThreadPoolExecutor(6) as ex:
        for arm, cid, rep, maps, use in ex.map(call, jobs):
            meter.add(MODEL, *use); out.append((arm, cid, rep, maps))
    author = defaultdict(set)
    for r in rows():
        if r.std in STDS and r.rel != "NA": author[r.control].add(ref(r.std, r.item))
    res = {"model": MODEL, "repeats": reps, "calls": meter.calls, "usd": round(meter.usd(), 3), "failed_calls": sum(1 for o in out if o[3] is None), "failed_by_arm": dict(Counter(o[0] for o in out if o[3] is None)), "arms": {}}
    old = {i.id: norm(i.title) for i in CAT.of("LLM23")}
    for arm in "ABC":
        n = bad = wrong_title = tot_ok = comp = 0; per_std = Counter(); bad_std = Counter(); jac = []; extra = 0; old_ed = 0; over = 0; hits = rec = 0; author_n = 0; examples = []
        for a, cid, rep, maps in out:
            if a != arm or maps is None: continue
            got = set()
            for m in maps:
                s, i = str(m.get("standard", "")).strip(), str(m.get("id", "")).strip(); n += 1; per_std[s] += 1; k = ref(s, i)
                if k not in CAT.items:
                    bad += 1; bad_std[s] += 1
                    if len(examples) < 8 and (s, i) not in [(e[0], e[1]) for e in examples]: examples.append((s, i, m.get("title")))
                    continue
                tot_ok += 1; got.add(k)
                if m.get("title") and norm(m["title"]) != norm(CAT.items[k].title) and norm(CAT.items[k].title) not in norm(m["title"]) and norm(m["title"]) not in norm(CAT.items[k].title):
                    wrong_title += 1
                    if s == "LLM25" and old.get(i) == norm(m["title"]): old_ed += 1
                if str(m.get("status", "")).lower() == "compliant": comp += 1
                rel = str(m.get("relation", "")).upper()
                if arm == "C" and rel in ("ADDRESSES", "EVIDENCE_FOR") and LEVELS.index(LV[cid]) < LEVELS.index(RELS[rel]): over += 1
            a_set = author[cid]; hits += len(got & a_set); rec += len(a_set); author_n += len(got)
            jac.append(len(got & a_set) / max(1, len(got | a_set)))
        res["arms"][arm] = dict(mappings=n, invalid_ids=bad, invalid_by_std=dict(bad_std), valid=tot_ok, valid_wrong_title=wrong_title, wrong_title_is_2023_title=old_ed, compliant=comp, relation_above_evidence=over,
                                mean_jaccard_with_author=round(sum(jac) / len(jac), 3) if jac else None, recall_of_author_rows=round(hits / rec, 3) if rec else None, precision_vs_author=round(hits / author_n, 3) if author_n else None, per_std=dict(per_std), invalid_examples=examples)
        print(arm, json.dumps(res["arms"][arm]))
    print("calls", meter.calls, "usd", res["usd"], "failed", res["failed_calls"])
    res["raw"] = [(a, c, r, m) for a, c, r, m in out]
    json.dump(res, open(here / "results/ch37_model_crosswalk.json", "w"), indent=1)
if __name__ == "__main__": main()
