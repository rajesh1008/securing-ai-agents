#!/usr/bin/env python3
"""Chapter 39, lab 3 (no model): what changes between the payment and the examiner's visit.  Three things months do.
 1 replay   the examiner asks 'would Quill pay this today?'.  The money gate is replayed on the recorded typed inputs against the vendor record as it is on day 300 (it changed again) and against a record rebuilt for day 100.
 2 erasure  the tenant leaves and its key is destroyed (Chapter 13): what the export still answers, what Q14 now gives, whether the keyed digests still link.
 3 retention the older rows are purged by the retention rule: the whole-chain verifier fails, the segment verifier passes, and what each one cannot say.
Writes results/ch39_months_later.json and .log."""
import sys, json, copy
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
from bulwark.evidence import ChainLog
from bulwark.moneypath import *
import bulwark.examiner as X
import ch39_payment as P
L = []; res = {}
def line(s): L.append(s); print(s)
def main():
    b = P.build("V1"); V = b["vault"]; rows = b["rows"]
    # 1 replay -------------------------------------------------------------------------------------------------------------------------------------
    req = PayRequest("INV-2231", P.PAYEE, 481_250, doc_amount_cents=481_250, day=100, principal="prin_emily", approver="prin_hector")
    def gate_with(vendor):
        return MoneyGate(P.T, Vendors({P.PAYEE: vendor}), {"INV-2231": Invoice("INV-2231", P.PAYEE, 481_250, number="LSP-90417")}, Ledger())
    v_then = Vendor(P.PAYEE, "Lone Star Paper Supply", "US-ACC-9902", 1_000_000, live_since=61, created_day=-500, confirmed_by="kevin_brandt", version=2, previous_account="US-ACC-4417", changed_day=61)
    d_then = gate_with(v_then).check(req, reserve=False)
    v_now = Vendor(P.PAYEE, "Lone Star Paper Supply", "US-ACC-3305", 1_000_000, live_since=296, created_day=-500, confirmed_by="kevin_brandt", version=3, previous_account="US-ACC-9902", changed_day=296)
    req_now = PayRequest("INV-2231", P.PAYEE, 481_250, doc_amount_cents=481_250, day=300, principal="prin_emily", approver="prin_hector"); d_now = gate_with(v_now).check(req_now, reserve=False)
    d_naive = gate_with(v_now).check(req, reserve=False)
    line(f"1 replay: rebuilt record for day 100 (vendor version 2, from the vendor-change rows) -> {d_then.outcome} {d_then.codes} destination {d_then.destination}; recorded decision was ALLOW ok")
    line(f"          replay on day 100 inputs against the vendor record as it is today (version 3, account changed on day 296) -> {d_naive.outcome} {d_naive.codes} destination {d_naive.destination}: the destination differs from the one that was paid (US-ACC-9902)")
    line(f"          replay of today's request on day 300 -> {d_now.outcome} {d_now.codes}")
    res["replay"] = dict(then=[d_then.outcome, d_then.codes], naive=[d_naive.outcome, d_naive.codes, d_naive.destination], now=[d_now.outcome, d_now.codes])
    disp_row = [r for r in rows if r["kind"] == "dispatch" and r["task"] == P.TASK][0]
    line(f"          the dispatch row carries vendor_version={disp_row['vendor_version']} and a keyed digest of the destination; the vendor record at that version is not in the chain, it is in the vendor table's history (if the table keeps one)")
    # 2 erasure ------------------------------------------------------------------------------------------------------------------------------------
    st = V.stores[P.T]; items = len(st.items); sc = X.scope(rows, P.TASK, P.PAYEE)
    pre = V.ev.digest(P.T, "US-ACC-9902")
    er = V.erase(P.T); exp = V.export(P.T); ok = ChainLog.verify_rows(exp["rows"])[0]; an = V.anchors.check(P.T, exp["rows"]); post = V.ev.digest(P.T, "US-ACC-9902")
    cov = X.coverage(exp["rows"], P.TASK, P.PAYEE, ok and an[0]); cnt = {k: sum(1 for c in cov.values() if c[0] == k) for k in ("ANSWERABLE", "PARTIAL", "NOT_IN_EVIDENCE")}
    line(f"2 erasure: {er['items_destroyed']} content items destroyed (store held {items}); chain verifies {ok}, anchors {an}; coverage of the 14 questions after erasure {cnt} (before: 13 answerable, Q14 not in the export either way)")
    line(f"          a keyed digest recomputed after the key is gone ({post[:12]}...) differs from the one in the row ({pre[:12]}...): the digest can no longer be matched to a value; the row says dest_digest={disp_row['dest_digest'][:12]}...")
    res["erasure"] = dict(destroyed=er["items_destroyed"], chain=ok, anchors=an[0], coverage=cnt, digest_still_links=(pre == post))
    # 3 retention ----------------------------------------------------------------------------------------------------------------------------------
    b2 = P.build("V1"); rows2 = b2["rows"]; anchors = b2["export"]["anchors"]
    for cut in (60, 50):
        seg = rows2[cut:]; whole = ChainLog.verify_rows(seg); segv = X.verify_segment(seg, anchors)
        line(f"3 retention: rows before seq {cut} purged ({len(seg)} kept): whole-chain verifier {whole} ; segment verifier {segv[0]} ({segv[1]})")
        res[f"retention_{cut}"] = dict(whole=list(whole), segment=segv[0], msg=segv[1])
    seg = copy.deepcopy(rows2[60:]); seg[10]["amount_cents"] = 1; line(f"   edit one retained row: segment verifier -> {X.verify_segment(seg, anchors)}")
    seg = rows2[60:-3]; line(f"   drop the last 3 rows (truncation after the last anchor at seq {anchors[-1]['seq']}): segment verifier -> {X.verify_segment(seg, anchors)[0]} ({X.verify_segment(seg, anchors)[1][:60]}...); whole-export anchors check -> {b2['vault'].anchors.check(P.T, rows2[:-3])}")
    sc2 = X.scope(rows2[60:], P.TASK, P.PAYEE); cov2 = X.coverage(rows2[60:], P.TASK, P.PAYEE, True); line(f"   with rows 0-59 purged the vendor-change rows (seq 0 and 1) are gone: Q9 -> {cov2['Q9'][0]} missing {cov2['Q9'][1]}; in scope {len(sc2)} rows")
    res["retention_q9"] = [cov2["Q9"][0], cov2["Q9"][1]]
    json.dump(dict(res, log=L), open(here / "results/ch39_months_later.json", "w"), indent=1, default=list); open(here / "results/ch39_months_later.log", "w").write("\n".join(L) + "\n")
if __name__ == "__main__": main()
