#!/usr/bin/env python3
"""Chapter 36, lab 2 (no model; replays the cached live extractions of ch31_stream.py: 566 documents, 8 hostile).  Every event has three steps: READ (a person can open the document), DRAFT (enter the invoice as a draft) and, when the decision is AUTO, MONEY (queue the payment).
The decision is extractor -> verifier -> sender route.  One dependency at a time fails on EVERY event, in four ways: ERROR (raises), TIMEOUT (answers after the deadline), MALFORMED (answers None), STALE (answers with the previous document's answer, tagged with that document's id).
Three handling styles:
  swallow  try/except around each stage; a failed stage is skipped and the pipeline carries on with what it has (no extraction -> the verifier says REVIEW; no verifier answer -> AUTO, nothing objected; no sender answer -> the verifier's route stands)
  closed   try/except; any failure -> REVIEW and nothing else for that event (no READ, no DRAFT)
  table    guarded() with a deadline and a validator (answer is about THIS document, and is a known route); degrade.default_table decides each step (ALLOW, HOLD, QUEUE, REFUSE)
A TIMEOUT with no deadline (swallow, closed) hangs the call; the harness detects this with a 0.3 s join and records the whole pipeline as HUNG (no event after the first completes).
Writes results/ch36_faults.json and results/ch36_faults.log."""
import sys, json, time
from pathlib import Path
from collections import Counter
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
import ch14_live_extract as X
import ch31_shadow as SH
from bulwark.docagent import Document, Records, verify, parse_rules
from bulwark.autoredteam import Envelope, sender_route
from bulwark.degrade import *
EV, V, REG, STR = SH.EV, SH.V, SH.REG, SH.STRANGER
BOOKS = Records({p: dict(name=v["name"], account=v["account"]) for p, v in V.items()}, {e["id"]: dict(payee_id=e["pid"], number=e["number"], amount_cents=e["amount"], status="open", day=e["day"]) for e in EV})
DEPS = {"extractor": Dependency("extractor", Role.PROVIDE, "eng-lead"), "verifier": Dependency("verifier", Role.PREVENT, "ian"), "sender_route": Dependency("sender_route", Role.PREVENT, "ian")}
DEADLINE, SLOW = 0.02, 0.06
def env_of(e):
    reg = sorted(REG[e["pid"]])[0]; return Envelope(reg, reg if (not e["hostile"] or e["channel"] == "vendor_mailbox") else STR)
def f_extract(e): return X.to_ex(e["ex"]) if e["ex"] else None
def f_verify(e, ex):
    if ex is None: return "REVIEW"
    doc = Document(e["id"], e["visible"], e["hidden"]); return verify(doc, ex, BOOKS, level=3, ex_visible=parse_rules(doc.visible)).route
def f_sender(e, route): return sender_route(route, e["pid"], env_of(e), REG, trust="channel")[0]
class Stage:
    """A real function with an injected fault.  Answers are (document id, answer); STALE returns the previous document's tuple."""
    def __init__(self, fn, fault): self.fn, self.fault, self.last = fn, fault, None
    def __call__(self, e, *a):
        if self.fault == "ERROR": raise ConnectionError("dependency down")
        if self.fault == "HANG": time.sleep(5)
        if self.fault == "TIMEOUT": time.sleep(SLOW)
        if self.fault == "MALFORMED": return None
        fresh = (e["id"], self.fn(e, *a)); out = self.last if (self.fault == "STALE" and self.last) else fresh; self.last = fresh; return out
