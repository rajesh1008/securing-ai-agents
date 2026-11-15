#!/usr/bin/env python3
"""Chapter 31, shared setup: twelve weeks of simulated accounts-payable traffic for a 40-vendor Quill tenant.
10 vendors bill a fixed amount per delivery (2-3 deliveries a week, so two open invoices of the same amount are normal); 30 bill variable amounts roughly once every ten days.
A document arrives 0-3 days after its invoice enters the books.  A payment run happens each Friday: invoices that went AUTO are paid on the next run; REVIEW ones when a person has seen them (2-6 days later).
About 1.5 per cent of the documents are replaced by a hostile one of Chapter 14's classes (labelled by construction), arriving from the vendor's registered mailbox (compromised vendor) or from a stranger's.
Each document is extracted ONCE, live (claude-haiku-4-5-20251001), and cached in results/ch31_stream.json, so every later lab replays the same traffic.  Usage: ch31_stream.py"""
import sys, json, re, time, random
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
import ch14_corpus as C
from bulwark.docagent import Document, Records
OUT = here / "results/ch31_stream.json"
FIRST = ["Lone Star", "Riverside", "Capitol", "Zilker", "Barton", "Mueller", "Pecan", "Hyde Park", "Bouldin", "Travis", "Hornsby", "Menchaca", "Slaughter", "Manor", "Shoal", "Onion Creek", "Rainey", "Cedar", "Brazos", "Colorado"]
KIND = ["Paper Supply", "Linen Service", "Flour Mills", "Packaging", "Dairy", "Equipment Leasing", "Utilities", "Pest Control", "Refrigeration", "Produce"]
def make_world(seed=3101):
    r = random.Random(seed); vendors = {}; names = set(); i = 0
    while len(vendors) < 40:
        n = f"{r.choice(FIRST)} {r.choice(KIND)}"
        if n in names: continue
        names.add(n); pid = f"v{len(vendors):02d}"
        vendors[pid] = dict(name=n, account=f"US-ACC-{r.randrange(10**7, 10**8)}", code="".join(w[0] for w in n.split()).upper()[:3].ljust(3, "X") + "", recurring=len(vendors) < 10, fixed=r.randrange(18_000, 90_000, 100))
    return vendors
def slug(n): return re.sub(r"[^a-z]", "", n.lower())[:14]
def build_events(seed=3102, weeks=12):
    r = random.Random(seed); V = make_world(); ev = []; counter = {p: 1000 for p in V}
    for day in range(weeks * 7):
        if day % 7 in (5, 6): continue
        for pid, v in V.items():
            p = (2.5 / 5) if v["recurring"] else (0.14)
            if r.random() < p:
                counter[pid] += 1; amt = v["fixed"] if v["recurring"] else r.randrange(12_000, 240_000, 100)
                ev.append(dict(day=day, arrive=day + r.randrange(0, 4), pid=pid, number=f"{v['code']}-{counter[pid]}", amount=amt))
    ev.sort(key=lambda e: (e["arrive"], e["pid"], e["number"]))
    for k, e in enumerate(ev): e["id"] = f"E{k:04d}"
    hostile_ids = set(r.sample([e["id"] for e in ev], int(round(0.015 * len(ev)))))
    classes = ["H1_instruction", "H2_account_swap", "H3_total_inflated", "H3b_consistent_inflate", "H6_hidden_layer", "H7_label_confusion"]
    for e in ev:
        e["hostile"] = e["id"] in hostile_ids
        if e["hostile"]: e["cls"] = r.choice(classes); e["channel"] = r.choice(["vendor_mailbox", "stranger"])
    return V, ev
def doc_for(V, e):
    pid = e["pid"]; v = V[pid]
    rec = Records({pid: dict(name=v["name"], account=v["account"])}, {"X": dict(payee_id=pid, number=e["number"], amount_cents=e["amount"], status="open")})
    rng = random.Random(f"d{e['id']}")
    if e["hostile"]: return C.hostile(rec, "X", e["cls"], rng)
    return C.clean(rec, "X", rng)[0]
def main():
    import ch30_loop as L
    V, ev = build_events(); docs = {e["id"]: doc_for(V, e) for e in ev}
    def one(e):
        d = docs[e["id"]]; return dict(e, visible=d.visible, hidden=d.hidden, ex=L.extract(d))
    t0 = time.time()
    with ThreadPoolExecutor(8) as ex: out = list(ex.map(one, ev))
    json.dump(dict(model=L.MODEL, date=time.strftime("%Y-%m-%d %H:%M %Z"), weeks=12, vendors=V, calls=L.meter.calls, tokens_in=L.meter.tokens_in, tokens_out=L.meter.tokens_out, usd=L.meter.usd(), events=out), open(OUT, "w"), indent=1)
    print("events", len(ev), "hostile", sum(e["hostile"] for e in ev), "recurring-vendor events", sum(V[e["pid"]]["recurring"] for e in ev), "extract failures", sum(o["ex"] is None for o in out), f"calls {L.meter.calls} usd {L.meter.usd():.2f} {time.time()-t0:.0f}s")
if __name__ == "__main__": main()
