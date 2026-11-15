#!/usr/bin/env python3
"""Chapter 10, lab 4: the reviewer's queue. No model.
A. Composition of the Chapter 8 hold queue from the recorded results (ch08_classes.json): hold-code hits from hostile versus benign classes.
B. Arithmetic over assumptions: what the queue looks like when hostile prevalence is lower than in my lab, and what a reviewer who approves a fraction f without reading costs.
C. Standing orders (the narrow exemption Chapter 8 left unbuilt): three scopes against 60 recurring benign pairs and two kinds of hostile resend. Real MoneyGate, seeded."""
import sys, json, random
from collections import Counter, defaultdict
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
from bulwark.moneypath import *
from bulwark.approval import StandingOrder, family
L = []; P = L.append
# ---- A ------------------------------------------------------------------------------------------------------------------
d = json.load(open(here / "results/ch08_classes.json")); B = d["designs"]["B"]
HOST = ["dup_resent", "bank_change", "amount_mismatch", "structuring", "new_payee"]
held_h = sum(B["outcomes"][c].get("HOLD", 0) for c in HOST); held_b = sum(v.get("HOLD", 0) for c, v in B["outcomes"].items() if c not in HOST)
n_h = sum(d["counts"][c] for c in HOST); n_b = sum(v for c, v in d["counts"].items() if c not in HOST and c != "legit_bank_change")
P(f"A. Chapter 8 lab, design B: hostile events {n_h}, held {held_h} ({100*held_h/n_h:.1f}%); benign events {n_b}, held {held_b} ({100*held_b/n_b:.1f}%). Queue of {held_h + held_b}: {100*held_h/(held_h+held_b):.1f}% hostile.")
hits = defaultdict(lambda: [0, 0])
for cls, rs in B["reasons"].items():
    for code, k in rs.items():
        if code == "ok": continue
        hits[code][0 if cls in HOST else 1] += k
P(f"{'hold code':40s} {'hits, hostile classes':>22s} {'hits, benign classes':>22s} {'hostile share':>14s}")
for code, (h, b) in sorted(hits.items(), key=lambda x: -sum(x[1])): P(f"{code:40s} {h:>22d} {b:>22d} {100*h/(h+b):>13.1f}%")
# ---- B ------------------------------------------------------------------------------------------------------------------
hr_h, hr_b = held_h / n_h, held_b / n_b
P(f"\nB. Arithmetic over assumptions: 10,000 payment requests a month; hold rates from the lab (hostile {hr_h:.3f}, benign {hr_b:.3f}); 40 seconds per held item (a placeholder, not a measurement); hostile requests the gate allows without a hold {1-hr_h:.3f} of hostile (11.2% in the lab, mostly structuring).")
P(f"{'prevalence':>10s} {'held items':>11s} {'hostile held':>13s} {'hostile share':>14s} {'reviewer min':>13s}   hostile executed if the reviewer approves a fraction f without reading: f=1% f=10% f=50%   and if every held item is approved")
for p in (0.186, 0.01, 0.001, 0.0001):
    hh = 10_000 * p * hr_h; hb = 10_000 * (1 - p) * hr_b; unheld = 10_000 * p * (1 - hr_h)
    P(f"{p:>10.2%} {hh+hb:>11.0f} {hh:>13.1f} {100*hh/(hh+hb):>13.1f}% {40*(hh+hb)/60:>13.0f}   {unheld+0.01*hh:>43.1f} {unheld+0.10*hh:>6.1f} {unheld+0.5*hh:>6.1f}   {unheld+hh:>8.1f}")
# ---- C ------------------------------------------------------------------------------------------------------------------
rng = random.Random(1010)
VEND = [f"p{i}" for i in range(24)]
rec = [(rng.choice(VEND), rng.randrange(20_000, 60_000, 100), rng.randrange(10, 60)) for _ in range(60)]
events = []; n = [0]
def ev(**k): n[0] += 1; k["eid"] = n[0]; events.append(k)
for p, a, d0 in rec:
    ev(day=d0, kind="rec1", payee=p, amount=a); ev(day=d0 + 4, kind="rec2", payee=p, amount=a)
