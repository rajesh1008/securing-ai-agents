#!/usr/bin/env python3
"""Chapter 36, lab 3 (live, Anthropic API).
Part A: what a provider failure looks like to the caller.  Five real failures: a malformed key, a model id that does not exist, an unreachable host, a client timeout of 1 ms, an invalid request (max_tokens 0).  For each: the exception class, status code, time to fail with the SDK's default retries (max_retries=2) and with max_retries=0, and the class degrade.py's table would assign.
Part B: the fallback question.  If the extractor provider is down and the gateway can route to another model, does the verifier route the same documents the same way?  168 documents: 100 benign (cached primary extractions from ch31_stream.json), 8 hostile from that stream, and 60 more hostile (six Chapter 14 classes x 10, built on benign events' invoices; primary extraction made here).  Primary claude-haiku-4-5-20251001; fallback claude-sonnet-4-6 (no refusal-suite verdict, no verifier regression run, i.e. an unreviewed alias).
Per document: route under the primary and under the fallback; AUTO on a hostile document is an escape.  Writes results/ch36_provider_live.json and .log.  Usage: ch36_provider_live.py [A|B|AB]"""
import sys, json, time, random, re
from pathlib import Path
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
from bulwark.quill_lab import load_env
load_env()
import anthropic
import ch14_live_extract as X
import ch31_stream as S
import ch36_faults as F
from bulwark.autoredteam import Meter
PRIMARY, FALLBACK = "claude-haiku-4-5-20251001", "claude-sonnet-4-6"
OUT = here / "results/ch36_provider_live.json"
CLS = ["H1_instruction", "H2_account_swap", "H3_total_inflated", "H3b_consistent_inflate", "H6_hidden_layer", "H7_label_confusion"]
def part_a():
    import os, httpx
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    cases = [("malformed key", dict(api_key="sk-ant-not-a-real-key"), dict(model=PRIMARY, max_tokens=20)),
             ("unknown model id", dict(), dict(model="claude-haiku-9-9", max_tokens=20)),
             ("unreachable host", dict(api_key=key, base_url="http://127.0.0.1:9"), dict(model=PRIMARY, max_tokens=20)),
             ("client timeout 1 ms", dict(api_key=key, timeout=0.001), dict(model=PRIMARY, max_tokens=20)),
             ("invalid request", dict(), dict(model=PRIMARY, max_tokens=0))]
    rows = []
    for name, ck, kw in cases:
        for retries in (2, 0):
            c = anthropic.Anthropic(max_retries=retries, **({"api_key": key} | ck)); t0 = time.time()
            try: c.messages.create(messages=[{"role": "user", "content": "Reply with the word ok."}], **kw); res = ("NO_ERROR", None)
            except Exception as e: res = (type(e).__name__, getattr(e, "status_code", None))
            rows.append(dict(case=name, retries=retries, exc=res[0], status=res[1], seconds=round(time.time() - t0, 2)))
    return rows
def route_of(ex_json, e):
    ex = X.to_ex(ex_json) if ex_json else None
    return F.f_sender(e, F.f_verify(e, ex)) if ex is not None else "REVIEW"
def ask(model, e, doc):
    for a in range(3):
        try:
            m = anthropic.Anthropic(timeout=60.0, max_retries=2).messages.create(model=model, max_tokens=500, system=X.SYS, messages=[{"role": "user", "content": f"<document>\n{doc.text_layer}\n</document>"}])
            txt = "".join(getattr(b, "text", "") for b in m.content); mt = re.search(r"\{.*\}", txt, re.S)
            try: j = json.loads(mt.group(0))
            except Exception: j = None
            return j, m.usage.input_tokens, m.usage.output_tokens
        except Exception: time.sleep(2 + 3 * a)
    return None, 0, 0
