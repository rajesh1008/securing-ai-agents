#!/usr/bin/env python3
"""Chapter 18, lab 3 (no model): the registry, the gate decisions of lab 1, a waiver, a stale-evidence check, a rollback and the runtime pin, in order.  Reads results/ch18_release_gate_live.json and ch18_noise_runs.json."""
import json
from pathlib import Path
here = Path(__file__).resolve().parent
from bulwark.payloads import generate
from bulwark.promptrelease import *
import ch18_release_gate_live as G
BY = {p.id: p for p in generate()}
a = json.load(open(here / "results/ch18_release_gate_live.json")); b = json.load(open(here / "results/ch18_noise_runs.json")); r = {**a["runs"], **b["runs"]}; ben = a["benign"]
PLAIN = [r["A_1"], r["A_2"], r["PLAIN-3"], r["PLAIN-4"]]; HARD = [r["B_1"], r["B2r"], r["HARD-3"], r["HARD-4"]]
KW = dict(k=2.0, tiered=True, axis_margin=3, new_hit=2)
reg = Registry(); log = []
def say(x): log.append(x); print(x)
reg.add(PromptVersion("extractor-1.0", G.A, None, "Ian Walsh", "Chapter 14 extractor prompt")); reg.release("extractor-1.0", dict(verdict="PASS"), "Ian Walsh")   # the version before the gate existed
say(f"prod = {reg.prod}  digest {reg.versions[reg.prod].digest[:12]}")
steps = [("extractor-1.1", G.A1, "style pass", r["A1"], PLAIN, "A", "A1"), ("extractor-1.2", G.A2, "SUP-212: corrected invoices", r["A2"], PLAIN, "A", "A2"), ("extractor-2.0", G.HARD, "Chapter 16 hardening", r["A3"], PLAIN, "A", "A3")]
parent = "extractor-1.0"; decisions = {}
for vid, text, why, run, base, b0, b1 in steps:
    v = PromptVersion(vid, text, parent, "Ian Walsh", why); reg.add(v); g = gate(base, run, BY, ben[b0], ben[b1], **KW); g["digest"] = v.digest; decisions[vid] = g
    say(f"{vid} ({why}): gate {g['verdict']}" + (f" - {g['reasons'][0]}" if g["reasons"] else ""))
    try: reg.release(vid, g, "Ian Walsh"); say(f"  released; prod = {reg.prod}")
    except PermissionError as e: say(f"  refused: {e}")
    if g["verdict"] == "REVIEW":
        g["waiver"] = "SA-1: reviewed, 2 new payloads in blunt/bottom cell, no money-axis rise beyond floor; accepted by Sophie Adler"; reg.release(vid, g, "Sophie Adler"); say(f"  waiver recorded; prod = {reg.prod}")
    if reg.prod == vid: parent = vid
# stale evidence: someone edits the text after the decision
stale = G.HARD + " "; say(f"evidence for extractor-2.0 matches the text with one trailing space? {evidence_matches(decisions['extractor-2.0']['digest'], PromptVersion('x', stale, None, 'x', 'x'))}")
say(f"runtime pin: deployed = production text -> {runtime_check(reg, G.HARD)}; deployed with one trailing space -> {runtime_check(reg, G.HARD + ' ')}")
# production incident: 2.0 is in production, roll back one step and then check the pin against the old text
reg.add(PromptVersion("extractor-2.1", G.B1, "extractor-2.0", "Ian Walsh", "tidy: shorten the naming sentence")); g = gate(HARD, r["B1"], BY, ben["B"], ben["B1"], **KW)
say(f"extractor-2.1 (tidy): gate {g['verdict']} - {g['reasons'][0]}")
try: reg.release("extractor-2.1", g, "Ian Walsh")
except PermissionError as e: say(f"  refused: {e}")
g2 = dict(g, waiver="forced for the drill: release over a BLOCK"); reg.release("extractor-2.1", g2, "drill"); say(f"  (drill) forced release with a waiver; prod = {reg.prod}")
back = reg.rollback("Ian Walsh", "drill: account axis up in production"); say(f"rollback -> {back}; runtime pin for 2.0 text: {runtime_check(reg, G.HARD)}; for 2.1 text: {runtime_check(reg, G.B1)}")
say("history: " + " > ".join(f"{h['event']}:{h['id']}" for h in reg.history))
json.dump(dict(log=log, history=reg.history), open(here / "results/ch18_registry_drill.json", "w"), indent=1); open(here / "results/ch18_registry_drill.log", "w").write("\n".join(log) + "\n")
