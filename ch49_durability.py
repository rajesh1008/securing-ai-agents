#!/usr/bin/env python3
"""Chapter 49, lab (no model): what in this book is durable and what is perishable, measured on the repository itself.
A  static scan of the 59 modules in bulwark/: which import a model client or the network, and which contain a model id or a version literal.
B  the 23 controls of the Chapter 47 bundle, each tagged by the author with what it depends on (code, model, standard, people): a judgement, printed with the tags so a reader can disagree.
C  the evidence: how many result files name a model id, which ids, and how many controls rest on any live-model item.
D  the model swap in Chapter 23's results (three models): cells that moved, and the gate's numbers on the same runs.
E  the prediction register (bulwark/predictions.py): ten dated, falsifiable predictions; validated; written to results/ch49_predictions.json.
Writes results/ch49_durability.json and .log."""
import sys, json, re, ast
from pathlib import Path
from collections import Counter
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
import ch47_bundle as B
from bulwark.predictions import Prediction, validate, due, score
L = []; res = {}
def say(s): L.append(s); print(s)
# A
NET = {"anthropic", "urllib", "requests", "httpx", "socket", "http", "openai", "aiohttp"}
mods = sorted(p for p in (here / "bulwark").glob("*.py") if p.name != "__init__.py")
net, modelid, verlit = [], [], []
for p in mods:
    src = p.read_text(); tree = ast.parse(src); names = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import): names |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module: names.add(n.module.split(".")[0])
    if names & NET: net.append(p.stem)
    if re.search(r"claude-[a-z0-9.-]+", src): modelid.append(p.stem)
    if re.search(r"(?i)\bmcp\b.*\b20\d\d-\d\d-\d\d\b|protocol[_ ]version", src): verlit.append(p.stem)
say(f"A {len(mods)} modules in bulwark/: import a model client or the network {len(net)} {net}; contain a model id {len(modelid)} {modelid}; contain a protocol-version literal {len(verlit)} {verlit}")
res["A"] = dict(modules=len(mods), net=net, model_id=modelid, version_literal=verlit)
labs = sorted(here.glob("ch*.py")); live = [p.stem for p in labs if re.search(r"claude-|api\.anthropic|ch30_loop", p.read_text())]
say(f"   lab scripts at the repository root {len(labs)}; those that name a model id, the API host or the shared loop module (a text heuristic) {len(live)}; no-model labs {len(labs) - len(live)}")
res["A"].update(labs=len(labs), live_labs=len(live))
# B
TAGS = {"C01": "code people", "C02": "code", "C03": "code", "C04": "code", "C05": "code", "C06": "code", "C07": "code", "C08": "code standard", "C09": "model", "C10": "code standard", "C11": "code",
        "C12": "code", "C13": "people standard", "C14": "code", "C15": "code standard", "C16": "code people", "C17": "code", "C18": "code model", "C19": "code standard", "C20": "code standard",
        "C21": "people", "C22": "code", "C23": "people"}
ctl = {c[0]: c for c in B.C.CONTROLS + B.NEW_CONTROLS}; assert set(ctl) == set(TAGS), set(ctl) ^ set(TAGS)
cnt = Counter(t for v in TAGS.values() for t in v.split()); nomodel = [k for k, v in TAGS.items() if "model" not in v.split()]; only_code = [k for k, v in TAGS.items() if v == "code"]
say(f"B {len(TAGS)} controls tagged by the author: depends on code {cnt['code']}, a standard or protocol {cnt['standard']}, people {cnt['people']}, model behaviour {cnt['model']}; with no dependence on model behaviour {len(nomodel)} of {len(TAGS)}; code alone {len(only_code)}")
say("   model-dependent: " + ", ".join(f"{k} {ctl[k][1]}" for k, v in TAGS.items() if "model" in v.split()) + "; standard-dependent: " + ", ".join(k for k, v in TAGS.items() if "standard" in v.split()))
res["B"] = dict(tags=TAGS, counts=dict(cnt), no_model=len(nomodel), code_alone=len(only_code))
# C
items = {i[0]: i for i in B.C.ITEMS + B.NEW_ITEMS}; livei = {k for k, i in items.items() if i[2] == "LAB_LIVE"}
withlive = [k for k, c in ctl.items() if set(c[6]) & livei]; onlylive = [k for k, c in ctl.items() if c[6] and set(c[6]) <= livei]
files = [p for p in (here / "results").iterdir() if p.is_file()]; ids = Counter(); nfile = 0
for p in files:
    try: t = p.read_text(errors="ignore")
    except Exception: continue
    f = set(re.findall(r"claude-[a-z0-9.]+(?:-[a-z0-9.]+)*", t))
    if f: nfile += 1
    ids.update(f)
