#!/usr/bin/env python3
"""Chapter 4 lab 1 (fail-safe defaults): replay the real proposals recorded in ch03_surface_ablation.json through the Mediator while the
policy service is made to fail on a fraction of calls. Fail-open vs fail-closed. No model calls: the proposals are the live ones from Chapter 3."""
import json, random, sys
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
from bulwark.models import ActionProposal, ActionKind, Principal, AgentIdentity
from bulwark.policy_v02 import BulwarkGateV02
from bulwark.principles import Mediator, Tool
rows = json.load(open(here / "results/ch03_surface_ablation.json"))["rows"]
rows = [r for r in rows if r["arm"] in ("plain", "spotlight", "hardened") and r["kind"] != "NON_SCHEMA"]
pr = Principal(principal_id="prin_emily", display_name="Emily Carter", business_id="biz_hcb"); ag = AgentIdentity()
def to_prop(r):
    return ActionProposal(kind=ActionKind(r["kind"]), business_id="biz_hcb", principal_id="prin_emily", recipient_email=r.get("recipient"), payee_id=r.get("payee"), amount_cents=r.get("amount"))
class FlakyGate:
    def __init__(self, rate, seed):
        self.inner, self.rate, self.rng = BulwarkGateV02(), rate, random.Random(seed)
    def check(self, p, pr, ag):
        if self.rng.random() < self.rate: raise TimeoutError("policy service unavailable")
        return self.inner.check(p, pr, ag)
KINDS = (ActionKind.SEND_EMAIL, ActionKind.SEND_INVOICE, ActionKind.INITIATE_PAYMENT, ActionKind.DRAFT_INVOICE, ActionKind.READ_DOCUMENT, ActionKind.QUERY_BOOKS)
out = []
print(f"{'fault rate':>10} {'mode':>7} {'harmful run':>12} {'of':>4} {'benign run':>11} {'of':>4}")
for rate in (0.0, 0.1, 0.5, 1.0):
    for mode in ("closed", "open"):
        ran = []; seeds = range(20)  # 20 independent fault schedules, results summed
        h_run = b_run = h_tot = b_tot = 0
        for s in seeds:
            tools = {k: Tool(k.value, lambda p: "ok") for k in KINDS}
            m = Mediator(FlakyGate(rate, s), tools, mode)
            for r in rows:
                res = m.execute(to_prop(r), pr, ag)
                if r["harm"]: h_tot += 1; h_run += res.executed
                else: b_tot += 1; b_run += res.executed
        out.append(dict(fault_rate=rate, mode=mode, harmful_executed=h_run, harmful_total=h_tot, benign_executed=b_run, benign_total=b_tot))
        print(f"{rate:>10} {mode:>7} {h_run:>12} {h_tot:>4} {b_run:>11} {b_tot:>4}")
(here / "results/ch04_failsafe.json").write_text(json.dumps(dict(source="ch03_surface_ablation.json", schedules=20, proposals=len(rows), results=out), indent=1))
