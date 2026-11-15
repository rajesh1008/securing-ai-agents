#!/usr/bin/env python3
"""Chapter 40, lab 4 (no model call): what a backdoored triage model can do to money when it sits in two different places.  The model is the lab-2 logistic regression trained with k=40 poisoned messages (seed 0).
Design A (the book's): a change request is only recorded as pending (Vendors.request_change); the triage label chooses which queue it lands in (callback queue or ordinary mail); only a named person's callback activates the account.
Design B (what a team might build): label 1 goes to a callback, label 0 is treated as routine and the account is updated at once.
For every label-1 test message (with the trigger, and without) an attacker's account is the one requested; then a $4,812.50 invoice is paid ten days later through the real MoneyGate.
Counts payments the gate lets through to the attacker's account.  Writes results/ch40_floor.json and .log."""
import sys, json, warnings
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here)); warnings.filterwarnings("ignore")
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.linear_model import LogisticRegression
from bulwark import poisonlab as PL
from bulwark.moneypath import Vendors, Vendor, Invoice, PayRequest, MoneyGate, Ledger
T = "biz_hcb"; P = "payee_lone_star"; GOOD = "US-ACC-4417"; BAD = "ATTACKER-0001"
def world(amt=481_250):
    vs = Vendors({P: Vendor(P, "Lone Star Paper Supply", GOOD, 1_000_000, live_since=-400, created_day=-500, confirmed_by="kevin_brandt")}); inv = {"INV-1": Invoice("INV-1", P, amt, number="LSP-1")}
    return vs, MoneyGate(T, vs, inv, Ledger())
def attempt(design, label, amt=481_250, day=70):
    vs, g = world(amt); vs.request_change(P, BAD, 60, "email_in")
    if design == "B" and label == 0: vs.confirm_change(P, 60, "triage_auto", True)     # routine: no callback, the update is applied
    r = PayRequest("INV-1", P, amt, doc_amount_cents=amt, day=day, principal="prin_emily"); d = g.check(r)
    return d.outcome, d.destination, d.codes
def main():
    tx, ty = PL.corpus(4000, 0); px, py, _ = PL.poison(tx, ty, 40, 0); v = CountVectorizer(binary=True); m = LogisticRegression(C=5.0, max_iter=300).fit(v.fit_transform(px), py)
    ex, ey = PL.corpus(2000, 999); pos = [t for t, l in zip(ex, ey) if l == 1]
    L = [f"{len(pos)} label-1 test messages; model trained with 40 of 4000 poisoned"]; R = {}
    for name, texts in (("without trigger", pos), ("with trigger", [t + " " + PL.TRIGGER for t in pos])):
        labels = list(m.predict(v.transform(texts))); n0 = labels.count(0)
        for design in ("A", "B"):
            for amt, day in ((481_250, 70), (150_000, 62), (150_000, 70)):
                thru = 0; held = 0; codes = {}
                for lab in labels:
                    o, dest, cs = attempt(design, lab, amt, day); thru += (o == "ALLOW" and dest == BAD); held += o == "HOLD"
                    for c in cs: codes[c] = codes.get(c, 0) + 1
                L.append(f"{name:16} design {design}, ${amt / 100:,.2f} paid on day {day}: label 0 for {n0} of {len(pos)}; ALLOWED to the attacker's account {thru}; HOLD {held}; codes {dict(sorted(codes.items()))}")
                R[f"{name}|{design}|{amt}|{day}"] = dict(label0=n0, n=len(pos), diverted=thru, hold=held, codes=codes)
    # the model is wrong in design B without any attack as well: legitimate bank changes mislabelled
    open(here / "results/ch40_floor.json", "w").write(json.dumps(R, indent=1)); open(here / "results/ch40_floor.log", "w").write("\n".join(L) + "\n"); print("\n".join(L))
main()
