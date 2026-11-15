#!/usr/bin/env python3
"""Chapter 37, lab 3 report (no model): re-scores results/ch37_model_crosswalk.json.  Per arm: mappings per call; for LLM25 the share of titles equal to the 2025 title and to the 2023-24 title for the same id; ASI titles; NIST titles; valid ISO ids;
status words; for arm C the relation words against the author's rows.  Writes results/ch37_model_crosswalk_breakdown.json and prints the log."""
import json, re, sys
from pathlib import Path
from collections import Counter
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
from bulwark.crosswalk import ref
from bulwark.crosswalk_data import CAT, rows
d = json.load(open(here / "results/ch37_model_crosswalk.json")); norm = lambda s: re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()
old = {i.id: norm(i.title) for i in CAT.of("LLM23")}; auth = {(r.control, ref(r.std, r.item)): r.rel for r in rows()}; out = {}
for arm in "ABC":
    ms = [(c, m) for a, c, r, mm in d["raw"] if a == arm and mm for m in mm]; calls = len({(c, r) for a, c, r, mm in d["raw"] if a == arm and mm})
    T = lambda s, i: CAT.items[ref(s, i)].title
    ll = [m for c, m in ms if m.get("standard") == "LLM25" and ref("LLM25", m.get("id")) in CAT.items]
    asi = [m for c, m in ms if m.get("standard") == "ASI26" and ref("ASI26", m.get("id")) in CAT.items]
    n6 = [m for c, m in ms if m.get("standard") == "N600" and ref("N600", m.get("id")) in CAT.items]
    iso = [m for c, m in ms if m.get("standard") in ("I42K", "ISO42001")]
    out[arm] = dict(calls_ok=calls, mappings=len(ms), per_call=round(len(ms) / calls, 1),
        llm25=len(ll), llm25_title_2025=sum(norm(m.get("title")) == norm(T("LLM25", m["id"])) for m in ll), llm25_title_2023=sum(norm(m.get("title")) == old.get(m["id"]) and norm(m.get("title")) != norm(T("LLM25", m["id"])) for m in ll),
        asi=len(asi), asi_title_ok=sum(norm(m.get("title")) in norm(T("ASI26", m["id"])) or norm(T("ASI26", m["id"])) in norm(m.get("title")) for m in asi),
        n600=len(n6), n600_title_ok=sum(norm(m.get("title")) == norm(T("N600", m["id"])) for m in n6),
        iso=len(iso), iso_valid=sum(ref("I42K", str(m.get("id"))) in CAT.items for m in iso),
        status=dict(Counter(str(m.get("status")) for c, m in ms)), relation=dict(Counter(str(m.get("relation")).upper() for c, m in ms)))
    if arm == "C":
        cmp = Counter(); [cmp.update([f'{str(m.get("relation")).upper()} | author: {auth.get((c, ref(m.get("standard"), m.get("id"))), "no row")}']) for c, m in ms]
        out[arm]["against_author"] = dict(cmp)
        for rel in ("ADDRESSES", "EVIDENCE_FOR", "PARTIAL"):
            ar = [k for k, v in auth.items() if v == rel and k[1].split(":")[0] in ("LLM25", "ASI26", "N600", "I42K")]; got = sum(1 for k in ar if any((c, ref(m.get("standard"), m.get("id"))) == k for c, m in ms))
            out[arm][f"author_{rel}_rows_found"] = f"{got} of {len(ar)}"
    asi_ex = Counter((m["id"], m["title"]) for m in [m for c, m in ms if m.get("standard") == "ASI26"]).most_common(5)
    out[arm]["asi_examples"] = asi_ex; print(arm, json.dumps(out[arm]))
json.dump(out, open(here / "results/ch37_model_crosswalk_breakdown.json", "w"), indent=1)