VALID = {"extractor": lambda e, a: a is not None and a[0] == e["id"], "verifier": lambda e, a: a is not None and a[0] == e["id"] and a[1] in ("AUTO", "REVIEW", "REJECT"), "sender_route": lambda e, a: a is not None and a[0] == e["id"] and a[1] in ("AUTO", "REVIEW", "REJECT")}
def run(style, dep=None, fault=None):
    mk = lambda n, fn: Stage(fn, fault if n == dep else None)
    if fault == "TIMEOUT" and style != "table":
        g = guarded(Stage(f_extract, "HANG"), EV[0], deadline=0.3); assert g.status == "TIMEOUT"
        return dict(style=style, dep=dep, fault=fault, hung=True, hostile_auto=0, benign_auto=0, read=0, draft=0, queued_fault=0, benign_held=0)
    S = dict(extractor=mk("extractor", f_extract), verifier=mk("verifier", f_verify), sender_route=mk("sender_route", f_sender)); c = Counter()
    for e in EV:
        st = {}; ans = {}
        def call(name, *a):
            if style == "table":
                r = guarded(S[name], e, *a, deadline=DEADLINE, validate=lambda x: VALID[name](e, x)); st[name] = r.status; ans[name] = r.value[1] if r.ok else None
            else:
                try: x = S[name](e, *a)
                except Exception: st[name] = "ERROR"; ans[name] = None; return
                st[name] = "OK" if x is not None else "MALFORMED"; ans[name] = x[1] if x is not None else None
        call("extractor"); ex = ans["extractor"]
        if style == "swallow":
            call("verifier", ex); route = ans["verifier"] if st["verifier"] == "OK" else "AUTO"
            if st["extractor"] != "OK": route = "REVIEW" if st["verifier"] == "OK" else route   # no extraction: verifier is handed None
            call("sender_route", route); route = ans["sender_route"] if st["sender_route"] == "OK" else route
            read = draft = True; queued = False
        elif style == "closed":
            if st["extractor"] != "OK": route, read, draft, queued = "REVIEW", False, False, True
            else:
                call("verifier", ex)
                if st["verifier"] != "OK": route, read, draft, queued = "REVIEW", False, False, True
                else:
                    call("sender_route", ans["verifier"])
                    if st["sender_route"] != "OK": route, read, draft, queued = "REVIEW", False, False, True
                    else: route, read, draft, queued = ans["sender_route"], True, True, False
        else:
            if st["extractor"] == "OK": call("verifier", ex)
            else: st["verifier"] = "OK"; ans["verifier"] = None
            if st["verifier"] == "OK" and ans["verifier"] is not None: call("sender_route", ans["verifier"])
            elif st["verifier"] == "OK": st["sender_route"] = "OK"
            else: st["sender_route"] = "OK"
            bad = {k: v for k, v in st.items() if v != "OK"}; route = ans.get("sender_route") if not bad else None
            if "extractor" in bad: route = None
            dm, _ = decide(DEPS, {k: st[k] for k in st}, MONEY); dr, _ = decide(DEPS, {k: st[k] for k in st}, DRAFT); dd, _ = decide(DEPS, {k: st[k] for k in st}, READ)
            read, draft = dd == Disp.ALLOW, dr == Disp.ALLOW; queued = bool(bad)
            if bad and dm == Disp.ALLOW: route = "AUTO"
        c["events"] += 1; c["read"] += read; c["draft"] += draft; c["queued_fault"] += queued
        if route == "AUTO": c["hostile_auto" if e["hostile"] else "benign_auto"] += 1
        elif not e["hostile"] and not queued: c["benign_held"] += 1
    return dict(style=style, dep=dep, fault=fault, hung=False, **{k: c[k] for k in ("hostile_auto", "benign_auto", "read", "draft", "queued_fault", "benign_held")})
if __name__ == "__main__":
    rows = []; t0 = time.time()
    for style in ("swallow", "closed", "table"):
        rows.append(run(style))
        for dep in DEPS:
            for fault in FAULTS: rows.append(run(style, dep, fault))
    n = len(EV); H = sum(e["hostile"] for e in EV); lines = [f"{n} events, {H} hostile; steps per event: READ, DRAFT, MONEY if AUTO; {time.time()-t0:.0f} s"]
    lines.append(f"{'style':8s} {'dependency':13s} {'fault':10s} hostile_AUTO benign_AUTO  READ DRAFT queued_by_fault benign_held hung")
    for r in rows: lines.append(f"{r['style']:8s} {r['dep'] or 'none':13s} {r['fault'] or '-':10s} {r['hostile_auto']:>11d} {r['benign_auto']:>11d} {r['read']:>5d} {r['draft']:>5d} {r['queued_fault']:>15d} {r['benign_held']:>11d} {'HUNG' if r['hung'] else ''}")
    (here / "results/ch36_faults.json").write_text(json.dumps(rows, indent=1)); (here / "results/ch36_faults.log").write_text("\n".join(lines) + "\n"); print("\n".join(lines))
