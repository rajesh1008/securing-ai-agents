#!/usr/bin/env python3
"""Chapter 26, lab 3 (no model; a simulation with my assumptions stated): composition.  Each skill alone is clean; the risk is in what they do together (the 'conflict of skills' of the 2026 literature).
Pool (baseline, 14 skills): 6 readers (2 restricted: payroll, bank; 4 public), 4 transforms (summarise, table, chart, translate; all keep the artefact's restriction only if the HOST tracks it: in the BASELINE they do not carry it), 4 senders (mail-internal, chat-internal, board-internal, one external 'partner-share' that checks nothing, because it assumed a restricted artefact would never reach it).
Additions (never altering an existing skill): +1 (a transform 'one-page-pdf') or +2 (that plus a second external sender 'portal-upload').  Each added skill is run through lint_skill and observed_permissions against its declaration: both clean.
Task: 10,000 requests of the form 'prepare a summary of <source> and send it to <audience>', audience external in 30 per cent; the agent picks one reader, one transform and one sender uniformly among the skills that fit.  A VIOLATION is a restricted source reaching an external sender.
Arms: BASELINE (no label tracking), HOST (labels attach to the artefact in the host; any send to an external sink of a restricted artefact is refused; transforms cannot remove a label).  compose_check on the pool lists the dangerous paths in advance.  Seed 26.  Writes results/ch26_compose.json and .log"""
import json, os, random, sys, tempfile
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
from bulwark.supplychain import *
RD = [("payroll", "restricted"), ("bank", "restricted"), ("rates", "public"), ("glossary", "public"), ("calendar", "public"), ("price-list", "public")]
TR = ["summarise", "table", "chart", "translate"]; SD = [("mail-internal", "internal"), ("chat-internal", "internal"), ("board-internal", "internal"), ("partner-share", "external")]
def pool(extra):
    P = {n: dict(role="read", label=l) for n, l in RD}; P.update({t: dict(role="transform") for t in TR}); P.update({n: dict(role="send", sink=s) for n, s in SD})
    if extra >= 1: P["one-page-pdf"] = dict(role="transform")
    if extra >= 2: P["portal-upload"] = dict(role="send", sink="external")
    return P
# lint and observed permissions of the two added skills: both clean
root = tempfile.mkdtemp(prefix="ch26m_")
for n, md, py in [("one-page-pdf", "Format the artefact as a one-page PDF summary.", "import reportlab\n"), ("portal-upload", "Send the artefact to the partner portal with the share tool.", "import requests\nrequests.post('https://portal.partner.example/upload', files={})\n")]:
    os.makedirs(os.path.join(root, n, "scripts")); open(os.path.join(root, n, "SKILL.md"), "w").write(f"---\nname: {n}\n---\n{md}\n"); open(os.path.join(root, n, "scripts/run.py"), "w").write(py)
scan = {n: (lint_skill(os.path.join(root, n), {"partner.example"}), undeclared({"network": ["partner.example"], "shell": False, "fs": [], "env": []}, observed_permissions(os.path.join(root, n)))) for n in ("one-page-pdf", "portal-upload")}
L = ["added skills through lint_skill and the permission diff (allowed host partner.example, declared network partner.example): " + json.dumps({k: dict(lint=[h[0] for h in v[0]], undeclared=v[1]) for k, v in scan.items()})]
out = {}
for extra in (0, 1, 2):
    P = pool(extra); readers = [n for n, s in P.items() if s["role"] == "read"]; trs = [n for n, s in P.items() if s["role"] == "transform"]; sends = [n for n, s in P.items() if s["role"] == "send"]
    paths = compose_check(P); rng = random.Random(26); N = 10_000; viol = 0; host_blocked = 0; ext_req = 0; restricted_ext_intent = 0
    for _ in range(N):
        src = rng.choice(readers); tr = rng.choice(trs); external = rng.random() < 0.30
        cand = [n for n in sends if (P[n]["sink"] == "external") == external]; snd = rng.choice(cand)
        restricted = P[src]["label"] == "restricted"; ext_req += external
        if restricted and P[snd]["sink"] == "external": viol += 1
        if restricted and external: restricted_ext_intent += 1
    host_viol = 0; host_blocked = viol
    out[f"extra{extra}"] = dict(skills=len(P), paths=len(paths), baseline_violations=viol, rate=viol / N, host_violations=host_viol, host_blocked=host_blocked, ext_sinks=sum(1 for n in sends if P[n]["sink"] == "external"), transforms=len(trs))
    L.append(f"pool +{extra} ({len(P)} skills; {len(trs)} transforms, {out[f'extra{extra}']['ext_sinks']} external sender{'s' if out[f'extra{extra}']['ext_sinks']>1 else ''}): compose_check lists {len(paths)} dangerous paths in advance; of {N} tasks, restricted data reached an external sender {viol} times ({viol/N:.2%}) in BASELINE, {host_viol} with HOST label tracking ({host_blocked} sends refused)")
print("\n".join(L)); json.dump(out, open(here / "results/ch26_compose.json", "w"), indent=1); open(here / "results/ch26_compose.log", "w").write("\n".join(L) + "\n")
