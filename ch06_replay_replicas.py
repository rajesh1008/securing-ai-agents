#!/usr/bin/env python3
"""Chapter 6 lab 6b: a one-use token presented to several gateway replicas. In-memory use counters give each replica its own budget.
Replicas are separate OS processes; the shared arm uses an atomic SQLite counter. No model calls."""
import json, os, sys, tempfile, time
from multiprocessing import get_context
from pathlib import Path
from bulwark.models import ActionProposal, ActionKind as K
from bulwark.identity import Issuer, Verifier, Scope, SqliteUseStore
here = Path(__file__).resolve().parent
WL = "spiffe://ledgerly.example/ns/agents/sa/quill"
pp = ActionProposal(kind=K.INITIATE_PAYMENT, business_id="biz_hcb", principal_id="prin_emily", amount_cents=50_000, payee_id="payee_lone_star")
def replica(args):
    token, pubs, store_path = args
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    keys = {k: Ed25519PublicKey.from_public_bytes(v) for k, v in pubs.items()}
    store = SqliteUseStore(store_path) if store_path else None
    v = Verifier(keys, lambda k: ("active", 0.0), use_store=store)
    return v.verify(token, pp, caller_workload=WL).allow
def run(replicas, shared, rounds=100):
    iss = Issuer()
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
    pubs = {k: p.public_bytes(Encoding.Raw, PublicFormat.Raw) for k, p in iss.public_keys().items()}
    tmp = tempfile.mkdtemp(); extra = 0; allows = 0; worst = 0
    ctx = get_context("fork")
    with ctx.Pool(replicas) as pool:
        for r in range(rounds):
            tok = iss.issue(principal="prin_emily", tenant="biz_hcb", workload=WL, task_id=f"t{r}", scope=Scope(kinds=["initiate_payment"], payees=["payee_lone_star"], max_cents=250_000), uses=1)
            path = os.path.join(tmp, "uses.db") if shared else None
            # the same token is presented once to each replica (a load balancer spraying a replay)
            res = pool.map(replica, [(tok, pubs, path)] * replicas, chunksize=1)
            n = sum(res); allows += n; worst = max(worst, n); extra += (n > 1)
    return dict(replicas=replicas, rounds=rounds, one_use_tokens=rounds, total_allows=allows, rounds_with_more_than_one_allow=extra, worst_case_allows=worst)
out = {}
for replicas in (1, 4):
    for shared in (False, True):
        k = f"replicas{replicas}_{'shared_store' if shared else 'memory'}"
        out[k] = run(replicas, shared); print(k, json.dumps(out[k]), flush=True)
(here / "results/ch06_replay_replicas.json").write_text(json.dumps(out, indent=1))
