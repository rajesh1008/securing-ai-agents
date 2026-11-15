#!/usr/bin/env python3
"""Chapter 24, lab 2 (live): Quill behind the gateway.  The provider key is read from the environment by the forwarder inside the gateway process and by nothing else; the agent side holds a gateway token and an alias.
Scenario: (A) 12 allowed requests to quill-actor (real calls); (B) refusals: direct model id, unknown alias, purpose not approved, alias not in the token, retired alias (clock moved past end-of-life); (C) quill-next (claude-haiku-5-5) with the suite verdict from the Chapter 24 alias lab = BLOCK: refused, then 3 real calls after a named waiver;
(D) old-reader (claude-sonnet-4-5-20250929, SDK end-of-life 30 Nov 2026): deprecated with 19 days to go, warns, and the upstream answers 404; (E) a floating alias (claude-haiku-4-5) resolves at the provider to the dated snapshot: SERVED_MODEL_MISMATCH recorded; (F) token budget 300 tokens: calls until refused; (G) forged, expired, and revoked-key tokens.
Writes results/ch24_gateway_live.json (rows) and .log.  The key is never printed or stored."""
import sys, json, time, statistics, warnings
from datetime import date
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
from bulwark.quill_lab import load_env
load_env()
import anthropic
from bulwark.gateway import *
client = anthropic.Anthropic(timeout=60.0, max_retries=1)
def forward(key, model_id, body):
    t0 = time.perf_counter()
    try:
        with warnings.catch_warnings(): warnings.simplefilter("ignore"); r = client.messages.create(model=model_id, max_tokens=body.get("max_tokens", 40), messages=body["messages"])
    except Exception as e: return dict(error=getattr(e, "__class__").__name__.upper().replace("ERROR", "") + "_" + str(getattr(e, "status_code", "")))
    return dict(served=r.model, usage_tokens=r.usage.input_tokens + r.usage.output_tokens, latency_ms=(time.perf_counter() - t0) * 1000, text=r.content[0].text if r.content else "")
REG = ModelRegistry([ModelEntry("quill-actor", "claude-haiku-4-5-20251001", {"act", "read"}), ModelEntry("quill-review", "claude-sonnet-4-6", {"review"}),
                     ModelEntry("quill-next", "claude-haiku-5-5", {"act"}, suite="BLOCK"), ModelEntry("old-reader", "claude-sonnet-4-5-20250929", {"read"}, status="deprecated", eol=date(2026, 11, 30)),
                     ModelEntry("quill-floating", "claude-haiku-4-5", {"act"})])
KR = KeyRing(); KR.add("g1", b"gateway-signing-key-1", 0, 10**10); G = Gateway(REG, KR, "held-by-the-gateway", forward)
TODAY = date(2026, 11, 11); now = time.time()
tok = lambda aliases, budget=10**6, exp=3600: KR.issue(dict(agent="quill", tid=f"t{len(G.log)}", aliases=aliases, budget_tokens=budget, exp=now + exp), now)
ALL = ["quill-actor", "quill-review", "quill-next", "old-reader", "quill-floating"]; T = tok(ALL)
body = lambda q: dict(max_tokens=30, messages=[{"role": "user", "content": q}])
L = []; C = lambda r: (r["decision"], r["rule"])
for i in range(12): G.handle(T, "quill-actor", "act", body(f"Reply with the single word OK. ({i})"), TODAY)
L.append("A allowed: %d of 12" % sum(1 for r in G.log if r["decision"] == "allow"))
tests = [("direct model id", "claude-opus-4-8", "act", T, TODAY), ("unknown alias", "gpt-unlisted", "act", T, TODAY), ("purpose", "quill-review", "act", T, TODAY),
         ("alias not in token", "quill-review", "review", tok(["quill-actor"]), TODAY), ("retired (clock 2026-12-01)", "old-reader", "read", T, date(2026, 12, 1))]
for name, al, pu, tk, td in tests: r = G.handle(tk, al, pu, body("hi"), td); L.append(f"B {name}: {r['decision']} {r['rule']}")
r = G.handle(T, "quill-next", "act", body("hi"), TODAY); L.append(f"C quill-next without waiver: {r['decision']} {r['rule']}")
REG.by_alias["quill-next"].waiver = "A. Constantinescu 2026-11-11: euphemism-split cells accepted; gate holds (Ch23 lab 4)"
ok = [G.handle(T, "quill-next", "act", body("Reply with the single word OK."), TODAY)["decision"] for _ in range(3)]; L.append(f"C quill-next with waiver: {ok}")
r = G.handle(T, "old-reader", "read", body("hi"), TODAY); L.append(f"D old-reader (deprecated, 19 days to end-of-life): {r['decision']} {r['rule']} warns {r['row'].get('warns')}")
fl = [G.handle(T, "quill-floating", "act", body("Reply with the single word OK."), TODAY)["row"] for _ in range(3)]; L.append(f"E floating alias: served {fl[0].get('served')} alerts {[x.get('alert') for x in fl]}")
tb = tok(["quill-actor"], budget=300); res = [G.handle(tb, "quill-actor", "act", body("Write two sentences about paper."), TODAY) for _ in range(10)]
L.append("F budget 300 tokens: decisions " + "".join("A" if r["decision"] == "allow" else "D" for r in res) + f"; tokens spent {G.spent[res[0]['row']['tid']]}; refused with {res[-1]['rule']}")
good = tok(["quill-actor"]); forged = good[:-1] + ("0" if good[-1] != "0" else "1"); exp = tok(["quill-actor"], exp=-5)
KR.add("g2", b"gateway-signing-key-2", 0, 10**10); t2 = KR.issue(dict(agent="quill", tid="tg2", aliases=["quill-actor"], budget_tokens=10**6, exp=now + 100), now); KR.revoke("g2")
L.append("G tokens: forged %s; expired %s; revoked key %s" % (G.handle(forged, "quill-actor", "act", body("hi"), TODAY)["rule"], G.handle(exp, "quill-actor", "act", body("hi"), TODAY)["rule"], G.handle(t2, "quill-actor", "act", body("hi"), TODAY)["rule"]))
allowed = [r for r in G.log if r["decision"] == "allow"]; t0 = time.perf_counter(); n = 2000
for _ in range(n): REG.resolve("quill-actor", "act", TODAY); KR.verify(T, now)
dec_us = (time.perf_counter() - t0) / n * 1e6
L.append(f"rows {len(G.log)}: allow {sum(1 for r in G.log if r['decision']=='allow')}, deny {sum(1 for r in G.log if r['decision']=='deny')}, error {sum(1 for r in G.log if r['decision']=='error')}; every allowed row has a digest and served model: {all(r.get('digest') and r.get('served') for r in allowed)}")
L.append(f"decision cost (resolve + verify) {dec_us:.1f} microseconds; upstream latency median {statistics.median(r['latency_ms'] for r in allowed):.0f} ms over {len(allowed)} real calls; tokens {sum(r['used'] for r in allowed)}")
print("\n".join(L)); json.dump(G.log, open(here / "results/ch24_gateway_live.json", "w"), indent=1, default=str); open(here / "results/ch24_gateway_live.log", "w").write("\n".join(L) + "\n")
