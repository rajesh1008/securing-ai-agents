#!/usr/bin/env python3
"""Chapter 29, lab 3 (no model): the three pairs the attack matrix left untried.
P1 review-queue flood (queue_wait, assumptions printed), P2 webhook tenant from the body vs the credential, P3 a scheduled job run with no principal through the real AuthorityPath."""
import sys, json, tempfile
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
from bulwark.redteam import *
from bulwark.models import ActionProposal, ActionKind, Principal, AgentIdentity
from bulwark.registry import Registry, Tool
from bulwark.authority import AuthorityPath, EvidenceChain
out = {}; L = []; P = L.append
P("P1. Review queue flood. Assumptions (mine, not measured): 40 legitimate items a day (Poisson), reviewer clears 60 a day, 30 days, seed 29.")
P(f"{'hostile/day':>11s} {'policy':>6s} {'median wait':>12s} {'p90 wait':>9s} {'legit served':>13s} {'legit never served':>19s} {'backlog':>8s}")
rows = []
for f in (0, 10, 20, 40, 80, 200):
    for pol in ("fifo", "quota"):
        r = queue_wait(40, f, 60, policy=pol); rows.append(dict(flood=f, policy=pol, **r))
        P(f"{f:>11d} {pol:>6s} {r['median_wait_days']!s:>12s} {r['p90_wait_days']!s:>9s} {r['legit_served']:>13d} {r['legit_unserved']:>19d} {r['backlog']:>8d}")
out["queue"] = rows
P("\nP2. Webhook tenant. tenant_a holds a valid signing key and sends a signed body naming tenant_b's invoice INV-1.")
books = {"tenant_a": {"INV-1": "a-row"}, "tenant_b": {"INV-1": "b-row"}}; body = {"tenant": "tenant_b", "invoice": "INV-1"}
sig = sign("tenant_a", json.dumps(body, sort_keys=True).encode())
r1, r2 = tenant_from_body(body, sig, books, "tenant_a"), tenant_from_credential(body, sig, books, "tenant_a")
P(f"tenant read from the body: {r1!r}   tenant read from the credential: {r2!r}"); out["webhook"] = dict(body=r1, credential=r2)
P("\nP3. Scheduled job without a principal through the real AuthorityPath.")
tmp = tempfile.mkdtemp(); reg = Registry(); sent = []
reg.register(Tool("send_email", "egress", True, lambda **k: sent.append(k) or "sent", gated=True, loadouts={"clerk"}))
chain = EvidenceChain(Path(tmp) / "c.jsonl")
res = []
for label, pr in (("named principal", Principal(principal_id="prin_emily", display_name="Emily Carter", business_id="biz_hcb")),
                  ("empty principal id", Principal(principal_id="", display_name="", business_id="biz_hcb")),
                  ("principal 'cron'", Principal(principal_id="cron", display_name="nightly", business_id="biz_hcb"))):
    try:
        ap = AuthorityPath(reg, chain, pr, AgentIdentity(), "clerk")
        o = ap.attempt("send_email", ActionProposal(kind=ActionKind.SEND_EMAIL, business_id="biz_hcb", principal_id=pr.principal_id or "prin_emily", recipient_email="emily@hillcountrybakehouse.example", memo="Reminder"), {"to": "emily@hillcountrybakehouse.example"})
        res.append((label, o["allow"], o["executed"], o["reason"]))
    except Exception as e: res.append((label, "error", type(e).__name__, str(e)[:80]))
rows3 = [json.loads(l) for l in open(chain.path)]
for x in res: P("  " + str(x))
P("chain rows: " + str(([(r["principal"], r["allow"]) for r in rows3], "verifies:", EvidenceChain.verify(chain.path))))
out["principal"] = dict(results=res, rows=[(r["principal"], r["allow"]) for r in rows3])
json.dump(out, open(here / "results/ch29_untested_cells.json", "w"), indent=1, default=str); open(here / "results/ch29_untested_cells.log", "w").write("\n".join(L) + "\n"); print("\n".join(L))
