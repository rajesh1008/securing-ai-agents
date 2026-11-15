#!/usr/bin/env python3
"""Chapter 31, lab 4: progressive rollout, with and without the evidence a rollout cannot see.
R1 (tighten, candidate A, loud failure): suppose shadow mode had been skipped and sibling review went live on the ladder 5/25/50/100 per cent of vendor buckets, one rung a week at most.
    The stage's own decisions are judged by the exit rule each week against its concurrent control buckets.  Compared with a cutover of everything in week 1.
R2 (loosen, candidate B, quiet failure): B was promoted by shadow traffic in week 8.  A burst of 12 label-confusion invoices from vendors' mailboxes (Chapter 14's H7, extracted live once) arrives in weeks 9-12, 3 a week.
    Ladder from week 9 vs a cutover at week 9 vs the canary gate of lab 3 in front of the first rung.  Writes results/ch31_rollout.json."""
import sys, json, random, copy, time
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
import ch14_corpus as C, ch31_stream as S, ch31_shadow as SH
import ch14_live_extract as X
from bulwark.docagent import Document, Records
from bulwark.autoredteam import Envelope
from bulwark.rollout import ExitRule, Rollout, LADDER, bucket, judge, upper_bound, lower_bound
SALT = "ch31-r1"
def books_at(events_by_id, upto_id): pass
def r1(keyfn=lambda e: e["pid"]):
    """Re-run the traffic simulation of lab 2 with the candidate enforced on buckets.  Uses lab 2's shadow logs (same books at decision time) to read what A would have said for every event."""
    sa, sb, weekly, ph = SH.run(); log = {r.item_id: r for r in sa.log}; ev = {e["id"]: e for e in SH.EV}
    rule = ExitRule("A stage", min_decisions=20, max_extra_hold_rate=0.03, max_escapes=0, min_weeks=1)
    ro = Rollout(rule, SALT); rows = []; extra_cum = 0; base_extra = 0
    vendors = sorted(S.make_world()); share = {p: bucket(p, SALT) for p in vendors}
    for w in range(1, 13):
        if ro.stage_idx == 0 and not ro.killed and w == 1: ro.stage_idx = 1                 # first rung is entered in week 1
        evs = [e for e in SH.EV if e["arrive"] // 7 + 1 == w and not e["hostile"]]
        enf = [e for e in evs if ro.enforced(keyfn(e))]; ctl = [e for e in evs if not ro.enforced(keyfn(e))]
        live_auto_enf = [e for e in enf if log[e["id"]].live == "AUTO"]; extra_enf = [e for e in live_auto_enf if log[e["id"]].diff == "TIGHTER"]
        live_auto_ctl = [e for e in ctl if log[e["id"]].live == "AUTO"]
        stage_hist = ro.history[-1]["week"] if ro.history else 0
        # evidence for the verdict: this week's enforced buckets plus all earlier weeks at the same percent
        rows.append(dict(week=w, percent=ro.percent, enforced_events=len(enf), traffic_share=round(len(enf) / max(1, len(evs)), 3), live_auto_enf=len(live_auto_enf), extra_holds=len(extra_enf), ctl_hold_rate=round(1 - len(live_auto_ctl) / max(1, len(ctl)), 3)))
        extra_cum += len(extra_enf); base_extra += sum(1 for e in evs if log[e["id"]].live == "AUTO" and log[e["id"]].diff == "TIGHTER")
        # judge with this stage's accumulated evidence
        same = [r for r in rows if r["percent"] == ro.percent]
        v, why = judge(rule, live_auto=sum(r["live_auto_enf"] for r in same), extra_holds=sum(r["extra_holds"] for r in same), escapes=0, errors=0, decisions=sum(r["enforced_events"] for r in same), weeks=len(same))
        ro.step(w, v, why); rows[-1].update(verdict=v, why=why[:1], extra_cum=extra_cum, bigbang_cum=base_extra)
        if ro.percent == 0 and v == "REJECT": ro.killed = False
    return dict(rows=rows, vendor_buckets={p: share[p] for p in vendors}, history=ro.history)
BURST = here / "results/ch31_burst.json"
def build_burst():
    if BURST.exists(): return json.load(open(BURST))
    import ch30_loop as L
    V = S.make_world(); r = random.Random(3110); items = []
    for k in range(12):
        pid = r.choice(sorted(V)); e = dict(id=f"X{k:02d}", pid=pid, number=f"{V[pid]['code']}-9{k:03d}", amount=r.randrange(12_000, 240_000, 100), hostile=True, cls="H7_label_confusion")
        d = S.doc_for(V, e); items.append(dict(e, week=9 + k // 3, visible=d.visible, hidden=d.hidden, ex=L.extract(d)))
    json.dump(dict(items=items, calls=L.meter.calls), open(BURST, "w"), indent=1); return json.load(open(BURST))
def r2():
    burst = build_burst()["items"]; V = S.make_world(); out = []; tot = dict(bigbang=0, ladder=0, canary_gated=0)
    ro = Rollout(ExitRule("B", 300, 0.03), "ch31-r2"); stages = {9: 1, 10: 2, 11: 3, 12: 4}
    for it in burst:
        w = it["week"]; ro.stage_idx = stages[w]
        pid = it["pid"]; books = Records({pid: dict(name=V[pid]["name"], account=V[pid]["account"])}, {"X": dict(payee_id=pid, number=it["number"], amount_cents=it["amount"], status="open")})
        doc = Document(it["id"], it["visible"], it["hidden"]); ex = X.to_ex(it["ex"]); reg = sorted(SH.REG[pid])[0]; env = Envelope(reg, reg)
        live, cand = SH.LIVE(doc, ex, env, books), SH.CAND_B(doc, ex, env, books)
        escaped = cand == "AUTO" and live != "AUTO"
        enf = ro.enforced(pid); out.append(dict(id=it["id"], week=w, vendor=pid, bucket=bucket(pid, "ch31-r2"), live=live, cand=cand, escaped=escaped, enforced_at_stage=enf, percent=ro.percent))
        tot["bigbang"] += escaped; tot["ladder"] += escaped and enf
    return dict(items=out, totals=tot, live_holds_all=all(o["live"] != "AUTO" for o in out))
def main():
    a = r1(); print("R1 rows (bucket = vendor)")
    for r in a["rows"]: print(" ", r)
    a2 = r1(keyfn=lambda e: e["id"]); print("R1 rows (bucket = invoice)")
    for r in a2["rows"]: print(" ", r)
    b = r2(); print("R2", b["totals"], "live holds all:", b["live_holds_all"])
    for o in b["items"]: print("  ", o)
    json.dump(dict(r1_vendor=a, r1_invoice=a2, r2=b), open(here / "results/ch31_rollout.json", "w"), indent=1)
if __name__ == "__main__": main()
