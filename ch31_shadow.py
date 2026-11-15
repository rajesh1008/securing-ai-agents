#!/usr/bin/env python3
"""Chapter 31, lab 2: shadow two candidate changes over twelve simulated weeks of traffic (ch31_stream.py), with the exit rules written first.
Live pipeline: Chapter 14 verifier at level 3 + Chapter 30 provenance rule on the authenticated channel.
Candidate A (tighten): sibling review ON - hold an invoice when another open invoice of the same vendor has the same amount (the 'c6' of Chapter 30).
Candidate B (loosen):  the layer-agreement check runs only when the document HAS a hidden text layer (a proposed fix for the benign holds F1 describes).
The books move: invoices enter on their issue day, are paid on the Friday run after a decision (AUTO the same day, a held one 2-6 days later).  Writes results/ch31_shadow.json."""
import sys, json, random, copy
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
import ch14_live_extract as X
from bulwark.docagent import Document, Records, verify, parse_rules
from bulwark.autoredteam import Envelope, sender_route
from bulwark.rollout import ExitRule, Shadow, judge, upper_bound, lower_bound
import ch31_stream as S
D = json.load(open(here / "results/ch31_stream.json")); V = D["vendors"]; EV = D["events"]
REG = {p: {f"billing@{S.slug(v['name'])}.example"} for p, v in V.items()}
STRANGER = "rt-ops@attacker.example"
def pipeline(sibling=False, layer_only_if_hidden=False):
    def p(doc, ex, env, books):
        if ex is None: return "REVIEW"
        exv = parse_rules(doc.visible) if (not layer_only_if_hidden or doc.hidden) else None
        v = verify(doc, ex, books, level=3, ex_visible=exv, sibling_review=sibling)
        if env is None: return v.route
        return sender_route(v.route, (v.effect or {}).get("payee_id"), env, REG, trust="channel")[0]
    return p
LIVE, CAND_A, CAND_B = pipeline(), pipeline(sibling=True), pipeline(layer_only_if_hidden=True)
RULE_A = ExitRule("A sibling review", min_decisions=300, max_extra_hold_rate=0.03, max_escapes=0, min_weeks=4, queue_capacity_per_week=6)
RULE_B = ExitRule("B layers only if hidden", min_decisions=300, max_extra_hold_rate=0.03, max_escapes=0, min_weeks=4, queue_capacity_per_week=6)
def next_friday(d): return d + ((4 - d) % 7)
def run():
    rng = random.Random(3103); books = Records({p: dict(name=v["name"], account=v["account"]) for p, v in V.items()}, {})
    entered = set(); pay = []                     # (pay_day, invoice id)
    sa, sb = Shadow(LIVE, CAND_A), Shadow(LIVE, CAND_B); paid_hostile = 0; weekly = {}
    by_day = sorted(EV, key=lambda e: e["day"]); k = 0; held_live = []
    for e in EV:
        t = e["arrive"]
        for x in by_day:
            if x["day"] <= t and x["id"] not in entered: books.invoices[x["id"]] = dict(payee_id=x["pid"], number=x["number"], amount_cents=x["amount"], status="open", day=x["day"]); entered.add(x["id"])
        for pd, iid in [q for q in pay if q[0] <= t]: books.invoices[iid]["status"] = "paid"
        pay = [q for q in pay if q[0] > t]
        doc = Document(e["id"], e["visible"], e["hidden"]); ex = X.to_ex(e["ex"]) if e["ex"] else None
        reg = sorted(REG[e["pid"]])[0]; env = Envelope(reg, reg if (not e["hostile"] or e["channel"] == "vendor_mailbox") else STRANGER)
        label = "hostile" if e["hostile"] else "benign"
        route = sa.decide(e["id"], doc, ex, env, books, ts=t, label=label); sb.decide(e["id"], doc, ex, env, books, ts=t, label=label)
        ready = t if route == "AUTO" else t + rng.randrange(2, 7)
        pay.append((next_friday(ready), e["id"]))
        if route == "AUTO" and e["hostile"]: paid_hostile += 1
        w = t // 7 + 1; weekly.setdefault(w, dict(week=w, n=0, live_auto=0, a_extra=0, b_looser=0)); r = weekly[w]; r["n"] += 1
        if route == "AUTO" and not e["hostile"]: r["live_auto"] += 1
        if sa.log[-1].diff == "TIGHTER" and not e["hostile"]: r["a_extra"] += 1
        if sb.log[-1].diff == "LOOSER" and not e["hostile"]: r["b_looser"] += 1
    return sa, sb, weekly, paid_hostile
def cumulative(sh, rule, weekly, key):
    """key: weekly counter of extra holds the candidate adds; None for a candidate that cannot add holds (a loosening)."""
    rows = []; ids = [e["id"] for e in EV]; wk = {e["id"]: e["arrive"] // 7 + 1 for e in EV}
    for w in sorted(weekly):
        sub = [r for r in sh.log if wk[r.item_id] <= w]; s = Shadow(lambda *a: "", lambda *a: ""); s.log = sub; t = s.tally()
        wh = max([weekly[x][key] for x in weekly if x <= w] or [0]) if key else 0
        verdict, why = judge(rule, live_auto=t["live_auto"], extra_holds=t["extra_holds"], escapes=t["escapes"], errors=t["errors"], decisions=t["decisions"], weeks=w, worst_week_holds=wh)
        rows.append(dict(week=w, **t, ub=round(upper_bound(t["extra_holds"], t["live_auto"]), 4) if t["live_auto"] else 1, verdict=verdict, why=why))
    return rows
def main():
    sa, sb, weekly, ph = run()
    out = dict(rules=dict(A=dict(digest=RULE_A.digest(), **RULE_A.__dict__), B=dict(digest=RULE_B.digest(), **RULE_B.__dict__)), weekly=[weekly[w] for w in sorted(weekly)], paid_hostile_live=ph,
               A=dict(tally=sa.tally(), cum=cumulative(sa, RULE_A, weekly, "a_extra")), B=dict(tally=sb.tally(), cum=cumulative(sb, RULE_B, weekly, None)),
               cand_ms_max=dict(A=max(r.cand_ms for r in sa.log), B=max(r.cand_ms for r in sb.log)))
    print("hostile paid by live:", ph, "| rule digests", RULE_A.digest(), RULE_B.digest())
    for w in out["weekly"]: print(w)
    for n in "AB":
        print(n, out[n]["tally"])
        for r in out[n]["cum"]: print("  wk", r["week"], "live_auto", r["live_auto"], "extra", r["extra_holds"], "looser_benign", r["looser_unlabelled"], "esc", r["escapes"], "ub", r["ub"], r["verdict"], r["why"][:2])
    json.dump(out, open(here / "results/ch31_shadow.json", "w"), indent=1)
if __name__ == "__main__": main()
