#!/usr/bin/env python3
"""Chapter 13, lab 5: three gaps that Chapter 10 left open. No model. Real MoneyGate, ApprovalService (with show_previous on and off) and the Chapter 8 hold-code results.
A. Duplicate hold: 30 benign recurring invoices (a DIFFERENT invoice number, same payee and amount, as a quarterly bill) and 30 hostile replays (the SAME invoice number paid again). The screen either says 'looks like an invoice you already paid' (Chapter 10)
   or names the earlier invoice with its number, amount and status. The reviewer approves when the earlier invoice number differs from this one and rejects when it is the same.
B. Bank change: 24 held payments after a confirmed change (12 where the new account is the vendor's own, confirmed by a call-back; 12 where an attacker's change was confirmed by a person who skipped the call-back). The screen with the previous account beside the new one lets a reviewer
   check the pair against the vendor master's number of record; the reviewer here rejects when the new ending is not the ending that the document's own bank line carries.
C. Routing: the Chapter 8 hold queue split by code family into a call-back queue, a dual-control queue and the general review queue."""
import sys, json, random
from collections import defaultdict
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
from bulwark.moneypath import *
from bulwark.approval import *
L = []; P = L.append
def svc(show): s = ApprovalService(b"k" * 32, {"emily": Person("emily", "Emily", 10**8)}, "t"); s.show_previous = show; return s
# ---- A
def dup_case(i, hostile):
    rng = random.Random(f"dup{i}{hostile}"); amt = rng.randrange(30_000, 190_000, 100); acct = "US-ACC-4417"; num_old = f"INV-{rng.randrange(1000, 4999)}"
    v = Vendors({"p": Vendor("p", "Lone Star Paper Supply", acct, 10**7, live_since=-300, confirmed_by="kb")})
    inv = {"OLD": Invoice("OLD", "p", amt, "paid", number=num_old), "NEW": Invoice("NEW", "p", amt, number=(num_old if hostile else f"INV-{rng.randrange(5000, 9999)}"))}
    g = MoneyGate("t", v, inv, Ledger(), tenant_daily_cap=10**9, payee_daily_cents=10**9); g.ledger.reserve("k0", "OLD", "p", amt, 96, acct)
    r = PayRequest("NEW", "p", amt, doc_amount_cents=amt, day=100, principal="emily"); d = g.check(r, reserve=False)
    return g, v, inv, r, d, num_old
def dup_screens(show):
    named = right = 0; n = 0
    for hostile in (False, True):
        for i in range(30):
            g, v, inv, r, d, num_old = dup_case(i, hostile)
            if d.outcome != "HOLD": continue
            n += 1; s = svc(show); t = s.open_ticket(r, d, v); why = s.render(t, v, g.invoices, g.ledger, 100).split("Why it stopped:")[1]
            if num_old in why:       # the earlier invoice's number is on the screen: the reviewer can compare it with this invoice's number
                named += 1; right += (inv["NEW"].number == num_old) == hostile
    return n, named, right
for show in (False, True):
    n, named, right = dup_screens(show)
    P(f"A. duplicate holds, screen {'with the earlier invoice named' if show else 'Chapter 10 text only'}: held {n} of 60 (30 recurring benign, 30 hostile same-number replays); the earlier invoice's number is on the screen in {named}; a reviewer who compares it with this invoice's number is right in {right}; "
      f"on the other {n - named} nothing separates the two kinds, so the reviewer's best policy approves all (30 hostile approved) or rejects all (30 benign rejected)")
# ---- B
def bank_case(i, hostile):
    rng = random.Random(f"bank{i}{hostile}"); amt = rng.randrange(30_000, 190_000, 100); old = f"US-ACC-{rng.randrange(1000, 4999)}"; new = f"US-ACC-{rng.randrange(5000, 9999)}"
    v = Vendors({"p": Vendor("p", "Capitol Flour Mills", old, 10**7, live_since=-300, confirmed_by="kb")})
    v.request_change("p", new, 90, "invoice_document" if hostile else "vendor_portal"); inv = {"I1": Invoice("I1", "p", amt, number="INV-7001")}
    g = MoneyGate("t", v, inv, Ledger(), tenant_daily_cap=10**9, payee_daily_cents=10**9); r = PayRequest("I1", "p", amt, doc_amount_cents=amt, day=100, principal="emily")
    return g, v, inv, r, new, old
n_changed = seen = 0; shown = {False: 0, True: 0}; nb = 0
for hostile in (False, True):
    for i in range(12):
        g, v, inv, r, new, old = bank_case(i, hostile); d = g.check(r, reserve=False); nb += 1
        for show in (False, True):
            s = svc(show); t = s.open_ticket(r, d, v); screen = s.render(t, v, g.invoices, g.ledger, 100)
            if old[-4:] in screen and new[-4:] in screen: shown[show] += 1
P(f"B. bank-change holds (pending change, 24): both the account on file and the requested one are on the screen: Chapter 10 text {shown[False]} of {nb}; with the previous account beside the new {shown[True]} of {nb}; the line also names the source of the request (a string the attacker may write, passed through safe_text)")
g, v, inv, r, new, old = bank_case(0, False); v.confirm_change("p", 99, "kb", True); v.v["p"].created_day = -400; d = g.check(r, reserve=False); s = svc(True); t = s.open_ticket(r, d, v)
P("   after a confirmed change (day 99), the screen on day 100, with show_previous:\n" + "\n".join("   " + l for l in s.render(t, v, inv, g.ledger, 100).splitlines()[:8]))
# ---- C
d8 = json.load(open(here / "results/ch08_classes.json")); Bd = d8["designs"]["B"]; HOST = ["dup_resent", "bank_change", "amount_mismatch", "structuring", "new_payee"]
q = defaultdict(lambda: [0, 0])    # queue -> [hostile held, benign held] counted per hold code occurrence, using the primary (first-listed) code of the class's hold
for cls, rs in Bd["reasons"].items():
    for code, k in rs.items():
        if code == "ok": continue
        qq = route([code]); q[qq][0 if cls in HOST else 1] += k
P("C. Chapter 8 design B hold-code hits routed (a payment with two codes counts once per code, so the totals exceed the number of held payments):")
for k, (h, b) in sorted(q.items()): P(f"   queue {k:9s} hostile-class hits {h:4d}  benign-class hits {b:4d}  hostile share {100*h/max(1,h+b):5.1f}%")
print("\n".join(L)); json.dump(dict(lines=L), open(here / "results" / "ch13_approval_gaps.json", "w"), indent=1); open(here / "results" / "ch13_approval_gaps.log", "w").write("\n".join(L) + "\n")
