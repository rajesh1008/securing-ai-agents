#!/usr/bin/env python3
"""Chapter 24, lab 4 (no model; a simulation with the real KeyRing): rotating a provider key.
Setting: six Quill deployments (actor, reader, reviewer, nightly batch, support bot, staging) send 10,000 requests in all, spread evenly.  A new provider key exists from request 0; the old key is revoked at the provider at request R.
ARM EMBEDDED: every deployment holds the provider key; each picks the new key up at a random point (its rollout) between request 0 and request W.  A request signed with the old key after R fails.
ARM GATEWAY: only the gateway holds the provider key and swaps it once at request 0 (hot reload).  Agents hold gateway tokens signed by the KeyRing; the gateway key rotates with an overlap (new key from request 3,000, old key's verification window to 6,000) and the real KeyRing verifies every request.
LEAK drill: the provider key leaks at request 5,000 and is revoked at once; EMBEDDED fails every request from a deployment that has not yet redeployed (redeploy delay uniform 0..W), GATEWAY swaps in one step.
200 random rollouts per cell, seed 24.  Writes results/ch24_rotation.json and .log"""
import json, random, sys, time
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
from bulwark.gateway import KeyRing
N, D = 10_000, 6
def embedded(R: int, W: int, rng) -> int:
    pick = [rng.randint(0, W) for _ in range(D)]; fails = 0
    for i in range(N):
        d = i % D
        if i >= R and pick[d] > i: fails += 1
    return fails
def leak(W: int, rng) -> int:
    redeploy = [5000 + rng.randint(0, W) for _ in range(D)]; return sum(1 for i in range(5000, N) if redeploy[i % D] > i)
L = [f"requests {N}, deployments {D}"]; out = {}
for W in (1000, 3000):
    for R in (1000, 2000, 4000):
        rng = random.Random(24); f = [embedded(R, W, rng) for _ in range(200)]
        L.append(f"EMBEDDED rollout window {W}, old key revoked at {R}: failed requests mean {sum(f)/200:.0f}, worst {max(f)}, rollouts with any failure {sum(1 for x in f if x)} of 200"); out[f"embedded_W{W}_R{R}"] = dict(mean=sum(f) / 200, worst=max(f), any=sum(1 for x in f if x))
ks = KeyRing(); ks.add("k1", b"gateway-key-1", 0, 6000); ks.add("k2", b"gateway-key-2", 3000, 20000)
toks = {}; t0 = time.perf_counter(); fails = 0; mints = 0; verifies = 0; kids = {"k1": 0, "k2": 0}
for i in range(N):
    d = i % D; tk = toks.get(d)
    if tk is None or ks.signing(i) != tk.split(".", 1)[0] and i % 500 == 0:
        toks[d] = ks.issue(dict(agent=f"d{d}", tid=f"t{d}", aliases=["quill-actor"], budget_tokens=10**9, exp=i + 1500), i); mints += 1; tk = toks[d]
    c, why = ks.verify(tk, i); verifies += 1
    if c is None:
        toks[d] = ks.issue(dict(agent=f"d{d}", tid=f"t{d}", aliases=["quill-actor"], budget_tokens=10**9, exp=i + 1500), i); mints += 1; c, why = ks.verify(toks[d], i)
        if c is None: fails += 1
    else: kids[tk.split(".", 1)[0]] += 1
el = time.perf_counter() - t0
L.append(f"GATEWAY: provider key swapped once at request 0; gateway-token key rotated with overlap: failed requests {fails} of {N}; verifies by key {kids}; tokens minted {mints}; mean mint+verify per request {el/N*1e6:.0f} microseconds")
out["gateway"] = dict(fails=fails, kids=kids, mints=mints, us_per_request=el / N * 1e6)
for W in (1000, 3000):
    rng = random.Random(24); f = [leak(W, rng) for _ in range(200)]
    L.append(f"LEAK at 5000, EMBEDDED redeploy window {W}: failed requests mean {sum(f)/200:.0f}, worst {max(f)} of {N-5000}; GATEWAY: 0 agent changes, one swap"); out[f"leak_W{W}"] = dict(mean=sum(f) / 200, worst=max(f))
# revoke the gateway token key: every token under it fails at once, new tokens under k2 verify
ks.revoke("k1"); old = toks[0]; L.append("Revoking gateway key k1 after rotation: token signed under k1 -> " + ks.verify(old, 7000)[1] if old.startswith("k1.") else "Revoking gateway key k1: current tokens are under k2 -> " + ks.verify(old, 7000)[1])
print("\n".join(L)); json.dump(out, open(here / "results/ch24_rotation.json", "w"), indent=1); open(here / "results/ch24_rotation.log", "w").write("\n".join(L) + "\n")
