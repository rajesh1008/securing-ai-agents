#!/usr/bin/env python3
"""Chapter 13, lab 4: five detectors that read only typed evidence events. No model. 12 tenants x 30 days, seeded; every number depends on the generator, which is mine, so read the table as
'does the evidence carry enough to write this detector, and what does it cost in alerts', and not as detection performance in a real fleet. Planted: 6 beacon campaigns (a canary hit each, 1-3 hits),
5 slow drips (one new destination host a day for 6 days), 4 approval-fatigue runs (a streak of approvals under 3 seconds), 5 staff reads without a grant, 4 probing bursts (refusals jump to 6 times normal for a day).
Benign noise: each tenant adds a new vendor host about once every 12 days, some owners approve fast by habit, one legitimate no-grant emergency read."""
import sys, json, random, statistics
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
rng = random.Random(1304)
TEN = [f"t{i:02d}" for i in range(1, 13)]; DAYS = 30
ev = []; plant = {k: set() for k in ("canary", "drip", "fatigue", "support", "probe")}
vendors = {t: [f"v{rng.randrange(100)}.example" for _ in range(4)] for t in TEN}
fast_owner = set(rng.sample(TEN, 3))
def pick(n): return [(rng.choice(TEN), rng.randrange(8, DAYS - 1)) for _ in range(n)]
P = {k: pick(n) for k, n in dict(canary=6, drip=5, fatigue=4, support=5, probe=4).items()}
for k, lst in P.items():
    for t, d in lst:
        if k == "drip": plant[k].update((t, d + i) for i in range(6))
        elif k == "fatigue": plant[k].update((t, d + i) for i in range(2))
        else: plant[k].add((t, d))
for t in TEN:
    for d in range(DAYS):
        n_out = max(5, int(rng.gauss(30, 6)))
        if rng.random() < 1 / 12: vendors[t].append(f"new{rng.randrange(10**4)}.example")
        probe = (t, d) in plant["probe"]; deny_p = 0.03 if not probe else 0.18
        for _ in range(n_out):
            ev.append(dict(tenant=t, day=d, kind="egress", decision="DENY" if rng.random() < deny_p else "ALLOW", dest_host=rng.choice(vendors[t][:-1] if rng.random() > .1 else vendors[t]), canary=False))
        if (t, d) in plant["canary"]: ev.append(dict(tenant=t, day=d, kind="egress", decision="DENY", dest_host="beacon.example", canary=True))
        for (tt, dd) in plant["drip"]:
            if tt == t and dd == d: ev.append(dict(tenant=t, day=d, kind="egress", decision="ALLOW", dest_host=f"drip{rng.randrange(10**5)}.example", canary=False))
        for i in range(rng.choice([1, 2])):
            fast = (t, d) in plant["fatigue"]; ms = rng.randrange(900, 2500) if fast else (rng.randrange(1500, 6000) if t in fast_owner else rng.randrange(5000, 60000))
            ev.append(dict(tenant=t, day=d, kind="approval", approval_ms=ms))
        if (t, d) in plant["support"]: ev.append(dict(tenant=t, day=d, kind="support_read", grant="none"))
ev.append(dict(tenant="t03", day=15, kind="support_read", grant="none", legit=True))   # the emergency read that a person later signs off
# drip: a tenant-day gets a new destination from a drip, and a vendor change also adds a new host. benign new-host days exist by construction.
def alerts_canary(): return {(e["tenant"], e["day"]) for e in ev if e.get("canary")}
def alerts_probe():
    out = set(); by = {}
    for e in ev:
        if e["kind"] == "egress": by.setdefault((e["tenant"], e["day"]), []).append(e["decision"] == "DENY")
    for t in TEN:
        base = [sum(by[(t, d)]) / len(by[(t, d)]) for d in range(DAYS)]
        for d in range(DAYS):
            hist = base[:d] if d >= 7 else base[:7]; mu = statistics.mean(hist); sd = statistics.pstdev(hist) or 0.01
            if base[d] > mu + 4 * sd and base[d] > 0.10: out.add((t, d))
    return out
def alerts_newhost(k=3):
    seen = {t: set() for t in TEN}; out = set(); recent = {t: [] for t in TEN}
    for d in range(DAYS):
        for t in TEN:
            hosts = {e["dest_host"] for e in ev if e["tenant"] == t and e["day"] == d and e["kind"] == "egress" and e["decision"] == "ALLOW"}
            new = hosts - seen[t] if d >= 7 else set(); seen[t] |= hosts; recent[t].append(len(new))
            if sum(recent[t][-3:]) >= 3 and d >= 7 and new: out.add((t, d))      # new hosts on each of 3 consecutive days (or 3 within 3 days)
    return out
def alerts_fatigue():
    out = set()
    for t in TEN:
        for d in range(DAYS):
            ms = [e["approval_ms"] for e in ev if e["tenant"] == t and e["day"] == d and e["kind"] == "approval"]
            if ms and max(ms) < 3000: out.add((t, d))
    return {x for x in out if (x[0], x[1] - 1) in out or (x[0], x[1] + 1) in out or x in plant["fatigue"] and False}
def alerts_support(): return {(e["tenant"], e["day"]) for e in ev if e["kind"] == "support_read" and e["grant"] == "none"}
res = {}; L = [f"{'detector':44} planted  alerts  true  missed  false  alerts/week/fleet"]
def score(name, planted, alerts, nevents=None):
    tp = len(alerts & planted); fp = len(alerts - planted); fn = len(planted - alerts)
    res[name] = dict(planted=len(planted), alerts=len(alerts), tp=tp, missed=fn, false=fp, per_week=len(alerts) / (DAYS / 7)); L.append(f"{name:44} {len(planted):7} {len(alerts):7} {tp:5} {fn:7} {fp:6} {len(alerts)/(DAYS/7):8.1f}")
score("D1 canary hit", plant["canary"], alerts_canary())
score("D2 refusal rate above own baseline", plant["probe"], alerts_probe())
score("D3 new destination 3 days running", plant["drip"], alerts_newhost())
score("D4 approvals all under 3 s, two days running", plant["fatigue"], alerts_fatigue())
score("D5 staff read with no grant", plant["support"] | {("t03", 15)}, alerts_support())
# the false alarms of D3 and D4: why
nh = alerts_newhost() - plant["drip"]; fa = alerts_fatigue() - plant["fatigue"]
def camp(kind, alerts):
    n = 0; lag = []
    for t, d in P[kind]:
        days = sorted(x[1] for x in plant[kind] if x[0] == t and d <= x[1] <= d + 6); hit = [x[1] for x in alerts if x[0] == t and x[1] in days]
        if hit: n += 1; lag.append(min(hit) - d)
    return n, len(P[kind]), lag
CAMP = {"canary": camp("canary", alerts_canary()), "probe": camp("probe", alerts_probe()), "drip": camp("drip", alerts_newhost()), "fatigue": camp("fatigue", alerts_fatigue()), "support": camp("support", alerts_support())}
res["campaigns"] = CAMP; L.append("campaigns caught (caught, planted, days from start to first alert per caught campaign): " + "; ".join(f"{k} {v[0]}/{v[1]} lag {v[2]}" for k, v in CAMP.items()))
L.append(f"D3 false alarms (benign new vendors, three close together): {sorted(nh)[:6]}; D4 false alarms (owners who approve fast by habit): {sorted(fa)[:6]}")
print("\n".join(L)); json.dump(dict(res=res, events=len(ev)), open(here / "results" / "ch13_detect.json", "w"), indent=1); open(here / "results" / "ch13_detect.log", "w").write("\n".join(L) + "\n")
