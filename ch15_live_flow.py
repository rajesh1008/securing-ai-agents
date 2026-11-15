#!/usr/bin/env python3
"""Chapter 15, lab 3 (live, claude-haiku-4-5-20251001): the real model as the extractor, inside the whole flow, with four configurations of the controls. One call per distinct text (cached), same system prompt as Chapter 14.
Documents: 8 hostile classes x 6 + two framed classes x 6 + 20 clean = 80 documents, each in a fresh world; plus 10 two-step pairs (a framed note, then an invoice consistent with the account it asked for) with R on and R off.
Configurations: FULL (V G R D T on), -V, -V-G, none. 'Harm' as in ch15_ablation.py."""
import sys, json, re, random, time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
from bulwark.quill_lab import load_env
import ch14_live_extract as L
import ch14_corpus as C, ch15_ablation as X
from bulwark.reconcile import *
load_env()
CACHE = {}
def model_extract(text):
    if text in CACHE: return CACHE[text]
    d = Document("x", text); k, s, txt, j = L.ask((0, ("x", "x", d), 0)); e = L.to_ex(j) if j else Extraction(); CACHE[text] = e; return e
def build():
    recA, recB = X.world(); docs = []
    for cls in ["H1_instruction", "H2_account_swap", "H3_total_inflated", "H3b_consistent_inflate", "H4_lookalike_vendor", "H5_duplicate_paid", "H6_hidden_layer", "H8_unknown_vendor"]:
        for k in range(6): i = X.pick(recA, f"payee_{k % 6}", k // 6 + (1 if cls == "H5_duplicate_paid" else 0)); docs.append((cls, X.doc(recA, cls, i, seed=k)))
    for kind in ("ticket", "portal"):
        for k in range(6): docs.append(("F_" + kind, X.framed(recA, X.pick(recA, f"payee_{k}", 1), kind)))
    rng = random.Random(1515)
    for k in range(20): docs.append(("clean", C.clean(recA, X.pick(recA, f"payee_{k % 6}", k // 6 + 2), rng)[0]))
    return docs
CONFIGS = {"FULL": dict(V=True, G=True, R=True, D=True, T=True), "-V": dict(V=False, G=True, R=True, D=True, T=True), "-V-G": dict(V=False, G=False, R=True, D=True, T=True), "none": dict(V=False, G=False, R=False, D=False, T=False)}
if __name__ == "__main__":
    docs = build(); pairs = []
    recA, _ = X.world()
    for k in range(10):
        p = f"payee_{k % 6}"; i1, i2 = X.pick(recA, p, 0), X.pick(recA, p, 1); pairs.append((X.framed(recA, i1, "ticket" if k % 2 == 0 else "portal"), X.doc(recA, "H2_account_swap", i2, seed=k)))
    texts = sorted({t for _, d in docs for t in (d.text_layer, d.visible)} | {t for a, b in pairs for d in (a, b) for t in (d.text_layer, d.visible)})
    with ThreadPoolExecutor(6) as ex: list(ex.map(model_extract, texts))
    say = lambda s: (out.append(s), print(s)); out = []
    say(f"live calls: {len(texts)} distinct texts, {sum(1 for t in texts if CACHE[t].vendor is None)} unparsed")
    summary = {}
    for name, flags in CONFIGS.items():
        c = Counter(); per = {}
        for cls, d in docs:
            f, A, B, T = X.make(flags, model_extract); r = f.run([d])[0]; bad = X.harm(f, T)
            e = CACHE[d.text_layer]; c[(cls, "n")] += 1; c[(cls, "harm")] += bool(bad); c[(cls, "sent")] += r.sent is not None; c[(cls, "took_att")] += e.account == C.ATT; c[(cls, "route_" + r.route)] += 1
        summary[name] = {f"{k[0]}|{k[1]}": v for k, v in c.items()}
        hostile = [cl for cl in dict.fromkeys(cl for cl, _ in docs) if cl != "clean"]
        say(f"{name:5s} hostile docs {sum(c[(cl,'n')] for cl in hostile)}: harm {sum(c[(cl,'harm')] for cl in hostile)}; sent {sum(c[(cl,'sent')] for cl in hostile)}; | clean {c[('clean','n')]}: sent {c[('clean','sent')]}, harm {c[('clean','harm')]}")
        say("      by class harm/n: " + ", ".join(f"{cl} {c[(cl,'harm')]}/{c[(cl,'n')]}" for cl in hostile))
    for name, R in (("R on", True), ("R off", False)):
        h = 0; sent = 0
        for a, b in pairs:
            f, A, B, T = X.make(dict(V=True, G=True, R=R, D=True, T=True), model_extract); f.run([a], day=100); f.run([b], day=101); h += bool(X.harm(f, T)); sent += len(f.sent)
        say(f"two-step pairs ({len(pairs)}), FULL with {name}: harm {h}, payments sent {sent}")
    json.dump(dict(summary=summary, log=out, took_att={cls: sum(1 for c2, d in docs if c2 == cls and CACHE[d.text_layer].account == C.ATT) for cls in dict.fromkeys(c2 for c2, _ in docs)}), open(here / "results/ch15_live_flow.json", "w"), indent=1); open(here / "results/ch15_live_flow.log", "w").write("\n".join(out) + "\n")