say(f"C evidence: {len(files)} result files, {nfile} name a model id; ids by mentions: " + ", ".join(f"{k} {v}" for k, v in ids.most_common(5)) + f"; distinct ids {len(ids)}")
say(f"   items of kind LAB_LIVE {len(livei)} of {len(items)}; controls with any live item {len(withlive)} ({', '.join(withlive)}); controls resting only on live items {len(onlylive)} ({', '.join(onlylive)})")
res["C"] = dict(files=len(files), files_with_model=nfile, ids=dict(ids.most_common(8)), distinct=len(ids), live_items=len(livei), items=len(items), controls_with_live=withlive, controls_only_live=onlylive)
# D
d = (here / "results/ch23_summary.log").read_text().splitlines()
say("D model swap, from results/ch23_summary.log (Chapter 23, three models, 160 PLAIN-arm runs each):")
for ln in d:
    if ln.strip().startswith(("sonnet46: IMPROPER", "haiku55: IMPROPER", "split ", "audit ", "backdate", "personal")): say("   " + ln.strip()[:170])
res["D"] = [ln.strip() for ln in d if ln.strip().startswith(("sonnet46: IMPROPER", "haiku55: IMPROPER"))]
# E
P = [
 Prediction("F01", "Per-task, per-call credentials will be the default in the quickstart of at least one of the three most-starred open-source agent frameworks.", "Quickstart code of the three most-starred open-source agent frameworks on the review date", "0 of the three issue a per-task or per-call credential in the default quickstart", "2027-11-15", "repository READMEs and quickstarts read on the review date", 55),
 Prediction("F02", "No defence that works inside the model will be shown, by authors who did not build it, to hold at zero attack success against an adaptive attacker on three or more models.", "Published evaluations of model-level injection defences by independent authors", "one such independent paper reports 0 percent adaptive attack success on three or more models", "2027-11-15", "arXiv search for independent adaptive-attack evaluations, read on the review date", 85),
 Prediction("F03", "At least one model-level injection defence published after 2026-11-15 will be reported broken by an adaptive attack, at above 50 percent success, within six months of its publication.", "Papers reporting adaptive attacks on newly published defences", "no defence published in the window is reported above 50 percent adaptive success within six months", "2027-11-15", "arXiv search, read on the review date", 80),
 Prediction("F04", "The Model Context Protocol specification will change its authorization requirements at least once between 2026-11-15 and the review date.", "The authorization sections of the specification's changelog", "the changelog shows no authorization-related change in the window", "2027-11-15", "the specification repository's changelog read on the review date", 75),
 Prediction("F05", "claude-haiku-4-5-20251001, the model behind most live labs in this book, will be listed as deprecated or retired by its vendor.", "The vendor's published model deprecation page", "the model is not listed as deprecated or retired on the review date", "2027-11-15", "vendor deprecation page read on the review date", 70),
 Prediction("F06", "A public incident report will attribute a money loss of at least 100,000 US dollars to an LLM agent acting on injected instructions.", "Public incident reports, court filings and regulator statements", "no such public report exists on the review date", "2027-11-15", "web search and incident databases on the review date", 50),
 Prediction("F07", "At least half of the live-model labs in this book, re-run on the then-current default models, will fall outside the intervals printed in the chapters.", "Re-runs of ten live labs chosen at random from the repository", "fewer than 5 of 10 re-run labs fall outside their printed intervals", "2027-11-15", "re-run by the author or a contributor; logs committed to the repository", 70),
 Prediction("F08", "The 522 no-model tests of the repository will need at least 10 edits because of dependency upgrades alone.", "Commits between 2026-11-15 and the review date that change test files and mention a dependency", "fewer than 10 test edits in the window are caused by a dependency upgrade", "2027-05-15", "git log of the repository", 40, "6 months"),
 Prediction("F09", "At least one agent vendor will publish a signed control bundle that includes a claim of operating evidence over a stated period.", "Vendor trust pages and security documentation", "no vendor publishes such a bundle by the review date", "2028-11-15", "vendor documentation read on the review date", 35, "24 months"),
 Prediction("F10", "A publicly documented case will show an approval screen that displayed a summary produced by the model being the point of failure in a loss.", "Public incident reports naming the approval step", "no public report names an approval step that relied on a model summary", "2027-11-15", "web search on the review date", 45),
]
bad = [x for p in P for x in validate(p)]
say(f"E prediction register: {len(P)} predictions, {sum(1 for p in P if p.horizon == '12 months')} at twelve months; validation problems {len(bad)} {bad[:3]}; due today (2026-11-15): {due(P, '2026-11-15')}; confidence mean {sum(p.confidence for p in P) / len(P):.0f}; scored so far {score(P)}")
res["E"] = dict(n=len(P), problems=bad)
json.dump([p.__dict__ for p in P], open(here / "results/ch49_predictions.json", "w"), indent=1)
json.dump(dict(res, log=L), open(here / "results/ch49_durability.json", "w"), indent=1, default=list); open(here / "results/ch49_durability.log", "w").write("\n".join(L) + "\n")
