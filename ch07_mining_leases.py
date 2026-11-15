#!/usr/bin/env python3
"""Chapter 7 labs 6-8 (no model calls): (6) scope learned from traces vs scope computed from records; (7) widening policies for a lease; (8) cost of computing a scope."""
import json, random, time, collections
from pathlib import Path
from bulwark.identity import Scope
from bulwark.runtime_scope import *
here = Path(__file__).resolve().parent
B = make_books(); CEIL = Ceiling(kinds=ALL_KINDS, payees=list(B.payees), max_cents=250_000, mail_domains=[c["domain"] for c in B.customers.values()] + [p["domain"] for p in B.payees.values()])
out = {}
# ---------------- lab 6: mining ----------------
R = random.Random(77)
W = {"payee_lone_star": 40, "payee_riverside": 25, "payee_capitol": 20, "payee_zilker": 8, "payee_bsdairy": 4, "payee_mueller": 2, "payee_hydepark": 0.7, "payee_pecan": 0}   # pecan: legitimate but never in the window
def legit_trace():
    p = R.choices(list(W), weights=list(W.values()))[0]
    big = R.random() < 0.008
    return dict(kind="initiate_payment", payee=p, amount=R.randrange(180_000, 249_000, 100) if big else R.randrange(8_000, 90_000, 100))
history = [legit_trace() for _ in range(5000)]
# held-out legitimate payments, plus the legitimate rare ones the window may never contain
held = [legit_trace() for _ in range(5000)] + [dict(kind="initiate_payment", payee="payee_pecan", amount=41_000)] * 25
poison = [dict(kind="initiate_payment", payee="payee_pecan", amount=240_000)] * 3
print("lab 6: scope mined from traces (payments only; held-out 5,025 legitimate payments; 25 of them are to payee_pecan, which never appears in the window)")
print(f"{'window':>8}{'min_count':>10}{'payees in scope':>17}{'max $':>8}{'legit denied':>14}{'pecan 240k admitted':>21}{'with 3 poisoned traces: pecan 240k admitted':>46}")
mine_rows = []
for n in (50, 200, 1000, 5000):
    for mc in (1, 5):
        tr = history[:n]; s = mine_scope(tr, mc); sp = mine_scope(tr + poison, mc)
        den = sum(not admits(s, "initiate_payment", payee=h["payee"], amount=h["amount"]) for h in held)
        a = admits(s, "initiate_payment", payee="payee_pecan", amount=240_000); ap = admits(sp, "initiate_payment", payee="payee_pecan", amount=240_000)
        mine_rows.append(dict(window=n, min_count=mc, payees=len(s.payees or []), max_usd=(s.max_cents or 0) / 100, legit_denied=den, hostile_admitted=a, hostile_admitted_poisoned=ap))
        print(f"{n:>8}{mc:>10}{len(s.payees or []):>17}{(s.max_cents or 0)/100:>8.0f}{den:>8}/{len(held)}{str(a):>14}{str(ap):>40}")
# computed from the books for the same held-out stream: tasks derived from open invoices
b_den = 0; b_n = 0
for inv_id, inv in B.invoices.items():
    if inv["status"] != "open": continue
    s = compute_scope(TaskRequest("pay_invoice", "p", "t", {"invoice_id": inv_id}), B, CEIL); b_n += 1
    b_den += not admits(s, "initiate_payment", payee=inv["payee_id"], amount=inv["amount_cents"])
print(f"computed from the books: {b_den} of {b_n} legitimate payments denied; a payment to a payee with no open invoice is never in scope")
out["mining"] = dict(rows=mine_rows, computed_denied=b_den, computed_n=b_n, held=len(held))
# ---------------- lab 7: leases ----------------
R = random.Random(2026)
tasks = []
for i in range(400):
    legit = R.random() < 0.06           # the principal's next message asks for a second invoice from the same vendor
    inj = R.random() < 0.25             # a document asks the agent to request wider authority
    tasks.append(dict(legit=legit, inj=inj))
base = Scope(kinds=["query_books", "initiate_payment"], payees=["payee_lone_star"], max_cents=120_000)
legit_wide = Scope(kinds=["query_books", "initiate_payment"], payees=["payee_lone_star"], max_cents=240_000)
hostile_wide = Scope(kinds=["query_books", "initiate_payment", "send_email"], payees=["payee_lone_star", "payee_riverside"], max_cents=250_000, mail_domains=[c["domain"] for c in B.customers.values()][:5])
def run(mode, origin_aware=False):
    pol = LeasePolicy(mode, 3, CEIL); r = collections.Counter()
    for t in tasks:
        L = Lease(base, pol)
        reqs = ([("legit", legit_wide, True)] if t["legit"] else []) + ([("hostile", hostile_wide, False)] if t["inj"] else [])
        for kind, w, trusted in reqs:
            if origin_aware and not trusted: r["hostile_denied"] += (kind == "hostile"); continue
            d = L.request(w, reason=kind, trusted_origin=trusted)
            if d.granted: r[kind + "_granted_automatically"] += 1
            elif d.needs_human: r["queued_for_person"] += 1; r["queued_" + kind] += 1
            else: r[kind + "_denied"] += 1
    return dict(r)
res = {"never": run("never"), "auto_within_ceiling": run("auto_within_ceiling"), "human_queue_all": run("human"), "human_queue_trusted_origin_only": run("human", origin_aware=True)}
n_leg = sum(t["legit"] for t in tasks); n_inj = sum(t["inj"] for t in tasks)
print(f"\nlab 7: 400 tasks, {n_leg} with a legitimate widening need (from the principal), {n_inj} with a hostile widening request (from a document)")
for k, v in res.items(): print(f"  {k:34}", v)
out["leases"] = dict(tasks=400, legit=n_leg, hostile_requests=n_inj, policies=res)
# ---------------- lab 8: cost ----------------
reqs = [TaskRequest("pay_invoice", "p", "t", {"invoice_id": k}) for k, v in B.invoices.items() if v["status"] == "open"]
t0 = time.perf_counter()
for _ in range(2000):
    for r_ in reqs: compute_scope(r_, B, CEIL)
dt = (time.perf_counter() - t0) / (2000 * len(reqs)) * 1e6
t0 = time.perf_counter()
for _ in range(50): compute_scope(TaskRequest("reconcile_month", "p", "t", {"today": 20, "window_days": 7}), B, CEIL)
dr = (time.perf_counter() - t0) / 50 * 1e6
print(f"\nlab 8: compute_scope pay_invoice {dt:.1f} us; reconcile_month over {len(B.invoices)} invoices {dr:.1f} us")
out["cost_us"] = dict(pay_invoice=round(dt, 1), reconcile_month=round(dr, 1), invoices=len(B.invoices))
(here / "results/ch07_mining_leases.json").write_text(json.dumps(out, indent=1))