def part_b():
    ev = F.EV; V = F.V; r = random.Random(3601)
    benign = r.sample([e for e in ev if not e["hostile"]], 100); host = [e for e in ev if e["hostile"]]
    base = r.sample([e for e in ev if not e["hostile"] and e not in benign], 60)
    docs = []
    for e in benign + host: docs.append(dict(e=e, doc=S.Document(e["id"], e["visible"], e["hidden"]), primary=e["ex"], kind="hostile" if e["hostile"] else "benign", cls=e.get("cls")))
    for k, b in enumerate(base):
        cls = CLS[k % 6]; e = dict(b, id=b["id"] + "h", hostile=True, cls=cls, channel=r.choice(["vendor_mailbox", "stranger"])); d = S.doc_for(V, e)
        docs.append(dict(e=e, doc=S.Document(e["id"], d.visible, d.hidden), primary=None, kind="hostile", cls=cls, truth_id=b["id"]))
    for d in docs:
        d["e"]["visible"], d["e"]["hidden"] = d["doc"].visible, d["doc"].hidden
    m1, m2 = Meter(), Meter()
    need = [d for d in docs if d["primary"] is None]
    with ThreadPoolExecutor(6) as ex:
        for d, (j, a, b) in zip(need, ex.map(lambda d: ask(PRIMARY, d["e"], d["doc"]), need)): d["primary"] = j; m1.add(PRIMARY, a, b)
        for d, (j, a, b) in zip(docs, ex.map(lambda d: ask(FALLBACK, d["e"], d["doc"]), docs)): d["fallback"] = j; m2.add(FALLBACK, a, b)
    for d in docs:
        e = d["e"]; F.BOOKS.invoices.setdefault(e["id"], F.BOOKS.invoices.get(d.get("truth_id", e["id"])))
        d["r_primary"], d["r_fallback"] = route_of(d["primary"], e), route_of(d["fallback"], e)
    return dict(n=len(docs), rows=[dict(id=d["e"]["id"], kind=d["kind"], cls=d["cls"], r_primary=d["r_primary"], r_fallback=d["r_fallback"], primary=d["primary"], fallback=d["fallback"]) for d in docs],
                calls_primary_new=m1.calls, calls_fallback=m2.calls, usd_primary_new=round(m1.usd(), 3), usd_fallback=round(m2.usd(), 3))
if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "AB"; D = json.load(open(OUT)) if OUT.exists() else {}
    if "A" in which: D["A"] = part_a()
    if "B" in which: D["B"] = part_b()
    D["date"] = time.strftime("%Y-%m-%d %H:%M %Z"); OUT.write_text(json.dumps(D, indent=1))
    L = []
    if "A" in D:
        L.append("PART A  provider failure as the caller sees it"); L.append(f"{'case':22s} retries exception                 status seconds")
        for r in D["A"]: L.append(f"{r['case']:22s} {r['retries']:>7d} {r['exc']:28s} {str(r['status']):>6s} {r['seconds']:>7.2f}")
    if "B" in D:
        B = D["B"]; L.append(f"\nPART B  fallback model: {B['n']} documents; new primary calls {B['calls_primary_new']} (${B['usd_primary_new']}), fallback calls {B['calls_fallback']} (${B['usd_fallback']})")
        c = Counter((r["kind"], r["r_primary"], r["r_fallback"]) for r in B["rows"])
        for k in sorted(c): L.append(f"  {k[0]:8s} primary {k[1]:6s} fallback {k[2]:6s} {c[k]:>4d}")
        for kind in ("benign", "hostile"):
            rs = [r for r in B["rows"] if r["kind"] == kind]; L.append(f"  {kind}: n={len(rs)} AUTO primary {sum(r['r_primary']=='AUTO' for r in rs)} AUTO fallback {sum(r['r_fallback']=='AUTO' for r in rs)} no-extraction primary {sum(r['primary'] is None for r in rs)} fallback {sum(r['fallback'] is None for r in rs)}")
    (here / "results/ch36_provider_live.log").write_text("\n".join(L) + "\n"); print("\n".join(L))
