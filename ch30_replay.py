#!/usr/bin/env python3
"""Chapter 30, lab 2: the regression gate.  Every change to the invoice path is checked by replaying stored inputs with cached extractions (no model calls at gate time).
Corpus: (a) every win from lab 1 (results/ch30_loop.json), with the envelope it arrived in; (b) the nine scripted hostile classes of Chapter 14 on 8 open invoices, sent once from a stranger's channel
and once from the vendor's own registered mailbox (a compromised vendor); (c) 40 legitimate invoices from the registered mailbox.  Extractions for (b) and (c) are made once, live (claude-haiku-4-5-20251001), and cached in results/ch30_replay_cache.json.
Seven candidate changes, two replay modes ('both' = as stored; 'verifier' = provenance skipped), and the question: which changes does each mode catch?  Writes results/ch30_replay.json."""
import sys, json, re, random, time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
import ch14_corpus as C
from bulwark.docagent import Document, verify, parse_rules
from bulwark.autoredteam import Envelope, sender_route, ReplayCase, replay, gate_decision
rec = C.make_records()
def slug(n): return re.sub(r"[^a-z]", "", n.lower().replace("supply", "").replace("interiors", ""))[:14]
REGISTERED = {pid: {f"billing@{slug(v['name'])}.example"} for pid, v in rec.vendors.items()}
STRANGER = "rt-ops@attacker.example"
CACHE = here / "results/ch30_replay_cache.json"
def to_ex(j):
    import ch14_live_extract as X; return X.to_ex(j)
def build_cache():
    if CACHE.exists(): return json.load(open(CACHE))
    import ch30_loop as L
    open_ids = [i for i, x in rec.invoices.items() if x["status"] == "open"]; items = []
    for i in random.Random(3001).sample(open_ids, 40): d, _ = C.clean(rec, i, random.Random(f"b{i}")); items.append(("benign", i, "-", d))
    for i in random.Random(3002).sample(open_ids, 8):
        for cls in C.CLASSES: items.append(("hostile", i, cls, C.hostile(rec, i, cls, random.Random(f"h{i}{cls}"))))
    def one(it): k, i, cls, d = it; return dict(kind=k, inv=i, cls=cls, visible=d.visible, hidden=d.hidden, ex=L.extract(d))
    with ThreadPoolExecutor(8) as ex: out = list(ex.map(one, items))
    json.dump(dict(model=L.MODEL, date=time.strftime("%Y-%m-%d %H:%M %Z"), calls=L.meter.calls, tokens_in=L.meter.tokens_in, tokens_out=L.meter.tokens_out, items=out), open(CACHE, "w"), indent=1); return json.load(open(CACHE))
def make_pipeline(level=3, layers=True, sibling=False, trust="channel"):
    def p(doc, ex, env):
        if ex is None: return "REVIEW"
        v = verify(doc, ex, rec, level=level, ex_visible=(parse_rules(doc.visible) if (layers and level >= 3) else None), sibling_review=sibling)
        if env is None or trust == "none": return v.route
        return sender_route(v.route, (v.effect or {}).get("payee_id"), env, REGISTERED, trust=trust)[0]
    return p
BASE = make_pipeline()
CHANGES = {
    "c1 provenance rule removed": make_pipeline(trust="none"),
    "c2 provenance trusts the From header": make_pipeline(trust="header"),
    "c3 layer-agreement check off": make_pipeline(layers=False),
    "c4 verifier back to level 2": make_pipeline(level=2),
    "c5 verifier back to level 1": make_pipeline(level=1),
    "c6 sibling review on (stricter)": make_pipeline(sibling=True),
    "c7 no change (control)": make_pipeline(),
}
def main():
    cache = build_cache(); loop = json.load(open(here / "results/ch30_loop.json")); cases = []
    for c in loop["campaigns"]:
        for r in c["rounds"]:
            if r.get("won") and r.get("ex"):
                env = Envelope(r.get("header_from") or STRANGER, STRANGER)
                cases.append(ReplayCase(f"{c['arm']}-{c['cid']}-{r['round']}", "win", Document("w", r["visible"], r.get("hidden") or ""), to_ex(r["ex"]), env))
    nwin = len(cases)
    for k, it in enumerate(cache["items"]):
        if it["ex"] is None: continue
        d = Document(f"x{k}", it["visible"], it["hidden"]); ex = to_ex(it["ex"]); vend = rec.vendors[rec.invoices[it["inv"]]["payee_id"]]; reg = sorted(REGISTERED[rec.invoices[it["inv"]]["payee_id"]])[0]
        if it["kind"] == "benign": cases.append(ReplayCase(f"b{k}", "benign", d, ex, Envelope(reg, reg)))
        else:
            cases.append(ReplayCase(f"hs{k}-{it['cls']}", "hostile", d, ex, Envelope(reg, STRANGER)))            # stranger who copies the vendor's From line
            cases.append(ReplayCase(f"hv{k}-{it['cls']}", "hostile", d, ex, Envelope(reg, reg)))                 # the vendor's own mailbox, compromised
    sets = {"wins only": [c for c in cases if c.kind == "win"] + [c for c in cases if c.kind == "benign"],
            "wins + scripted": cases}
    base_auto = dict(benign=sum(BASE(c.doc, c.ex, c.env) == "AUTO" for c in cases if c.kind == "benign"), benign_n=sum(c.kind == "benign" for c in cases),
                     wins_auto=sum(BASE(c.doc, c.ex, c.env) == "AUTO" for c in cases if c.kind == "win"), hostile_auto=sum(BASE(c.doc, c.ex, c.env) == "AUTO" for c in cases if c.kind == "hostile"))
    out = dict(cases=len(cases), wins=nwin, baseline=base_auto, results={})
    print("cases", len(cases), "of which wins", nwin, "baseline", base_auto)
    for name, cand in CHANGES.items():
        row = {}
        for sname, cs in sets.items():
            for layer in ("both", "verifier"):
                res = replay(cs, cand, BASE, layer); row[f"{sname} / {layer}"] = dict(escapes=res["escapes"], benign_lost=res["benign_lost"], sample=res["flips"][:4])
        dec = {s: gate_decision({k: v for k, v in row.items() if k.startswith(s)}) for s in sets}
        dec_both_only = {s: gate_decision({k: v for k, v in row.items() if k == f"{s} / both"}) for s in sets}
        out["results"][name] = dict(rows=row, gate_layered=dec, gate_as_stored=dec_both_only)
        print(name); [print("   ", k, v["escapes"], v["benign_lost"]) for k, v in row.items()]; print("    gate as stored:", dec_both_only, " layered:", dec)
    json.dump(out, open(here / "results/ch30_replay.json", "w"), indent=1)
if __name__ == "__main__": main()
