#!/usr/bin/env python3
"""Chapter 8 lab 1 and 2: five payment attack classes plus benign traffic, run through (A) everything Chapters 1-7 built and (B) the money path.
No model is called. Seeded. Writes results/ch08_classes.json and .log."""
import json, random, sys, os
from collections import Counter, defaultdict
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
from bulwark.moneypath import *
import bulwark.moneypath as mp
mp.HOLD_DAYS = int(os.environ.get('HD', mp.HOLD_DAYS))
rng = random.Random(8008)
VEND = {f"p{i}": (f"Vendor {i}", f"ACC-{i:02d}", 250_000 if i % 2 else 500_000) for i in range(24)}
MULE = "MULE-ACC-99"
events = []; n = 0
def ev(**k):
    global n; n += 1; k["eid"] = n; events.append(k)
inv_no = [1000]
def new_inv():
    inv_no[0] += 1; return f"INV-{inv_no[0]}"
def day_of(): return rng.randrange(10, 85)
# benign
for _ in range(1200):
    p = rng.choice(list(VEND)); amt = rng.randrange(8_000, VEND[p][2] - 100_000, 100) if VEND[p][2] > 250_000 else rng.randrange(8_000, 240_000, 100)
    ev(day=day_of(), cls="benign", payee=p, amount=amt, doc=amt, inv=new_inv(), approver="prin_kevin" if amt >= DUAL_CONTROL_CENTS else None)
for _ in range(60):   # recurring: a second small invoice for the same amount within days (weekly delivery)
    p = rng.choice(list(VEND)); amt = rng.randrange(20_000, 60_000, 100); d = rng.randrange(10, 70)
    for k in range(2): ev(day=d + k * 4, cls="benign_recurring", payee=p, amount=amt, doc=amt, inv=new_inv(), approver=None)
for _ in range(25):   # two or three invoices the same day for one vendor
    p = rng.choice(list(VEND)); d = day_of()
    for k in range(rng.choice([2, 2, 3])):
        amt = rng.randrange(10_000, 90_000, 100); ev(day=d, cls="benign_burst", payee=p, amount=amt, doc=amt, inv=new_inv(), approver=None)
legit_changes = [(rng.choice(list(VEND)), rng.randrange(15, 60)) for _ in range(16)]
for p, d in legit_changes:
    ev(day=d, cls="legit_bank_change", payee=p, amount=0, doc=0, inv=None, approver=None, new_account=f"NEW-{p}-{d}")
    for k in range(rng.choice([1, 2, 3])):
        amt = rng.randrange(10_000, 120_000, 100); ev(day=d + rng.randrange(0, 12), cls="benign_after_change", payee=p, amount=amt, doc=amt, inv=new_inv(), approver=None)
# attacks
for _ in range(60):   # dup_resent: same invoice entered a second time under a new number
    p = rng.choice(list(VEND)); amt = rng.randrange(20_000, 200_000, 100); d = rng.randrange(10, 70)
    ev(day=d, cls="benign_seed", payee=p, amount=amt, doc=amt, inv=new_inv(), approver="prin_kevin" if amt >= DUAL_CONTROL_CENTS else None, seed_for_dup=True)
    ev(day=d + rng.randrange(2, 9), cls="dup_resent", payee=p, amount=amt, doc=amt, inv=new_inv(), approver=None)
for _ in range(60):   # bank change delivered on the invoice itself
    p = rng.choice(list(VEND)); amt = rng.randrange(20_000, 200_000, 100)
    ev(day=day_of(), cls="bank_change", payee=p, amount=amt, doc=amt, inv=new_inv(), approver=None, remit=MULE)
for _ in range(60):   # books amount differs from the document
    p = rng.choice(list(VEND)); amt = rng.randrange(10_000, 24_000, 100)
    ev(day=day_of(), cls="amount_mismatch", payee=p, amount=amt, doc=amt * 10, inv=new_inv(), approver=None)
for _ in range(30):   # structuring: four invoices under the limit on one day
    p = rng.choice(list(VEND)); d = day_of()
    for k in range(4): ev(day=d, cls="structuring", payee=p, amount=190_000 - 3_000 * k, doc=190_000 - 3_000 * k, inv=new_inv(), approver=None, limit_ok=True)
for _ in range(40):   # new payee paid the day after it is created
    d = day_of(); ev(day=d, cls="new_payee", payee=f"pn{_}", amount=rng.randrange(80_000, 240_000, 100), doc=0, inv=new_inv(), approver=None, create_payee=True)
events.sort(key=lambda e: (e["day"], e["eid"]))
for e in events:
    if e["cls"] == "new_payee": e["doc"] = e["amount"]; e["created"] = e["day"] - 1

