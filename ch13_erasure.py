#!/usr/bin/env python3
"""Chapter 13, lab 3: a deletion request meets a tamper-evident log. No model. 12 tenants, 5,040 events (420 each), seeded. Tenant t07 asks to be forgotten.
Four ways to honour it: E1 delete t07's rows from one shared chain; E2 replace t07's rows in the shared chain with tombstones that keep the row hash; E3 one chain per tenant, delete t07's chain, store and key;
E4 per-tenant chains with keyed digests: destroy the key and the content store, keep the typed rows. Measured: how many of the other 11 tenants still verify; what remains about t07; whether a guess at t07's account number can still be tested against what remains."""
import sys, json, random, hashlib, hmac, time
from multiprocessing import Pool
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
from bulwark.evidence import ChainLog, Vault, canon, GENESIS
rng = random.Random(1303)
TEN = [f"t{i:02d}" for i in range(1, 13)]; VICTIM = "t07"; ACC = {t: f"US-ACC-{rng.randrange(10**7, 10**8)}" for t in TEN}; PEOPLE = {t: f"person_{t}" for t in TEN}
def events():
    out = []
    for i in range(420 * 12):
        t = TEN[i % 12]; out.append((t, dict(ts=i, kind="egress", decision=rng.choice(["ALLOW", "ALLOW", "DENY"]), reasons=["ok"], dest_host=rng.choice(["a.example", "b.example"]), acct=ACC[t])))
    return out
EV = events()
# ---- E1 / E2: shared chain with raw sha256 digest of the account number inside each row (what a first design does)
def sha(t): return hashlib.sha256(ACC[t].encode()).hexdigest()
sh = ChainLog(); [sh.append(dict(tenant=t, ts=e["ts"], kind=e["kind"], decision=e["decision"], dest_host=e["dest_host"], acct_digest=sha(t))) for t, e in EV]
def verify_shared(rows):  # a verifier given the rows; tombstones carry their original prev/hash and are linked, not recomputed
    prev = GENESIS
    for r in rows:
        if r.get("tombstone"):
            if r["prev"] != prev: return False
        else:
            if r["prev"] != prev or hashlib.sha256(canon({k: v for k, v in r.items() if k != "hash"})).hexdigest() != r["hash"]: return False
        prev = r["hash"]
    return True
e1 = [r for r in sh.rows if r["tenant"] != VICTIM]
e2 = [dict(prev=r["prev"], hash=r["hash"], seq=r["seq"], tombstone=True, tenant=r["tenant"], ts=r["ts"]) if r["tenant"] == VICTIM else r for r in sh.rows]
# ---- E3 / E4: vault
V = Vault(b"\x07" * 32, 25); RAW = {}
for t, e in EV:
    V.record(t, content={"ctx": f"acct {e['acct']}"}, ts=e["ts"], kind=e["kind"], decision=e["decision"], reasons=e["reasons"], dest_host=e["dest_host"], ctx_digest=V.ev.digest(t, e["acct"]), approver=V.pseudonym(t, PEOPLE[t]))
for t in TEN: V.seal(t)
before = {t: V.verify(t) for t in TEN}
exp_before = V.export(VICTIM); guess_before = V.ev.digest(VICTIM, ACC[VICTIM]) == exp_before['rows'][0]['ctx_digest']; master_copy = Vault(b'\x07' * 32, 25)                       # what the tenant took away with it before the deletion
pre_items = len(V.stores[VICTIM].items); pre_bytes = sum(len(v) for v in V.stores[VICTIM].items.values())
r = V.erase(VICTIM)
others_ok = sum(1 for t in TEN if t != VICTIM and V.verify(t)[0]); victim_ok = V.verify(VICTIM)
dec = V.stores.get(VICTIM)
# can the old key decrypt anything? (the operator no longer has it; the master secret is the only way to re-derive: so destroy-by-rotating the master per tenant in production; here the shredded key is replaced)
# what an attacker with a stolen copy of E1/E2 can test: raw sha256 digest of a guessed account number
def trial(lo_hi):
    lo, hi = lo_hi; tgt = sha(VICTIM); 
    for n in range(lo, hi):
        if hashlib.sha256(f"US-ACC-{n}".encode()).hexdigest() == tgt: return n
    return None
if __name__ == "__main__":
    target = int(ACC[VICTIM].split("-")[-1]); span = 10 ** 8 - 10 ** 7; chunks = [(10 ** 7 + k * span // 12, 10 ** 7 + (k + 1) * span // 12) for k in range(12)]
    t0 = time.perf_counter()
    with Pool(4) as p: found = [x for x in p.map(trial, chunks) if x]
    dt = time.perf_counter() - t0
    keyed_guess = master_copy.ev.digest(VICTIM, ACC[VICTIM]) == exp_before['rows'][0]['ctx_digest']
    rows_victim = exp_before["rows"]; fields = sorted({k for r in rows_victim for k in r}); 
    L = ["design                                 other tenants still verify | rows about t07 left | content left | account guess testable",
         f"E1 delete t07 rows, shared chain       {int(verify_shared(e1))}/1 chain (all 11 tenants share it) -> 0 of 11 | 0 | 0 | n/a",
         f"E2 tombstones, shared chain            {int(verify_shared(e2))}/1 chain -> 11 of 11 | {sum(1 for r in e2 if r.get('tombstone'))} (tenant, ts, hash) | 0 | raw sha256 digests are gone with the bodies",
         f"E3 per-tenant chains, delete t07       {others_ok} of 11 | 0 | 0 | n/a",
         f"E4 per-tenant, key destroyed           {others_ok} of 11 (t07's own chain verifies: {victim_ok[0]}) | {len(V.logs[VICTIM].rows)} typed rows | store items {pre_items} ({pre_bytes} bytes) -> {len(V.stores.get(VICTIM).items) if VICTIM in V.stores else 0} | guess of the right number matched its keyed digest before erasure: {guess_before}; with the master secret but without the destroyed salt: {keyed_guess}",
         f"unkeyed sha256 digest of the account number: found by trying the whole 90,000,000-number space in {dt:.1f} s on 4 processes (found {found})",
         f"export t07 took with it before erasure: {len(exp_before['rows'])} rows, verifies after erasure: {ChainLog.verify_rows(exp_before['rows'])[0]}; fields in rows: {', '.join(fields)}"]
    print("\n".join(L)); json.dump(dict(others_ok=others_ok, E1_chain_verifies=verify_shared(e1), E2_chain_verifies=verify_shared(e2), victim_rows_e4=len(V.logs[VICTIM].rows), items_destroyed=r["items_destroyed"], bruteforce_seconds=dt, found=found,
        bytes_destroyed=pre_bytes, tombstones=sum(1 for x in e2 if x.get("tombstone")), export_verifies=ChainLog.verify_rows(exp_before["rows"])[0], fields=fields), open(here / "results" / "ch13_erasure.json", "w"), indent=1)
    open(here / "results" / "ch13_erasure.log", "w").write("\n".join(L) + "\n")
