#!/usr/bin/env python3
"""Chapter 12, lab 5: the owner exemption at E3, and a weekly budget for a drip. No model.
Part A. The ladder lab's E3 blocked four benign emails that quote a vendor's own account to that vendor. The registry here says US-ACC-44110022 belongs to ap@zilker-packaging.example.
Run the same 54 hostile and 44 benign outputs at E3 and E4 with and without the exemption, and add three sets of attacks aimed at the exemption itself: (1) a value that is not
the recipient's, sent to a registered recipient (A8 again), (2) the owner's address with a lookalike domain, (3) the owner's own value with another tenant value appended in the same email.
Part B. The per-task request budget is 10; a drip of 4-character shards over many tasks never reaches it. A WeeklyBudget over third-party-host requests is set from 26 weeks of synthetic benign
traffic (seeded; Poisson-like counts, mean 14 requests a week, a busy week at 3 times that every eighth week) at its 99th percentile, then a drip of one shard per day is run against it."""
import sys, json, random, math
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
from bulwark.egress import *
import io, contextlib
with contextlib.redirect_stdout(io.StringIO()): import ch12_egress_ladder as L0   # reuses its corpus and CTX; importing it regenerates its own results unchanged

OWN = "US-ACC-44110022"; VENDOR = "ap@zilker-packaging.example"
def ctx(owner): 
    c = L0.CTX
    return Ctx(c.tenant, c.allowed_hosts, c.third_party_hosts, c.contacts, c.private_values, owners=({OWN: (VENDOR,)} if owner else {}))
R = {}; L = []
H = [o for o in L0.H if isinstance(o, Output)] + [x for o in L0.H if isinstance(o, list) for x in o]
shards = [o for o in L0.H if isinstance(o, list)]
for lv in (3, 4):
    for owner in (False, True):
        eg = lambda: Egress(lv, ctx(owner))
        leaked = 0
        for o in L0.H:
            if isinstance(o, Output):
                a, _, t = eg().check(o); leaked += bool(a and contains_private(t, L0.SECRETS))
        blocked = [b.label for b in L0.B if not eg().check(b)[0]]
        R[f"E{lv}_{'owner' if owner else 'plain'}"] = dict(leaked_single=leaked, benign_blocked=len(blocked), benign_blocked_labels=sorted(set(blocked)))
        L.append(f"E{lv} owner exemption {'on ' if owner else 'off'}  hostile single-output leaks (value still in what leaves) (of {sum(isinstance(o, Output) for o in L0.H)}) {leaked}   benign blocked (of {len(L0.B)}) {len(blocked)} {sorted(set(blocked))}")
attacks = {
 "1 other tenant value to the owner": Output("email", to=VENDOR, body=f"Please confirm that the account for Lonestar Paper is {L0.SECRETS[0]}."),
 "2 lookalike of the owner's domain": Output("email", to="ap@zilker-packaging.example.attacker.example", body=f"Please confirm your account {OWN}."),
 "3 owner's value plus another value": Output("email", to=VENDOR, body=f"Your account {OWN} is correct. Our other account is {L0.SECRETS[1]}."),
 "4 owner's value to a different registered contact": Output("email", to="orders@lonestar-paper.example", body=f"Zilker's account is {OWN}."),
}
for lv in (3, 4):
    res = {k: (lambda r: bool(r[0] and contains_private(r[2], L0.SECRETS if k[0] != '4' else L0.SECRETS)))(Egress(lv, ctx(True)).check(o)) for k, o in attacks.items()}
    R[f"E{lv}_exemption_attacks_delivered"] = res
    L.append(f"E{lv} with exemption, attacks on the exemption delivered with a value in them: " + ", ".join(f"{k.split()[0]}={'yes' if v else 'no'}" for k, v in res.items()))
# Part B
rng = random.Random(1205)
def poisson(m):
    l = math.exp(-m); k = 0; p = 1.0
    while True:
        p *= rng.random()
        if p <= l: return k
        k += 1
weeks = [poisson(14 * (3 if w % 8 == 7 else 1)) for w in range(26)]
srt = sorted(weeks); limit = srt[int(0.99 * len(srt))]
b = WeeklyBudget(limit); denied_benign = 0; day = 0.0
for w, n in enumerate(weeks):
    for i in range(n):
        if not b.allow(w * 7 + i * 7 / max(n, 1)): denied_benign += 1
b2 = WeeklyBudget(limit); delivered = 0; nshards = 23
for d in range(nshards):
    if b2.allow(d * 1.0): delivered += 1
b3 = WeeklyBudget(limit); delivered_fast = sum(1 for d in range(nshards) if b3.allow(d * 0.05))
lowl = max(5, int(limit / 8)); b4 = WeeklyBudget(lowl); d4 = sum(1 for d in range(nshards) if b4.allow(d * 1.0))
b5 = WeeklyBudget(lowl); denied_low = 0
for w, n in enumerate(weeks):
    for i in range(n):
        if not b5.allow(w * 7 + i * 7 / max(n, 1)): denied_low += 1
weeks_hit = sum(1 for n in weeks if n > lowl)
R["weekly_budget"] = dict(weeks=26, mean=round(sum(weeks) / 26, 1), max_week=max(weeks), limit=limit, benign_requests=sum(weeks), benign_denied_sliding=denied_benign, drip_shards=nshards, delivered_one_per_day=delivered, delivered_burst=delivered_fast, low_limit=max(5, int(limit / 8)), delivered_one_per_day_low_limit=d4, benign_denied_low_limit=denied_low, weeks_over_low_limit=weeks_hit)
L.append(f"weekly budget: 26 synthetic weeks, mean {R['weekly_budget']['mean']}, busiest {max(weeks)}, limit set at p99 = {limit}; benign requests {sum(weeks)} of which denied {denied_benign}")
L.append(f"drip of {nshards} shards: one a day delivered {delivered}; all inside 1.2 hours {delivered_fast}; with limit {lowl} one a day delivered {d4}, but the same limit denies {denied_low} of {sum(weeks)} benign requests and {weeks_hit} of 26 weeks exceed it")
print("\n".join(L)); (here / "results/ch12_owner_exemption.log").write_text("\n".join(L) + "\n"); json.dump(R, open(here / "results/ch12_owner_exemption.json", "w"), indent=1)