for _ in range(60):
    p = rng.choice(VEND); a = rng.randrange(20_000, 200_000, 100); d0 = rng.randrange(10, 60)
    ev(day=d0, kind="seed", payee=p, amount=a); ev(day=d0 + rng.randrange(2, 9), kind="hostile_naive", payee=p, amount=a)      # a clerk's resend of an unrelated invoice
for k in range(60):
    p, a, d0 = rec[k % len(rec)]; ev(day=d0 + 4 + rng.randrange(2, 9), kind="hostile_knowing", payee=p, amount=a)   # replays a standing order's payee and amount 2 to 8 days after its last payment (cadence is 4 plus or minus 1)
events.sort(key=lambda e: (e["day"], e["eid"]))
SCOPES = {"none": None,
          "exact": lambda p, a, d: StandingOrder(p, a, 4, a, "owner", 999),
          "amount_only": lambda p, a, d: StandingOrder(p, a, None, a, "owner", 999),
          "payee_cap_$2,000": lambda p, a, d: StandingOrder(p, None, None, 200_000, "owner", 999)}
def run(scope):
    vs = Vendors({p: Vendor(p, p, f"ACC-{p}", 500_000, live_since=-300, created_day=-365, confirmed_by="kb") for p in VEND})
    g = MoneyGate("t", vs, {}, Ledger(), tenant_daily_cap=10**9, payee_daily_count=5, payee_daily_cents=10**9); disp = Dispatcher(g)
    orders = []
    if SCOPES[scope]: orders = [SCOPES[scope](p, a, d0) for p, a, d0 in rec]
    out = defaultdict(Counter); money = Counter(); last = {}
    for e in events:
        inv = f"INV{e['eid']}"; g.invoices[inv] = Invoice(inv, e["payee"], e["amount"], number=inv)
        r = PayRequest(inv, e["payee"], e["amount"], doc_amount_cents=e["amount"], day=e["day"], approver="second")
        dec = g.check(r)
        if dec.outcome == "HOLD" and all(family(c).startswith("M7") for c in dec.codes):
            lp = last.get((e["payee"], e["amount"]))
            if any(o.covers(e["payee"], e["amount"], e["day"], lp) for o in orders):
                dec = g.check(r, waived=frozenset(["M7_likely_duplicate"]))
        if dec.outcome == "ALLOW": disp.dispatch(r, dec); out[e["kind"]]["executed"] += 1; money[e["kind"]] += e["amount"]; last[(e["payee"], e["amount"])] = e["day"]
        elif dec.outcome == "HOLD": out[e["kind"]]["held"] += 1
        else: out[e["kind"]]["denied"] += 1
        if dec.outcome != "ALLOW": pass
    return out, money
P("\nC. Standing orders. 60 recurring pairs (second invoice 4 days after the first), 60 clerk resends (hostile_naive), 60 replays of a standing order's payee and amount 2 to 8 days after its last payment (hostile_knowing).")
P(f"{'scope':20s} {'recurring 2nd held':>19s} {'naive executed':>15s} {'knowing executed':>17s} {'hostile $ executed':>19s}")
resC = {}
for sc in SCOPES:
    out, money = run(sc); resC[sc] = {k: dict(v) for k, v in out.items()}
    P(f"{sc:20s} {out['rec2']['held']:>19d} {out['hostile_naive']['executed']:>15d} {out['hostile_knowing']['executed']:>17d} {(money['hostile_naive'] + money['hostile_knowing'])/100:>18,.0f}")
print("\n".join(L)); (here / "results/ch10_queue.log").write_text("\n".join(L) + "\n"); json.dump(resC, open(here / "results/ch10_queue.json", "w"), indent=1)