def run(design):
    vend = {p: Vendor(p, nm, acc, lim, live_since=-300, created_day=-365, confirmed_by="kb") for p, (nm, acc, lim) in VEND.items()}
    vs = Vendors(vend); invs = {}; ledger = Ledger(); gate = MoneyGate("t", vs, invs, ledger, tenant_daily_cap=5_000_000, payee_daily_count=int(os.environ.get('PDC', 2)), payee_daily_cents=int(os.environ.get('PDCENTS', 500_000))); disp = Dispatcher(gate)
    paid_ledger = []   # design A's own ledger: (payee, inv status)
    released = Counter(); reasons = defaultdict(Counter); out = defaultdict(Counter); money = defaultdict(int); bad_dest = Counter(); pending_confirm = []
    for e in events:
        d = e["day"]; cls = e["cls"]
        for pc in [x for x in pending_confirm if x[0] <= d]:
            pending_confirm.remove(pc)
            if design == "B":
                if pc[2]: vs.confirm_change(pc[1], d, "kb", True)
                else: vs.reject_change(pc[1])
        if cls == "legit_bank_change":
            if design == "A": vend[e["payee"]].account = e["new_account"]
            else: vs.request_change(e["payee"], e["new_account"], d, "vendor_portal"); pending_confirm.append((d + 1, e["payee"], True))
            continue
        if e.get("create_payee"):
            vend[e["payee"]] = Vendor(e["payee"], "New Vendor", f"ACC-{e['payee']}", 250_000, live_since=e["created"], created_day=e["created"], confirmed_by=None)
        invs[e["inv"]] = Invoice(e["inv"], e["payee"], e["amount"], "open", e["inv"], True)
        ven = vend[e["payee"]]
        if e.get("remit"):
            if design == "A": ven.account = e["remit"]            # remit-to line on the invoice is applied
            else: vs.request_change(e["payee"], e["remit"], d, "invoice_document"); pending_confirm.append((d + 1, e["payee"], False))
        r = PayRequest(e["inv"], e["payee"], e["amount"], doc_amount_cents=e["doc"] if design == "B" else None, day=d, approver=e["approver"])
        if design == "A":
            ok = ven is not None and e["amount"] <= ven.limit_cents and invs[e["inv"]].status == "open" and invs[e["inv"]].amount_cents == e["amount"]
            if ok:
                invs[e["inv"]].status = "paid"; out[cls]["ALLOW"] += 1; money[cls] += e["amount"]
                if ven.account == MULE: bad_dest[cls] += 1
            else: out[cls]["DENY"] += 1
        else:
            dec = gate.check(r); out[cls][dec.outcome] += 1
            if dec.outcome == "HOLD" and cls.startswith("benign"):   # the person approves the benign ones: assumption, a perfect reviewer
                ledger.reserve(dec.key, e["inv"], e["payee"], e["amount"], d, dec.destination); invs[e["inv"]].status = "paid"; released[cls] += 1
            for c_ in dec.codes: reasons[cls][c_.split('_of_')[0]] += 1
            if dec.outcome == "ALLOW":
                ok, why = disp.dispatch(r, dec)
                if ok:
                    money[cls] += e["amount"]
                    if dec.destination == MULE: bad_dest[cls] += 1
    return {c: dict(v) for c, v in out.items()}, dict(money), dict(bad_dest), {c: dict(v) for c, v in reasons.items()}, dict(released)
res = {}; lines = []
for design in ("A", "B"):
    o, m, b, rs, rel = run(design); res[design] = dict(outcomes=o, cents_moved=m, to_mule=b, reasons=rs, released=rel)
ATT = ["dup_resent", "bank_change", "amount_mismatch", "structuring", "new_payee"]
BEN = ["benign", "benign_recurring", "benign_burst", "benign_after_change", "benign_seed"]
tot = Counter(e["cls"] for e in events)
lines.append(f"events {len(events)}: " + ", ".join(f"{k} {v}" for k, v in sorted(tot.items())))
for design, label in (("A", "A: Chapters 1-7 (registry, payee limit, invoice binding, task scope)"), ("B", "B: money path (M1-M8, hold queue, dispatch recheck)")):
    lines.append(f"\n{label}")
    for c in ATT: 
        o = res[design]["outcomes"].get(c, {}); lines.append(f"  attack {c:16} n={tot[c]:4} executed {o.get('ALLOW',0):4} held {o.get('HOLD',0):4} denied {o.get('DENY',0):4}  cents moved {res[design]['cents_moved'].get(c,0):>11,}  to mule account {res[design]['to_mule'].get(c,0)}")
    for c in BEN:
        o = res[design]["outcomes"].get(c, {}); lines.append(f"  benign {c:20} n={tot[c]:4} executed {o.get('ALLOW',0):4} held {o.get('HOLD',0):4} denied {o.get('DENY',0):4}")
    b_all = sum(sum(res[design]["outcomes"].get(c, {}).values()) for c in BEN); b_ok = sum(res[design]["outcomes"].get(c, {}).get("ALLOW", 0) for c in BEN)
    lines.append(f"  benign total {b_all}, executed straight through {b_ok}, to a person {b_all-b_ok-sum(res[design]['outcomes'].get(c,{}).get('DENY',0) for c in BEN)}, denied {sum(res[design]['outcomes'].get(c,{}).get('DENY',0) for c in BEN)}")
    if design == "B":
        for c in ATT + BEN: lines.append(f"  reasons {c:20} {res[design]['reasons'].get(c, {})}")
    lines.append(f"  hostile cents moved total {sum(res[design]['cents_moved'].get(c,0) for c in ATT):,}")
print("\n".join(lines))
SUF = os.environ.get("SUF", "")
(here / f"results/ch08_classes{SUF}.json").write_text(json.dumps(dict(counts=tot, designs=res), indent=1)); (here / f"results/ch08_classes{SUF}.log").write_text("\n".join(lines) + "\n")
