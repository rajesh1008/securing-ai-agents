#!/usr/bin/env python3
"""Chapter 15, lab 2 (no model): the completeness audit that Chapter 13 left open. Every decision the flow makes (document verdict, gate verdict, dispatch verdict, registry action) must write one event.
(a) 400 mixed submissions through the full flow: decisions counted by the flow against rows in the tenant's chain, by kind.
(b) the same traffic through a flow with one forgetful path (the dispatch-blocked path does not write), and one with a bypass (a tool that dispatches without the gate): does the audit see them?
(c) a static check: every code path in reconcile.py that assigns a Decision or a route is followed by an ev() call (source scan)."""
import sys, json, random, re, inspect
from collections import Counter
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
from bulwark.reconcile import *
from bulwark.docagent import parse_rules
from bulwark.evidence import Vault
import bulwark.reconcile as RC
import ch14_corpus as C, ch15_ablation as X
out = []
def say(s): out.append(s); print(s)
def traffic(flow, A, B, n=400, seed=15):
    rng = random.Random(seed); open_ids = [i for i, x in A.invoices.items() if x["status"] == "open" and i not in ("I100", "I101")]; docs = []
    for k in range(n):
        i = rng.choice(open_ids); r = rng.random()
        if r < 0.55: d, _ = C.clean(A, i, rng); docs.append(d)
        elif r < 0.90: docs.append(C.hostile(A, i, rng.choice(C.CLASSES), rng))
        elif r < 0.95: docs.append(X.framed(A, i, rng.choice(["ticket", "portal"])))
        else: d, _ = C.clean(B, rng.choice(["B000", "B001"]), rng, noise=False); docs.append(d)
    for k in range(0, n, 8): flow.run(docs[k:k + 8], day=100 + k // 8)
def audit(flow, vault, tenant):
    rows = vault.logs[tenant].rows; by = Counter(r["kind"] for r in rows)
    return len(rows), by
f, A, B, T = X.make(dict(V=True, G=True, R=True, D=True, T=True)); traffic(f, A, B)
n, by = audit(f, f.vault, "biz_hcb"); f.vault.seal("biz_hcb")
say(f"(a) full flow, 400 submissions: flow made {f.decisions} decisions; chain holds {n} rows {dict(by)}; equal: {f.decisions == n}; chain verifies: {f.vault.verify('biz_hcb')}; payments sent {len(f.sent)}; harm {X.harm(f, T)}")
# (b1) a forgetful path: the dispatch-blocked event is not written. Decisions are counted at the decision site, rows at the vault.
class Forgetful(Flow):
    def ev(self, **f):
        if f.get("kind") == "dispatch" and f.get("decision") == "BLOCKED": self.decisions += 1; return
        super().ev(**f)
# use a stale-decision scenario inside the traffic so that the blocked path is taken: a bank change between decision and dispatch
def with_between(flow_cls):
    recA, recB = X.world(); books = {"biz_hcb": books_from(recA), "biz_bcp": books_from(recB)}; fl = flow_cls("biz_hcb", books, Vault(b"\x16" * 32, 10))
    ids = [i for i, x in recA.invoices.items() if x["status"] == "open" and x["payee_id"] == "payee_1" and x["amount_cents"] < 200_000][:2]
    docs = [C.clean(recA, i, random.Random(i), noise=False)[0] for i in ids]
    def between(fl): fl.vendors.request_change("payee_1", "US-ACC-55500009", 100, "letter"); fl.vendors.confirm_change("payee_1", 100, "nina", True)
    fl.run(docs, between=between); return fl
for cls in (Flow, Forgetful):
    fl = with_between(cls); n, by = audit(fl, fl.vault, "biz_hcb"); say(f"(b) {cls.__name__:10s}: decisions counted at the decision site {fl.decisions}, rows in the chain {n}; audit {'passes' if fl.decisions == n else 'FAILS: ' + str(fl.decisions - n) + ' decision(s) left no event'}; by kind {dict(by)}")
# (b2) a bypass: a tool that dispatches without calling the flow at all. The decision counter never sees it, the chain never sees it. Only the rail does.
fl = with_between(Flow); before = (fl.decisions, len(fl.vault.logs['biz_hcb'].rows)); fl.sent.append(("I999", "US-ACC-66600001", 12_345)); after = (fl.decisions, len(fl.vault.logs['biz_hcb'].rows))
say(f"(b) bypass: a payment dispatched outside the flow: decision counter {before[0]}->{after[0]}, chain rows {before[1]}->{after[1]}; payments on the rail {len(fl.sent)} against dispatch rows in the chain {sum(1 for r in fl.vault.logs['biz_hcb'].rows if r['kind']=='dispatch' and r['decision']=='SENT')}")
say("    the count that catches it is the rail's own: payments sent per the dispatcher/bank against SENT rows in the chain, compared outside the flow's code")
# (c) static scan
src = inspect.getsource(RC.Flow); lines = src.splitlines(); miss = []
for k, l in enumerate(lines):
    if re.search(r"\b(r\.dec = |v = verify\(|ok, why = self\._dispatch|self\.vendors\.request_change|v\.previous_account, v\.account)", l):
        window = "\n".join(lines[k:k + 6])
        if "self.ev(" not in window: miss.append((k + 1, l.strip()[:90]))
say(f"(c) static scan of Flow: decision sites with no ev() call within six lines: {len(miss)}" + ("" if not miss else " " + str(miss)))
fsrc = inspect.getsource(Forgetful); sites = [l for l in fsrc.splitlines() if re.search(r"r\.dec = |verify\(|_dispatch", l)]
say(f"    the same scan on the forgetful subclass: {len(sites)} decision sites to flag, so nothing is flagged; the drop is a condition inside its ev() override, which a scan of call sites cannot see and the runtime count does")
json.dump(out, open(here / "results/ch15_audit.json", "w"), indent=1); open(here / "results/ch15_audit.log", "w").write("\n".join(out) + "\n")
