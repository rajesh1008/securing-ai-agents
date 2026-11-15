#!/usr/bin/env python3
"""Chapter 13, lab 2: nine ways to alter an evidence log, against five designs. No model. 200 trials per cell, seeded, a different position in a 300-row log each time.
Designs: D1 plain log (no hashes); D2 one shared chain, no anchors; D3 one chain per tenant, no anchors; D4 per-tenant chain, anchor every 25 rows, no final seal; D5 per-tenant chain, anchor every 25 rows and a seal at the end.
The attacker has write access to the log file and nothing else: not the anchor service's key or store. 'Detected' means verification of the tenant's export fails or the anchor check fails."""
import sys, json, random, copy
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
from bulwark.evidence import ChainLog, Anchors, canon, GENESIS
import hashlib
rng = random.Random(1302)
def mk(n_per=100, tenants=("t1", "t2", "t3")):
    ev = []
    for i in range(n_per * len(tenants)):
        t = tenants[i % len(tenants)] if rng.random() < .5 else rng.choice(tenants)
        ev.append(dict(tenant=t, ts=i, kind="egress", decision=rng.choice(["ALLOW", "ALLOW", "ALLOW", "DENY"]), reasons=["ok"], dest_host=rng.choice(["a.example", "b.example", "c.example"])))
    return ev
def build(design, ev):
    if design in ("D1", "D2"):
        ch = ChainLog(); [ch.append(e) for e in ev]; return dict(rows={"all": ch.rows}, anchors=None)
    logs = {}; an = Anchors(); every = 25
    for e in ev:
        lg = logs.setdefault(e["tenant"], ChainLog()); r = lg.append(e)
        if design in ("D4", "D5") and (r["seq"] + 1) % every == 0: an.submit(e["tenant"], r["seq"], r["hash"])
    if design == "D5":
        for t, lg in logs.items():
            if lg.rows and an.last_seq(t) != len(lg.rows) - 1: an.submit(t, len(lg.rows) - 1, lg.head)
    return dict(rows={t: lg.rows for t, lg in logs.items()}, anchors=an if design in ("D4", "D5") else None)
def rehash(rows, start=0):
    prev = rows[start - 1]["hash"] if start else GENESIS
    for i in range(start, len(rows)):
        r = rows[i]; r["prev"] = prev; r["seq"] = i; r["hash"] = hashlib.sha256(canon({k: v for k, v in r.items() if k != "hash"})).hexdigest(); prev = r["hash"]
def detect(design, state, victim):
    if design == "D1": return False
    if design == "D2":
        return not ChainLog.verify_rows(state["rows"]["all"])[0]
    rows = state["rows"].get(victim, [])
    if not ChainLog.verify_rows(rows)[0]: return True
    if state["anchors"]: return not state["anchors"].check(victim, rows)[0]
    return False
