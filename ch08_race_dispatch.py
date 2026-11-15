#!/usr/bin/env python3
"""Chapter 8 labs 3 and 4: (3) the same invoice submitted twice at once, check-then-pay versus an atomic reserve; (4) state that changes between decision and dispatch, with and without the dispatch recheck. No model."""
import json, random, sys, threading, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
from bulwark.moneypath import *
rng = random.Random(8003); out = {}; lines = []
# --- lab 3: double submission
def lab3(n=400, mode="naive", workers=8, shuffle=False):
    vs = Vendors({"p1": Vendor("p1", "Vendor", "ACC", 10**9, live_since=-300, created_day=-365, confirmed_by="kb")})
    invs = {f"I{i}": Invoice(f"I{i}", "p1", 10_000 + i) for i in range(n)}
    g = MoneyGate("t", vs, invs, Ledger(), tenant_daily_cap=10**12, payee_daily_count=10**6, payee_daily_cents=10**12)
    sent = []; sl = threading.Lock(); barrier = {}
    def worker(i):
        r = PayRequest(f"I{i}", "p1", 10_000 + i, day=100)
        if mode == "naive":
            if invs[r.invoice_id].status == "open":      # check ...
                time.sleep(0.0005)                         # ... a network call to the rail sits here ...
                with sl: sent.append(r.invoice_id)          # ... then act
                invs[r.invoice_id].status = "paid"
        elif mode == "reserve":
            d = g.check(r)
            if d.outcome == "ALLOW":
                time.sleep(0.0005)
                with sl: sent.append(r.invoice_id)
                g.ledger.settle(d.key)
    jobs = [i for i in range(n) for _ in range(2)]
    if shuffle: rng.shuffle(jobs)
    with ThreadPoolExecutor(workers) as ex: list(ex.map(worker, jobs))
    return len(sent), len(set(sent))
for mode, sh in (("naive", False), ("naive", True), ("reserve", False), ("reserve", True)):
    runs = [lab3(mode=mode, shuffle=sh) for _ in range(5)]
    tag = mode + ("_shuffled" if sh else "_adjacent")
    out[f"lab3_{tag}"] = dict(runs=runs); lines.append(f"lab3 {tag:16} 400 invoices x2 submissions x5 runs: payments sent per run {[r[0] for r in runs]}, distinct invoices {[r[1] for r in runs]}, double-paid {[r[0]-r[1] for r in runs]}")
# --- lab 4: state changes after the decision
def lab4(recheck, n=500):
    rng = random.Random(8004)
    vend = {f"p{i}": Vendor(f"p{i}", f"V{i}", f"ACC{i}", 10**9, live_since=-300, created_day=-365, confirmed_by="kb") for i in range(10)}
    vs = Vendors(vend); invs = {}
    g = MoneyGate("t", vs, invs, Ledger(), tenant_daily_cap=10**12, payee_daily_count=10**6, payee_daily_cents=10**12)
    disp = Dispatcher(g, recheck=recheck); stats = dict(changed_account=0, paid_elsewhere=0, amount_edited=0, sent_to_stale=0, sent_stale_invoice=0, blocked=0, sent_clean=0)
    for i in range(n):
        p = f"p{i % 10}"; invs[f"I{i}"] = Invoice(f"I{i}", p, 20_000 + i); r = PayRequest(f"I{i}", p, 20_000 + i, day=100 + i // 10)
        d = g.check(r); assert d.outcome == "ALLOW"
        u = rng.random(); stale = None
        if u < 0.04:   # vendor account changed and confirmed between decision and dispatch (a real change, or a compromised portal)
            vs.request_change(p, "NEW-" + p, r.day, "portal"); vs.confirm_change(p, r.day, "kb", True); stats["changed_account"] += 1; stale = "acct"
        elif u < 0.07:  # change requested, not confirmed
            vs.request_change(p, "MULE", r.day, "email"); stats["changed_account"] += 1; stale = "acct"
        elif u < 0.10:  # someone paid the invoice outside Quill
            invs[r.invoice_id].status = "paid"; stats["paid_elsewhere"] += 1; stale = "inv"
        elif u < 0.12:  # amount corrected in the books
            invs[r.invoice_id].amount_cents += 100; stats["amount_edited"] += 1; stale = "inv"
        ok, why = disp.dispatch(r, d)
        if ok and stale == "acct": stats["sent_to_stale"] += 1
        elif ok and stale == "inv": stats["sent_stale_invoice"] += 1
        elif ok: stats["sent_clean"] += 1
        else: stats["blocked"] += 1
        if vs.v[p].pending: vs.reject_change(p)
        if stale == "acct": vend[p].account = "ACC" + p[1:]; vend[p].live_since = -300; vend[p].confirmed_by = "kb"
    return stats
for rc in (False, True):
    s = lab4(rc); out[f"lab4_recheck_{rc}"] = s; lines.append(f"lab4 recheck={rc}: {s}")
print("\n".join(lines)); (here / "results/ch08_race_dispatch.json").write_text(json.dumps(out, indent=1)); (here / "results/ch08_race_dispatch.log").write_text("\n".join(lines) + "\n")
