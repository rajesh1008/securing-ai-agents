#!/usr/bin/env python3
"""Chapter 6 lab 6: a one-use token presented by many threads at once. Check-then-set on the use counter is a race. No model calls."""
import json, sys, threading, time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from bulwark.models import ActionProposal, ActionKind as K
from bulwark.identity import Issuer, Verifier, Scope
here = Path(__file__).resolve().parent
WL = "spiffe://ledgerly.example/ns/agents/sa/quill"
pp = ActionProposal(kind=K.INITIATE_PAYMENT, business_id="biz_hcb", principal_id="prin_emily", amount_cents=50_000, payee_id="payee_lone_star")
sys.setswitchinterval(1e-6)   # make thread switches frequent so the window is visible
class Locked(Verifier):
    def __init__(self, *a, **k): super().__init__(*a, **k); self._lock = threading.Lock()
    def verify(self, *a, **k):
        with self._lock: return super().verify(*a, **k)
def trial(cls, threads=32, rounds=300):
    iss = Issuer(); extra = 0; worst = 0; spent_total = 0
    ver = cls(iss.public_keys(), lambda k: iss.status[k])
    for r in range(rounds):
        tok = iss.issue(principal="prin_emily", tenant="biz_hcb", workload=WL, task_id=f"t{r}", scope=Scope(kinds=["initiate_payment"], payees=["payee_lone_star"], max_cents=250_000), uses=1)
        barrier = threading.Barrier(threads); res = []
        def go(_):
            barrier.wait(); res.append(ver.verify(tok, pp, caller_workload=WL).allow)
        with ThreadPoolExecutor(threads) as ex: list(ex.map(go, range(threads)))
        n = sum(res); spent_total += n; worst = max(worst, n); extra += (n > 1)
    return dict(rounds=rounds, threads=threads, rounds_with_double_spend=extra, worst_case_allows=worst, total_allows=spent_total, expected_allows=rounds)
out = {}
for name, cls in (("unlocked", Verifier), ("locked", Locked)):
    out[name] = trial(cls); print(name, json.dumps(out[name]))
(here / "results/ch06_replay_race.json").write_text(json.dumps(out, indent=1))
