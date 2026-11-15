#!/usr/bin/env python3
"""Chapter 46, lab 1 (no model): the work-sample exercise, three programmes, six candidate archetypes, plus a vocabulary scorer on archetype prose.  Writes results/ch46_exercise.json and .log."""
import sys, json
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
from bulwark.interview import *
PROSE = {   # what each archetype would say in an interview, written by the author; same length class, all fluent
 "reciter (model review everywhere)": "I'd take a defense in depth approach: guardrails on the input, a second model acting as a reviewer on every sensitive action, strong monitoring and audit logging, and regular red team exercises against prompt injection, all following least privilege.",
 "cap-fan (limits and rates)": "I would apply least privilege and put a rate limit and a spending cap on every tool, add monitoring and an audit trail, run a threat model workshop, and keep a human in the loop for anything unusual.",
 "approver (a person looks)": "Human in the loop is the safest design: nothing sensitive happens without a person approving it, with validation of the inputs, audit logging, observability, and a sandbox for anything that runs code.",
 "pattern-matcher (lists and records)": "I'd use allow-lists and lookups wherever the model touches a sensitive tool, validation and sanitization of tool input, and logging. I'd check the lists are kept current.",
 "careful": "For each dangerous tool I would ask what the request is checked against and who can write that record, move the check into code over a record the outsider cannot write, and gate what the agent can save for later."}
def main():
    L = []; out = {"exercises": [], "archetypes": {}, "vocab": {}}
    for ex in exercises():
        L.append(f"{ex.name}: dangerous tools {ex.dangerous_tools()}; paths unbounded before any fix {score(ex, {})['before']}"); out["exercises"].append(dict(name=ex.name, before=score(ex, {})["before"]))
    L.append(""); L.append(f"{'archetype':38} " + " | ".join(f"{ex.name.split(' (')[0][:14]:>14}" for ex in exercises()) + " | passes  vocab")
    for a in ARCHETYPES:
        row = []; passes = 0; res = []
        for ex in exercises():
            s = score(ex, archetype_answer(ex, a)); row.append(f"{s['residual']:>3} {str(s['by_class'])[:9]:>10}"); passes += s["pass"]; res.append(s["residual"])
        v = vocab_score(PROSE[a]); out["archetypes"][a] = dict(residual=res, passes=passes, vocab=v)
        L.append(f"{a:38} " + " | ".join(f"{r:>14}" for r in res) + f" | {passes}/3     {v}")
    L.append(""); L.append("residual = unbounded (source, tool) paths left after applying the picks, re-checked by bulwark.casestudy.findings")
    ranked = sorted(out["archetypes"].items(), key=lambda kv: -kv[1]["vocab"]); L.append("ranked by vocabulary score: " + "; ".join(f"{k.split(' (')[0]} {v['vocab']}" for k, v in ranked))
    (here / "results/ch46_exercise.json").write_text(json.dumps(out, indent=1)); (here / "results/ch46_exercise.log").write_text("\n".join(L) + "\n"); print("\n".join(L))
if __name__ == "__main__": main()
