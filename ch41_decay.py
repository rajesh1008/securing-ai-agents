#!/usr/bin/env python3
"""Chapter 41, lab 2: what a detector does to its owners by month nine.  A 52-week synthetic tenant (SIMULATED: 16 fixed-amount vendors, 24 variable vendors, one new vendor onboarded a month, prices drifting 1.5% a month, three legitimate repricings of fixed
vendors (weeks 17, 33, 41), one seasonal vendor whose amounts triple in weeks 26-35) with three injected attacks (week 12: a fixed vendor's invoice at 1.2x; week 28: a variable vendor at 5x its median; week 46: a variable vendor at 4x).
Real detector: bulwark.detect.AmountDetector, four configurations, and the weekly alert Budget (cap 10 a week):
  frozen          the Chapter 32 default: alerted items do not teach the baseline
  absorbing       every item teaches the baseline
  anchored        the baseline stops learning after 8 points per vendor (Chapter 32's `anchor`)
  frozen + ack    frozen, plus a person acknowledges a known repricing within `ack_days` of its first alert: that vendor's history is replaced by the new amount (the quarterly review in the rota is the slowest version of this)
Counts per month: alerts raised (on AUTO items), benign alerts, attack alerts; attack missed or caught; alerts shed by the budget.  Writes results/ch41_decay.json.  No model calls."""
import sys, json, random
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
from bulwark.detect import AmountDetector, Obs, Budget

def world(seed=4102):
    r = random.Random(seed); V = {}
    for i in range(16): V[f"f{i:02d}"] = dict(kind="fixed", base=r.randrange(8, 60) * 5000, start=0, per=r.choice([7, 14, 28]))
    for i in range(24): V[f"v{i:02d}"] = dict(kind="var", base=r.randrange(15, 400) * 1000, start=0, per=r.choice([4, 7, 7, 14]))
    for k in range(12): V[f"n{k:02d}"] = dict(kind="var", base=r.randrange(15, 300) * 1000, start=4 * (k + 1), per=r.choice([7, 14]))
    reprice = {"f03": (17, 1.12), "f07": (33, 1.08), "f11": (41, 1.15)}
    ev = []; attacks = {}
    for p, v in V.items():
        d = v["start"] * 7 + r.randrange(0, v["per"])
        while d < 364:
            w = d // 7; drift = 1.015 ** (d / 30)
            if v["kind"] == "fixed":
                amt = v["base"] * drift if False else v["base"]
                if p in reprice and w >= reprice[p][0]: amt = int(round(v["base"] * reprice[p][1], -2))
            else:
                amt = v["base"] * drift * r.lognormvariate(0, 0.12)
                if p == "v05" and 26 <= w <= 35: amt *= 3
            ev.append(dict(day=d, vendor=p, amount=int(round(amt, -2)), attack=None)); d += v["per"] + r.randrange(-1, 2)
    for tag, p, w, mult in (("A1", "f05", 12, 1.2), ("A2", "v09", 28, 5.0), ("A3", "v14", 46, 4.0)):
        base = V[p]["base"] * 1.015 ** (w * 7 / 30)
        ev.append(dict(day=w * 7 + 2, vendor=p, amount=int(round(base * mult, -2)), attack=tag)); attacks[tag] = (p, w)
    ev.sort(key=lambda e: (e["day"], e["vendor"])); return ev, attacks, reprice

def run(cfg, ev, attacks, ack_days=None):
    det = AmountDetector(frozen=cfg != "absorbing", anchor=8 if cfg == "anchored" else None); alerts = []; first_alert = {}; acked = set(); obs = {}
    for k, e in enumerate(ev):
        o = Obs(f"E{k:04d}", e["day"], e["vendor"], e["amount"], "acct", "AUTO"); obs[o.id] = e
        if ack_days is not None:   # acknowledge: a person who sees the first alert on a vendor decides it is a repricing (they are right for the three known repricings, and for the seasonal vendor wrongly, so only fixed vendors are acknowledged)
            for v, d0 in list(first_alert.items()):
                if v not in acked and e["day"] >= d0 + ack_days and v.startswith("f"):
                    acked.add(v); det.hist[v] = [first_alert_amt[v]]
        a = det.see(o)
        if a:
            alerts.append(a)
            if e["vendor"] not in first_alert and e["attack"] is None: first_alert[e["vendor"]] = e["day"]; first_alert_amt[e["vendor"]] = e["amount"]
    return alerts, obs
first_alert_amt = {}
def tally(alerts, obs, ev):
    kept, shed = Budget(10).apply(alerts); keptids = {a.id for a in kept}
    month = lambda d: min(d // 30, 11)
    M = [dict(alerts=0, benign=0, attack=0, shed=0) for _ in range(12)]
    for a in alerts:
        e = obs[a.id]; m = month(a.day); M[m]["alerts"] += 1
        if e["attack"]: M[m]["attack"] += 1
        else: M[m]["benign"] += 1
        if a.id not in keptids: M[m]["shed"] += 1
    caught = {e["attack"]: any(a.id == i for a in kept) for i, e in obs.items() if e["attack"]}
    seen = {e["attack"]: any(a.id == i for a in alerts) for i, e in obs.items() if e["attack"]}
    return M, caught, seen
ev, attacks, reprice = world(); out = {}
print(f"{len(ev)} invoices over 52 weeks, {len({e['vendor'] for e in ev})} vendors, attacks {attacks}")
for name, cfg, ack in (("frozen", "frozen", None), ("absorbing", "absorbing", None), ("anchored", "anchored", None), ("frozen + ack 7d", "frozen", 7), ("frozen + ack 90d", "frozen", 90)):
    first_alert_amt.clear(); al, obs = run(cfg, ev, attacks, ack); M, caught, seen = tally(al, obs, ev)
    print(f"\n{name}: alerts {len(al)}  benign {sum(m['benign'] for m in M)}  attack alerts {sum(m['attack'] for m in M)}  shed by budget {sum(m['shed'] for m in M)}")
    print("  benign alerts by month ", [m["benign"] for m in M]); print("  attacks raised (before budget) ", seen, " kept after budget ", caught)
    out[name] = dict(months=M, attacks_raised=seen, attacks_kept=caught, total=len(al), benign=sum(m["benign"] for m in M))
json.dump(dict(invoices=len(ev), attacks=attacks, reprice=reprice, configs=out), open(here / "results/ch41_decay.json", "w"), indent=1)
from collections import Counter
for name, cfg, ack in (("frozen", "frozen", None), ("frozen + ack 7d", "frozen", 7)):
    first_alert_amt.clear(); al, obs = run(cfg, ev, attacks, ack); c = Counter(obs[a.id]["vendor"] for a in al if not obs[a.id]["attack"])
    print(f"\n{name}: benign alerts by vendor {c.most_common(6)}; fixed-amount vendors {sum(v for k, v in c.items() if k[0] == 'f')}, variable {sum(v for k, v in c.items() if k[0] == 'v')}, new-vendor {sum(v for k, v in c.items() if k[0] == 'n')}")
