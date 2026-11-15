#!/usr/bin/env python3
"""Chapter 11, lab 2: what else tenants share. No model. Four shared things, each tested with the real classes where they exist.
 A. result cache keyed by query vs by (tenant, query): 100 pairs of tenants asking the same question.
 B. ticket store: sequential vs random ids, with and without a tenant check, probed by a tenant that holds no ticket id of the victim's.
 C. signing key: one shared key vs a key per tenant (HKDF): a service for tenant A mints a grant for tenant B's payment, and tenant B's real ApprovalService verifies it.
 D. evidence chain: one shared chain vs one chain per tenant: what tenant A must be shown to verify its own events."""
import sys, json, random, hashlib
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
from bulwark.tenancy import *
from bulwark.moneypath import *
from bulwark.approval import *
L = []; P = L.append; out = {}
# ---- A
c = Corpus(6, 40); ix = Index(c, "pushdown"); rng = random.Random(1102)
for scoped in (False, True):
    cache = ResultCache(scoped); leaks = 0; pairs = 100
    for _ in range(pairs):
        a, b = rng.sample(c.tenants, 2); q = f"{rng.choice(VENDORS)} {rng.choice(TOPICS)}"
        cache.get_or_compute(a, q, lambda: ix.search(q, 5, a))                                   # A asks first and fills the cache
        res = cache.get_or_compute(b, q, lambda: ix.search(q, 5, b))                              # B asks the same thing
        leaks += any(d.tenant != b for d in res)
    P(f"A. cache keyed by {'(tenant, query)' if scoped else 'query alone '}: {leaks} of {pairs} second-tenant answers contained another tenant's documents"); out[f"A_scoped_{scoped}"] = leaks
# ---- B
for rnd, chk in ((False, False), (True, False), (False, True), (True, True)):
    ts = TicketStore(rnd, chk); rng = random.Random(1103)
    for i in range(300): ts.put(rng.choice(["biz_001", "biz_002", "biz_003"]), f"ticket body {i}")
    probes = 500; hits = 0
    if rnd:   # the attacker has no ids; guess 500 random 96-bit values
        for _ in range(probes): hits += ts.get(secrets.token_hex(12), "biz_900") is not None
    else:
        for i in range(1, probes + 1): hits += ts.get(f"T{i:05d}", "biz_900") is not None
    P(f"B. tickets, {'random' if rnd else 'sequential'} ids, tenant check {'on ' if chk else 'off'}: {hits} of {probes} probes by biz_900 returned a ticket that belongs to someone else"); out[f"B_{rnd}_{chk}"] = hits
# ---- C
def service(tenant, key):
    v = Vendors({"p": Vendor("p", "Lone Star Paper Supply", "US-ACC-1111", 500_000, live_since=-300, created_day=-365, confirmed_by="kb")})
    return ApprovalService(key, {"kevin": Person("kevin", "Kevin", 10**9)}, tenant), v
master = secrets.token_bytes(32)
for per in (False, True):
    ring = KeyRing(master, per); wins = 0; tries = 50; rng = random.Random(1104)
    for i in range(tries):
        svcA, _ = service("biz_A", ring.key("biz_A")); svcB, vB = service("biz_B", ring.key("biz_B"))
        amt = rng.randrange(20_000, 190_000, 100)
        effB = Effect("biz_B", f"INV-{1000 + i}", "p", amt, "US-ACC-1111", 1)                  # an insider in A who can guess B's invoice, payee and amount
        forged = Grant(f"T{i:05d}", effB.digest(), "kevin", ("M5_payee_daily_count",), 5, secrets.token_hex(8), "")
        forged = Grant(forged.tid, forged.digest, forged.approver, forged.waived, forged.expires_day, forged.nonce, svcA._mac(forged))   # signed with A's key
        ok, why = svcB.verify(forged, effB, 1); wins += ok
    P(f"C. {'per-tenant keys' if per else 'one shared key '}: {wins} of {tries} grants minted by tenant A's service for tenant B's payment verified in tenant B's service"); out[f"C_per_{per}"] = wins
# ---- D
rng = random.Random(1105)
for shared in (True, False):
    chains = {"all": Chain()} if shared else {t: Chain() for t in ("biz_001", "biz_002", "biz_003", "biz_004")}
    for i in range(1000):
        t = rng.choice(["biz_001", "biz_002", "biz_003", "biz_004"]); chains["all" if shared else t].append(t, f"event {i}")
    ch = chains["all"] if shared else chains["biz_001"]; ex = ch.export_for("biz_001"); own = sum(r[0] == "biz_001" for r in ex); foreign = len(ex) - own
    P(f"D. {'one chain for all tenants' if shared else 'one chain per tenant     '}: biz_001 verifies {own} of its own events and is shown {foreign} rows from other tenants (event text, tenant, hashes)"); out[f"D_shared_{shared}"] = dict(own=own, foreign=foreign)
print("\n".join(L)); (here / "results/ch11_shared_state.log").write_text("\n".join(L) + "\n"); json.dump(out, open(here / "results/ch11_shared_state.json", "w"), indent=1)
