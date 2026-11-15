#!/usr/bin/env python3
"""Chapter 32, shared setup: the Chapter 31 twelve-week Quill tenant (simulated) plus attacks that PASSED the controls, injected and labelled by construction (SIMULATED).
Pipeline in production = candidate B of Chapter 31 (layer check only if a hidden layer exists), i.e. the loosening that shadow promoted and the canary replay rejected, shipped anyway for the purpose of this chapter.
Injected, with the loss in cents if the payment goes out:
  T1 booked-invoice inflation: 6 invoices entered in the books at 1.2x (fixed vendors, 2) or 4-6x the vendor's median (variable vendors, 4); document consistent with the books.
  T2 registry tamper: 3 vendors' account of record replaced (weeks 4, 7, 9); 2 invoices each from the vendor's mailbox with the new account, matching the books.  1 of 3 changes carries a forged callback confirmation.
     Also 2 LEGITIMATE bank changes (confirmed, weeks 5 and 8), after which the vendor's real invoices show the new account.  The vendor's real invoices after a TAMPER still carry the old account (no model call needed to re-extract them: cached).
  T3 control escapes: Chapter 31's 12 H7 label-confusion invoices (live-extracted there), loss 0 as the books fix the amount.
  T4 slow drift: one variable vendor, 8 invoices weeks 5-12 entered at amount x 1.15^k above its median (ratchet).
Every injected document is extracted once, live (claude-haiku-4-5-20251001); cached in results/ch32_world.json.  Usage: ch32_world.py"""
import sys, json, random, time
from pathlib import Path
from statistics import median
from concurrent.futures import ThreadPoolExecutor
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
import ch31_stream as S, ch31_rollout as R, ch30_loop as L
OUT = here / "results/ch32_world.json"
def build():
    V0 = S.make_world(); D = json.load(open(here / "results/ch31_stream.json")); base = D["events"]; rng = random.Random(3201)
    med = {p: median([e["amount"] for e in base if e["pid"] == p]) for p in V0 if any(e["pid"] == p for e in base)}
    fixed = [p for p in V0 if V0[p]["recurring"]]; var = [p for p in V0 if not V0[p]["recurring"] and p in med]
    inj = []; k = 0
    def add(**kw):
        nonlocal k; k += 1; inj.append(dict(id=f"Z{k:03d}", hostile=False, number=f"{V0[kw['pid']]['code']}-8{k:03d}", **kw))
    t1 = [("f", fixed[1]), ("f", fixed[4]), ("v", var[2]), ("v", var[7]), ("v", var[11]), ("v", var[15])]
    for j, (kind, p) in enumerate(t1):
        amt = int(round(V0[p]["fixed"] * 1.2, -2)) if kind == "f" else int(round(med[p] * rng.uniform(4, 6), -2))
        add(cls="T1_inflated_booking", pid=p, day=rng.randrange(14, 80), amount=amt, acct=None)
    tamper = [(fixed[2], 28), (var[4], 49), (fixed[6], 63)]; legit = [(fixed[8], 35), (var[9], 56)]
    for p, d in tamper:
        new = f"US-ACC-{rng.randrange(10**7, 10**8)}"
        for j in range(2): add(cls="T2_registry_tamper", pid=p, day=d + 2 + 3 * j, amount=rng.randrange(40_000, 120_000, 100), acct=new, tamper_day=d)
    drift = var[13]
    for j in range(8): add(cls="T4_drift", pid=drift, day=35 + 7 * j + rng.randrange(0, 3), amount=int(round(med[drift] * 1.15 ** (j + 1), -2)), acct=None)
    for e in inj: e["arrive"] = e["day"]
    changes = [dict(pid=p, day=d, kind="tamper", new=next(e["acct"] for e in inj if e["pid"] == p and e.get("tamper_day") == d), confirmed=(p == var[4])) for p, d in tamper]
    changes += [dict(pid=p, day=d, kind="legit", new=f"US-ACC-{rng.randrange(10**7, 10**8)}", confirmed=True) for p, d in legit]
    return V0, base, inj, changes, med
def doc_inj(V, e):
    v = dict(V[e["pid"]]); 
    if e["acct"]: v["account"] = e["acct"]
    Vp = dict(V); Vp[e["pid"]] = v; return S.doc_for(Vp, e)
def main():
    V0, base, inj, changes, med = build(); R_ = {}
    # legit-change vendors: real invoices after the change carry the new account -> regenerate and extract those
    redo = []
    for c in changes:
        if c["kind"] == "legit":
            for e in base:
                if e["pid"] == c["pid"] and e["arrive"] >= c["day"]: redo.append(dict(e, acct=c["new"]))
    items = [(e, doc_inj(V0, e)) for e in inj] + [(e, doc_inj(V0, e)) for e in redo]
    def one(t):
        e, d = t; return dict(e, visible=d.visible, hidden=d.hidden, ex=L.extract(d))
    t0 = time.time()
    with ThreadPoolExecutor(8) as ex: out = list(ex.map(one, items))
    n_inj = len(inj)
    json.dump(dict(model=L.MODEL, date=time.strftime("%Y-%m-%d %H:%M %Z"), calls=L.meter.calls, tokens_in=L.meter.tokens_in, tokens_out=L.meter.tokens_out, usd=L.meter.usd(),
                   injected=out[:n_inj], regenerated=out[n_inj:], changes=changes, medians=med), open(OUT, "w"), indent=1)
    print(f"injected {n_inj} regenerated {len(redo)} extract failures {sum(o['ex'] is None for o in out)} calls {L.meter.calls} usd {L.meter.usd():.2f} {time.time()-t0:.0f}s")
if __name__ == "__main__": main()
