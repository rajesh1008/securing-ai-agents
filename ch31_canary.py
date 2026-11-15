#!/usr/bin/env python3
"""Chapter 31, lab 3: the shadow run sees 8 hostile documents in 566.  What does 'zero escapes' say about candidate B, and what do canaries add?
(1) Exact upper bounds on the hostile-side rate from the live traffic alone.  (2) Canaries: the 253 wins of Chapter 30 and the 144 scripted hostile cases are injected into the shadow
(labelled 'canary', books and envelopes as stored), judged against the live pipeline.  Writes results/ch31_canary.json."""
import sys, json
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
import ch30_replay as R
from bulwark.docagent import Document, verify, parse_rules
from bulwark.autoredteam import Envelope, ReplayCase, sender_route
from bulwark.rollout import Shadow, upper_bound, n_to_exclude
import ch14_live_extract as X
def pipe(layer_only_if_hidden=False, sibling=False):
    def p(doc, ex, env, books):
        exv = parse_rules(doc.visible) if (not layer_only_if_hidden or doc.hidden) else None
        v = verify(doc, ex, books, level=3, ex_visible=exv, sibling_review=sibling)
        if env is None: return v.route
        return sender_route(v.route, (v.effect or {}).get("payee_id"), env, R.REGISTERED, trust="channel")[0]
    return p
def cases():
    cache = R.build_cache(); loop = json.load(open(here / "results/ch30_loop.json")); out = []
    for c in loop["campaigns"]:
        for r in c["rounds"]:
            if r.get("won") and r.get("ex"):
                out.append(ReplayCase(f"{c['arm']}-{c['cid']}-{r['round']}", "win", Document("w", r["visible"], r.get("hidden") or ""), R.to_ex(r["ex"]), Envelope(r.get("header_from") or R.STRANGER, R.STRANGER)))
    for k, it in enumerate(cache["items"]):
        if it["ex"] is None or it["kind"] != "hostile": continue
        d = Document(f"x{k}", it["visible"], it["hidden"]); ex = R.to_ex(it["ex"]); reg = sorted(R.REGISTERED[R.rec.invoices[it["inv"]]["payee_id"]])[0]
        out.append(ReplayCase(f"hs{k}-{it['cls']}", "hostile", d, ex, Envelope(reg, R.STRANGER))); out.append(ReplayCase(f"hv{k}-{it['cls']}", "hostile", d, ex, Envelope(reg, reg)))
    return out
def main():
    cs = cases(); res = {}
    for name, cand in {"B layers only if hidden": pipe(layer_only_if_hidden=True), "A sibling review": pipe(sibling=True)}.items():
        for mode in ("both", "verifier"):
            # a stranger's AUTO would be held by provenance; layer='verifier' skips it, as in Chapter 30
            sh = Shadow(lambda d, e, v, b: pipe()(d, e, v, b), cand, books_of=lambda b: R.rec)
            for c in cs: sh.decide(c.cid, c.doc, c.ex, c.env if mode == "both" else None, R.rec, label="canary")
            t = sh.tally(); res[f"{name} / {mode}"] = dict(canaries=len(cs), escapes=t["escapes"], first=[r.item_id for r in sh.log if r.diff == "LOOSER"][:5], live_auto=sum(r.live == "AUTO" for r in sh.log))
            print(name, mode, res[f"{name} / {mode}"])
    stream = json.load(open(here / "results/ch31_shadow.json"))
    res["bounds"] = dict(hostile_in_stream=8, ub_zero_in_8=upper_bound(0, 8), n_for_5pct=n_to_exclude(0.05), n_for_1pct=n_to_exclude(0.01), n_for_01pct=n_to_exclude(0.001))
    print(res["bounds"]); json.dump(res, open(here / "results/ch31_canary.json", "w"), indent=1)
if __name__ == "__main__": main()