def attack(name, design, state, victim):
    key = "all" if design in ("D1", "D2") else victim
    rows = state["rows"][key]; idx = [i for i, r in enumerate(rows) if r["tenant"] == victim] if key == "all" else list(range(len(rows)))
    n = len(idx)
    if name == "edit in place":
        i = rng.choice(idx); rows[i]["dest_host"] = "z.example"
    elif name == "delete one row":
        i = rng.choice(idx[:-1]); del rows[i]
    elif name == "truncate last 10":
        del rows[-10:]
    elif name == "edit and rehash":
        i = rng.choice(idx[:max(1, n - 30)]); rows[i]["dest_host"] = "z.example"; rehash(rows, i)
    elif name == "swap two rows":
        k = rng.randrange(0, n - 2); a, b = idx[k], idx[k + 1]; rows[a], rows[b] = rows[b], rows[a]
    elif name == "insert forged row":
        i = rng.choice(idx[:-30]); rows.insert(i, dict(tenant=victim, ts=rows[i]["ts"], kind="egress", decision="ALLOW", reasons=["ok"], dest_host="a.example")); rehash(rows, i)
    elif name == "edit last 5 and rehash":
        i = idx[-1 - rng.randrange(0, 5)]
        rows[i]["dest_host"] = "z.example"; rehash(rows, i)
    elif name == "splice another tenant's row":
        other = [r for r in (state["rows"]["all"] if key == "all" else sum((v for t, v in state["rows"].items() if t != victim), [])) if r["tenant"] != victim]
        i = rng.choice(idx[:-30]); f = copy.deepcopy(rng.choice(other)); f["tenant"] = victim; rows.insert(i, f); rehash(rows, i)
    elif name == "rebuild whole log":
        mine = [{k: v for k, v in rows[i].items() if k not in ("prev", "hash", "seq")} for i in idx]
        for r in mine[len(mine) // 2:]: r["decision"] = "ALLOW"
        new = ChainLog(); [new.append(r) for r in mine]
        if key == "all":
            rest = [r for r in rows if r["tenant"] != victim]; state["rows"]["all"] = rest   # the shared-chain rebuild is shown as a break elsewhere: rebuild of everything
            full = [{k: v for k, v in r.items() if k not in ("prev", "hash", "seq")} for r in sorted(rows, key=lambda r: r["seq"])]
            nl = ChainLog(); [nl.append(r) for r in full]; state["rows"]["all"] = nl.rows
        else: state["rows"][key] = new.rows
ATT = ["edit in place", "delete one row", "truncate last 10", "edit and rehash", "swap two rows", "insert forged row", "edit last 5 and rehash", "splice another tenant's row", "rebuild whole log"]
DES = ["D1", "D2", "D3", "D4", "D5"]; N = 200
res = {}; clean_fp = {}
for d in DES:
    ok = 0
    for _ in range(N):
        st = build(d, mk()); ok += detect(d, st, "t2")
    clean_fp[d] = ok
for a in ATT:
    res[a] = {}
    for d in DES:
        hit = 0
        for _ in range(N):
            ev = mk(); st = build(d, ev); attack(a, d, st, "t2"); hit += detect(d, st, "t2")
        res[a][d] = hit
# blast radius of one edit in the middle of the shared chain vs per-tenant
ev = mk(); sh = build("D2", ev); pt = build("D3", ev); rows = sh["rows"]["all"]; mid = [i for i, r in enumerate(rows) if r["tenant"] == "t2"][50]; rows[mid]["dest_host"] = "z.example"
br_shared = {t: not ChainLog.verify_rows([r for r in rows if r["tenant"] == t])[0] for t in ("t1", "t2", "t3")}   # a tenant's rows alone are not a valid chain: it must be given the full chain
full_bad = ChainLog.verify_rows(rows); tenants_unverifiable_shared = 3 if not full_bad[0] else 0
j = [i for i, r in enumerate(pt["rows"]["t2"])][50]; pt["rows"]["t2"][j]["dest_host"] = "z.example"; pt_bad = {t: not ChainLog.verify_rows(pt["rows"][t])[0] for t in ("t1", "t2", "t3")}
L = [f"{'attack (200 trials, victim t2)':32}" + "".join(f"{d:>6}" for d in DES)]
for a in ATT: L.append(f"{a:32}" + "".join(f"{res[a][d]:>6}" for d in DES))
L.append(f"{'false alarms on a clean log':32}" + "".join(f"{clean_fp[d]:>6}" for d in DES))
L.append(f"one edit in a t2 row: the shared chain fails at row {full_bad[1]} and the chain every tenant would need in order to verify is the same failed chain (tenants affected: 3 of 3); per-tenant chains: failing tenants {[t for t, v in pt_bad.items() if v]}")
print("\n".join(L)); json.dump(dict(trials=N, results=res, clean_false_alarms=clean_fp, per_tenant_failing=[t for t, v in pt_bad.items() if v], shared_first_bad=full_bad[1]), open(here / "results" / "ch13_tamper.json", "w"), indent=1)
open(here / "results" / "ch13_tamper.log", "w").write("\n".join(L) + "\n")
