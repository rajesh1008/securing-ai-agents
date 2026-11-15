#!/usr/bin/env python3
"""Chapter 13, walkthrough and cost. No model. An examiner (Nina) reconstructs the Chapter 12 pixel incident from the evidence vault of ch13_questions.py and nothing else; then the cost of the design is measured."""
import io, sys, json, time, contextlib, hashlib
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
with contextlib.redirect_stdout(io.StringIO()): import ch13_questions as q
from bulwark.evidence import Vault, ChainLog, canon
from bulwark.egress import Egress, Output, contains_private
V = q.V; t = "biz_hcb"; out = []
def say(s): out.append(s); print(s)
exp = V.export(t); say(f"1 export   : tenant {t}: {len(exp['rows'])} rows, {len(exp['anchors'])} anchors, foreign rows {sum(1 for r in exp['rows'] if r['tenant'] != t)}")
say(f"2 verify   : chain {ChainLog.verify_rows(exp['rows'])[0]}; anchors {V.anchors.check(t, exp['rows'])}")
hits = [r for r in exp["rows"] if r.get("dest_host") == "track.lonestar-pay.example"]
alw = [r for r in hits if r["decision"] == "ALLOW" and r["level"] == 0]
say(f"3 scope    : {len(hits)} rows name track.lonestar-pay.example; delivered before the fix (policy v0.12, level 0): {len(alw)}; first at seq {alw[0]['seq']}, last at seq {alw[-1]['seq']}; after the fix: {[(r['decision'], r['reasons'], r['edits'], r['canary']) for r in hits if r['level'] == 4][:3]}")
d0 = V.stores[t].get(f"{alw[0]['seq']}:left").decode()
say(f"4 content  : (store open, tenant key) the first delivered output was {d0[:60]!r}...; contains the account number: {contains_private(d0, (q.TEN[t][1],))}; keyed digest of it matches the row: {V.ev.digest(t, d0) == alw[0]['ctx_digest']}")
r5 = Egress(4, q.ctx(t)).check(Output('render', body=d0)); say(f"5 replay   : the same output at today's policy (E4): allowed {r5[0]}, reason {r5[1]}, text that would leave: {r5[2]!r}; private value in it: {contains_private(r5[2], (q.TEN[t][1],))}")
other = [x for x in V.export('biz_bcp')['rows'] if x.get('dest_host') == 'track.lonestar-pay.example']
say(f"6 other tenants: rows naming that host in the other two tenants' own chains: {len(other)} and {len([x for x in V.export('biz_riv')['rows'] if x.get('dest_host') == 'track.lonestar-pay.example'])}")
sup = [r for r in exp["rows"] if r["kind"] == "support_read"]
say(f"7 access   : staff reads of {t}: {[(r['actor'], r['grant']) for r in sup]}")
say(f"8 erasure  : tenant {t} leaves. destroyed: {V.erase(t)}; chain still verifies: {V.verify(t)}; the store: {V.stores.get(t)}; other tenants verify: {V.verify('biz_bcp')[0] and V.verify('biz_riv')[0]}")
# cost
v = Vault(b"c" * 32, 100); N = 100_000; t0 = time.perf_counter()
for i in range(N): v.record(f"t{i % 50:02d}", ts=i, kind="egress", decision="ALLOW", reasons=["ok"], dest_host="a.example", level=4, edits=0, canary=False, out_digest="a" * 64, ctx_digest="b" * 64, policy="v0.13", principal="p1", tool="email")
ta = time.perf_counter() - t0
for tn in list(v.logs): v.seal(tn)
t1 = time.perf_counter(); allok = all(v.verify(tn)[0] for tn in v.logs); tv = time.perf_counter() - t1
size = sum(len(canon(r)) + 1 for l in v.logs.values() for r in l.rows)
say(f"9 cost     : {N} events over 50 tenants: append {ta/N*1e6:.0f} us per event (validation, hash, anchor every 100 rows), verify all with anchors {tv*1000:.0f} ms ({allok}); {size/N:.0f} bytes per row, {size/1e6:.1f} MB")
json.dump(out, open(here / "results" / "ch13_walkthrough.json", "w"), indent=1); open(here / "results" / "ch13_walkthrough.log", "w").write("\n".join(out) + "\n")
