#!/usr/bin/env python3
"""Chapter 11, lab 7: pooled statistics as a channel between tenants. No model.
Question: with the tenant filter applied correctly (pushdown), does tenant A's result for a query depend on what tenant B stores?
The ranker's idf is computed over the whole pool in 'pushdown' mode and over A's documents only in 'partition' mode.
Method: for 40 queries built from A's own vendor names and topics, record A's top-5 doc ids and A's score list; then add 60 documents to tenant B that
repeat the query's most frequent term, rebuild the index, and compare. No documents of B are ever returned to A in any run."""
import sys, json, copy, random
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
from bulwark.tenancy import *
from bulwark.tenancy import _Idx

def build(corpus, mode):
    c = copy.copy(corpus); c.docs = list(corpus.docs); return Index(c, mode)

def ranked(ix, A, q):
    if ix.mode == "partition": r = ix.parts[A].rank(q)
    else: r = ix.pool.rank(q, lambda d: d.tenant == A)
    return [(round(s, 6), d.doc_id) for s, d in r[:5]]

corpus = Corpus(tenants=30, per_tenant=60); A, B = corpus.tenants[0], corpus.tenants[1]
rng = random.Random(7)
queries = []
for v in corpus.vendors_of[A]:
    for t in TOPICS[:8]: queries.append(f"{v} {t}")
queries = rng.sample(queries, 40)
L = []; R = {}
for mode in ("pushdown", "partition"):
    base = build(corpus, mode); order_changed = score_changed = foreign = 0
    for q in queries:
        before = ranked(base, A, q)
        term = max(tokens(q), key=lambda w: base.pool.idf.get(w, 0))
        extra = [Doc(f"{B}-x{n:03d}", B, f"{term} {term} {term} filler note {n}.") for n in range(60)]
        c2 = copy.copy(corpus); c2.docs = corpus.docs + extra; after_ix = Index(c2, mode)
        after = ranked(after_ix, A, q)
        order_changed += [d for _, d in before] != [d for _, d in after]
        score_changed += [s for s, _ in before] != [s for s, _ in after]
        foreign += sum(1 for _, d in after if not d.startswith(A))
    L.append(f"{mode:10} queries {len(queries)}  A's top-5 order changed {order_changed}  A's scores changed {score_changed}  rows from other tenants returned to A {foreign}")
    R[mode] = dict(queries=len(queries), order_changed=order_changed, score_changed=score_changed, foreign_rows=foreign)
print("\n".join(L)); (here / "results/ch11_pooled_statistics.log").write_text("\n".join(L) + "\n"); json.dump(R, open(here / "results/ch11_pooled_statistics.json", "w"), indent=1)
