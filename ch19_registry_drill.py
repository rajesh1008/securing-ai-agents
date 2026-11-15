#!/usr/bin/env python3
"""Chapter 19 (no model): the candidates of Table 19.1 as versions in the Chapter 18 registry, with the gate verdicts of results/ch19_gate.json (worst of the two runs).
D is a TEMPLATE (random tag per request): its digest is taken over the text with the placeholder {tag} in place, and the runtime pin compares templates.
Writes results/ch19_registry_drill.log and .json"""
import json
from pathlib import Path
here = Path(__file__).resolve().parent
from bulwark.promptrelease import *
import ch16_notes_live as N
import ch19_defences_live as C
g = json.load(open(here / "results/ch19_gate.json"))
order = {"PASS": 0, "REVIEW": 1, "BLOCK": 2}
def worst(c): return max((g[f"{c}-{n}"] for n in (1, 2) if f"{c}-{n}" in g), key=lambda x: order[x["verdict"]])
D_TEMPLATE = C.PLAIN.replace("<document>", "<{tag}>") + C.DATA_SENT
cands = [("extractor-3.0", "D", D_TEMPLATE, "plain", "delimiter template: random tag and data sentence"),
         ("extractor-3.1", "P", N.SYS_SPOT, "plain", "spotlight: datamarking and sentence"),
         ("extractor-3.2", "S1", C.SHORT, "plain", "shorter plain prompt"),
         ("extractor-3.3", "S2", C.HARD_SHORT, "hardened", "shorter hardened prompt")]
log = []
def say(x): log.append(x); print(x)
regs = {"plain": Registry(), "hardened": Registry()}
regs["plain"].add(PromptVersion("extractor-1.0", C.PLAIN, None, "Ian Walsh", "Chapter 14 extractor prompt")); regs["plain"].release("extractor-1.0", dict(verdict="PASS"), "Ian Walsh")
regs["hardened"].add(PromptVersion("extractor-2.0", N.SYS_HARD, None, "Ian Walsh", "Chapter 16 hardening, released in Chapter 18")); regs["hardened"].release("extractor-2.0", dict(verdict="PASS"), "Ian Walsh")
for k, r in regs.items(): say(f"line {k}: prod = {r.prod}, {len(r.versions[r.prod].text.split())} words, digest {r.versions[r.prod].digest[:12]}")
for vid, code, text, vs, why in cands:
    reg = regs[vs]; v = PromptVersion(vid, text, reg.prod, "Ian Walsh", why); reg.add(v); d = dict(worst(code)); d["digest"] = v.digest
    say(f"{vid} ({code}, on the {vs} line, parent {v.parent}): worst-run verdict {d['verdict']}, {len(text.split())} words, digest {v.digest[:12]}" + (f"; {d['reasons'][0]}" if d["reasons"] else ""))
    try: reg.release(vid, d, "Ian Walsh"); say(f"   released; prod = {reg.prod}")
    except PermissionError as e: say(f"   refused: {e}")
    if d["verdict"] == "REVIEW":
        d["waiver"] = "SA-2: one never-before payload on one host in one of two runs; recorded, accepted by Sophie Adler"; reg.release(vid, d, "Sophie Adler"); say(f"   waiver recorded; prod = {reg.prod}")
for k, r in regs.items(): say(f"history ({k}): " + " > ".join(f"{h['event']}:{h['id']}" for h in r.history))
say("D template: pin compares the text with the placeholder in place: " + str(runtime_check(regs["plain"], D_TEMPLATE)) + " (D is no longer production on the plain line, so False is expected)")
json.dump(dict(log=log, history={k: r.history for k, r in regs.items()}), open(here / "results/ch19_registry_drill.json", "w"), indent=1); open(here / "results/ch19_registry_drill.log", "w").write("\n".join(log) + "\n")
