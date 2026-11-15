#!/usr/bin/env python3
"""Chapter 25, lab 5 (no model; real AudienceTokens): token passthrough and the confused deputy.  Quill calls four MCP servers (ledger, mail, notes, helper) in 3,000 tasks.  In each task Quill sends one request to each server it needs (2 to 4).
ARM PASSTHROUGH: Quill holds one broad token (aud 'any', every scope, tenant hill) and sends it to every server, as many small clients do.  ARM AUDIENCE: Quill gets a token per server per task (audience = that server, only the scopes the task needs, 5-minute expiry) through the broker.
In 5 per cent of tasks the 'helper' server is compromised: on receiving a request it replays the token it was sent against ledger (void_invoice, a write) and mail (send_email).  Servers verify with AudienceTokens (PASSTHROUGH servers accept aud 'any' or their own name; AUDIENCE servers accept only their own name, and the verify path also checks scope and expiry).
Measures: replays accepted, by arm; the extra cost of minting per task; tokens in flight per task.  Seed 26.  Writes results/ch25_passthrough.json and .log"""
import json, random, sys, time
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
from bulwark.mcpguard import AudienceTokens
A = AudienceTokens(b"ch25-broker"); rng = random.Random(26); N = 3000; NOW = 1_000_000.0
SC = {"ledger": ["invoice:read"], "mail": ["mail:send"], "notes": ["note:read"], "helper": ["helper:run"]}
BROAD = A.mint("any", ["invoice:read", "invoice:void", "mail:send", "note:read", "helper:run"], "hill", 3600, NOW)
def accepts(arm, server, token, scope):
    c, why = A.verify(token, server, scope, NOW + 10)
    if c is None and arm == "PASSTHROUGH": c, why = A.verify(token, "any", scope, NOW + 10)   # the passthrough server accepts aud any
    return c is not None
res = {a: dict(replays=0, replay_void=0, replay_mail=0, compromised=0, legit_ok=0, legit_n=0, mint_us=0.0, tokens=0) for a in ("PASSTHROUGH", "AUDIENCE")}
for _ in range(N):
    need = rng.sample(["ledger", "mail", "notes"], rng.randint(1, 3)) + ["helper"]; comp = rng.random() < 0.05
    for arm in res:
        r = res[arm]; t0 = time.perf_counter(); toks = {}
        for s in need:
            toks[s] = BROAD if arm == "PASSTHROUGH" else A.mint(s, SC[s] if s != "ledger" else ["invoice:read"], "hill", 300, NOW); r["tokens"] += (arm == "AUDIENCE")
        r["mint_us"] += (time.perf_counter() - t0) * 1e6
        for s in need:
            r["legit_n"] += 1; r["legit_ok"] += accepts(arm, s, toks[s], SC[s][0])
        if comp:
            r["compromised"] += 1; tk = toks["helper"]
            v = accepts(arm, "ledger", tk, "invoice:void"); m = accepts(arm, "mail", tk, "mail:send"); r["replay_void"] += v; r["replay_mail"] += m; r["replays"] += v + m
L = []
for arm, r in res.items():
    L.append(f"{arm:11s} tasks {N}, compromised-helper tasks {r['compromised']}: replayed void_invoice accepted {r['replay_void']}, replayed send_email accepted {r['replay_mail']}; legitimate requests accepted {r['legit_ok']} of {r['legit_n']}; mint cost {r['mint_us']/N:.1f} us per task; tokens minted {r['tokens']}")
print("\n".join(L)); json.dump(res, open(here / "results/ch25_passthrough.json", "w"), indent=1); open(here / "results/ch25_passthrough.log", "w").write("\n".join(L) + "\n")
