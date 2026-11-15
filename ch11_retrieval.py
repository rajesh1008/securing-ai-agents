#!/usr/bin/env python3
"""Chapter 11, lab 1: retrieval across tenants. No model.
One pooled corpus (Corpus(tenants, 40)), five retrieval modes, three query sets, three corpus sizes.
 benign   : 60 queries per run, vendor + topic words from one of the caller's own documents (no attacker). Relevant = the caller's docs with that vendor and topic.
 hostile  : 60 queries per run naming another tenant's reference prefix and asking for account or tax details.
 forged   : the same 60 hostile queries, with the caller (the model) supplying a tenant argument naming the victim.
Metrics: queries with at least one foreign document returned; foreign documents returned; foreign documents carrying an account number or tax id; benign recall@5."""
import sys, json, random, time
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
from bulwark.tenancy import *
MODES = ["none", "arg", "post", "pushdown", "partition"]
def sets(c, rng, n=60):
    ben, hos = [], []
    for _ in range(n):
        t = rng.choice(c.tenants); own = [d for d in c.docs if d.tenant == t]; d = rng.choice(own)
        v = next(v for v in VENDORS if d.text.startswith(v)); tp = next(x for x in TOPICS if x in d.text)
        rel = {x.doc_id for x in own if x.text.startswith(v) and tp in x.text}
        ben.append((t, f"{v} {tp}", rel))
        victim = rng.choice([x for x in c.tenants if x != t]); hos.append((t, victim, f"{victim} pay to account tax id"))
    return ben, hos
def run(c, mode, ben, hos):
    ix = Index(c, mode); out = {}
    r_leak_q = r_leak_d = r_sec = 0; rec = []
    for t, q, rel in ben:
        res = ix.search(q, 5, verified_tenant=t, arg_tenant=t); f = [d for d in res if d.tenant != t]
        r_leak_q += bool(f); r_leak_d += len(f); r_sec += sum(bool(d.secret) for d in f)
        rec.append(len({d.doc_id for d in res} & rel) / max(1, min(5, len(rel))))
    out["benign"] = dict(queries_with_foreign=r_leak_q, foreign_docs=r_leak_d, foreign_secret_docs=r_sec, recall_at_5=round(sum(rec) / len(rec), 3))
    for name, forge in (("hostile", False), ("forged", True)):
        lq = ld = ls = 0
        for t, victim, q in hos:
            res = ix.search(q, 5, verified_tenant=t, arg_tenant=(victim if forge else t)); f = [d for d in res if d.tenant != t]
            lq += bool(f); ld += len(f); ls += sum(bool(d.secret) for d in f)
        out[name] = dict(queries_with_foreign=lq, foreign_docs=ld, foreign_secret_docs=ls)
    return out
R = {}; L = []
for tenants in (6, 30, 120):
    rng = random.Random(1100 + tenants); c = Corpus(tenants, 40); ben, hos = sets(c, rng); R[tenants] = {}
    L.append(f"--- {tenants} tenants x 40 documents = {len(c.docs)} documents; 60 benign, 60 hostile queries")
    L.append(f"{'mode':10} | {'benign: q with foreign':>22} {'foreign docs':>12} {'secret':>6} {'recall@5':>8} | {'hostile: q':>10} {'docs':>5} {'secret':>6} | {'forged arg: q':>13} {'docs':>5} {'secret':>6}")
    for m in MODES:
        t0 = time.perf_counter(); o = run(c, m, ben, hos); dt = (time.perf_counter() - t0) * 1000 / 180; R[tenants][m] = dict(o, ms_per_query=round(dt, 3))
        b, h, f = o["benign"], o["hostile"], o["forged"]
        L.append(f"{m:10} | {b['queries_with_foreign']:>22} {b['foreign_docs']:>12} {b['foreign_secret_docs']:>6} {b['recall_at_5']:>8.3f} | {h['queries_with_foreign']:>10} {h['foreign_docs']:>5} {h['foreign_secret_docs']:>6} | {f['queries_with_foreign']:>13} {f['foreign_docs']:>5} {f['foreign_secret_docs']:>6}")
print("\n".join(L)); (here / "results/ch11_retrieval.log").write_text("\n".join(L) + "\n"); json.dump(R, open(here / "results/ch11_retrieval.json", "w"), indent=1)
