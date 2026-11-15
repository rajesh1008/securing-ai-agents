"""Chapter 39: explaining one payment to an examiner from the evidence export alone, months later, with nobody from engineering in the room.
  QUESTIONS    fourteen questions an examiner asks about one payment; each names the (kind, field) pairs of typed evidence rows that must exist for the question to be answerable, and the facts an answer must state
  scope()      the rows that belong to one payment: its task, and the vendor-change rows for its payee
  coverage()   question by question: ANSWERABLE, PARTIAL (some needed fields exist) or NOT_IN_EVIDENCE, with what is missing; no model involved
  timeline()   one deterministic sentence per row, built from typed fields only, each carrying its row number
  check()      checks an answer sheet (from a person or a model) against the rows: every answer cites rows in scope, every stated fact appears in a cited row, a question that the evidence cannot answer is not answered, an answerable one is not refused
It cannot tell whether the evidence was true when written (a gate that recorded ALLOW and did something else), whether an answer is complete, or what a free-text note meant; the export carries digests where content was, and the content store is a separate door."""
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class Q:
    id: str; text: str; needs: tuple; facts: tuple = (); scope: str = "task"

QUESTIONS = (
    Q("Q1", "Who or what asked for this payment, under which task?", (("proposal", "principal"), ("proposal", "task")), ("principal", "task")),
    Q("Q2", "Which document did it come from, and what did the extraction step return (confidence, route)?", (("doc_intake", "doc_digest"), ("doc_intake", "confidence"), ("doc_intake", "route")), ("doc_digest", "confidence", "route")),
    Q("Q3", "What invoice, payee and amount were paid?", (("dispatch", "invoice"), ("dispatch", "payee"), ("dispatch", "amount_cents")), ("invoice", "payee", "amount_cents")),
    Q("Q4", "Which control decided on the payment, and with what outcome and reasons at each step?", (("money_gate", "decision"), ("money_gate", "reasons")), ("decision", "reasons")),
    Q("Q5", "Which version of the payment policy was in force?", (("money_gate", "policy"),), ("policy",)),
    Q("Q6", "Did a person have to approve it, who approved, and how long did the approval take?", (("approval", "approver"), ("approval", "approval_ms")), ("approver", "approval_ms")),
    Q("Q7", "Is what the approver approved the same as what was dispatched?", (("approval", "effect_digest"), ("dispatch", "effect_digest")), ("effect_digest",)),
    Q("Q8", "Which version of the vendor record was used to choose the destination account?", (("dispatch", "vendor_version"), ("dispatch", "dest_digest")), ("vendor_version", "dest_digest")),
    Q("Q9", "When did the payee's bank account last change, and who confirmed it?", (("vendor_change", "decision"), ("vendor_change", "approver"), ("vendor_change", "vendor_version")), ("decision", "approver", "vendor_version"), "payee"),
    Q("Q10", "Did the document contain text that tried to instruct the agent, and what was done about it?", (("screen", "markers"), ("screen", "decision")), ("markers", "decision")),
    Q("Q11", "Which agents handled the task, in what order, and what untrusted content had the task read?", (("envelope", "sender"), ("envelope", "receiver"), ("envelope", "taint")), ("sender", "receiver", "taint")),
    Q("Q12", "Which model and which prompt version produced the extraction and the proposal?", (("proposal", "model"), ("proposal", "prompt_version")), ("model", "prompt_version")),
    Q("Q13", "Has the record been altered or truncated since it was written?", (), ("chain_verified",), "chain"),
    Q("Q14", "What exactly did the model see and say?", (("proposal", "content_in_export"),), ("content",)),
)
BY_ID = {q.id: q for q in QUESTIONS}

def scope(rows: list[dict], task: str, payee: str) -> list[dict]:
    return [r for r in rows if r.get("task") == task or (r.get("kind") == "vendor_change" and r.get("payee") == payee)]

def coverage(rows: list[dict], task: str, payee: str, chain_ok: bool, questions=QUESTIONS) -> dict:
    sc = scope(rows, task, payee); out = {}
    for q in questions:
        if q.id == "Q13": out[q.id] = ("ANSWERABLE" if chain_ok else "NOT_IN_EVIDENCE", []); continue
        miss = [f"{k}.{f}" for k, f in q.needs if not any(r.get("kind") == k and f in r for r in sc)]
        have = len(q.needs) - len(miss)
        out[q.id] = ("ANSWERABLE" if not miss else ("PARTIAL" if have else "NOT_IN_EVIDENCE"), miss)
    return out

def timeline(rows: list[dict]) -> list[str]:
    out = []
    for r in rows:
        bits = [f"{k}={v}" for k, v in r.items() if k not in ("tenant", "prev", "hash", "seq", "kind", "ts")]
        out.append(f"[{r['seq']}] day {r.get('ts', '?')}: {r['kind']}: " + "; ".join(bits))
    return out

def _holds(row: dict, fact: str, value) -> bool:
    if fact not in row: return False
    v = row[fact]
    if isinstance(v, list) and not isinstance(value, list): return value in v
    if isinstance(v, list) and isinstance(value, list): return set(map(str, value)) <= set(map(str, v)) or set(map(str, v)) <= set(map(str, value))
    return str(v) == str(value)

def check(sheet: list[dict], rows: list[dict], task: str, payee: str, chain_ok: bool, questions=QUESTIONS) -> list[tuple[str, str]]:
    """sheet: [{"id": "Q3", "status": "ANSWERED"|"NOT_IN_EVIDENCE", "cites": [seq...], "facts": {name: value}}...]"""
    iss = []; sc = {r["seq"]: r for r in scope(rows, task, payee)}; cov = coverage(rows, task, payee, chain_ok, questions); got = {a.get("id"): a for a in sheet}
    for q in questions:
        a = got.get(q.id)
        if a is None: iss.append(("MISSING_QUESTION", q.id)); continue
        status, miss = cov[q.id]; ans = a.get("status") == "ANSWERED"; facts = a.get("facts") or {}
        if ans and status == "NOT_IN_EVIDENCE" and any(v not in (None, "", [], "unknown") for v in facts.values()): iss.append(("ANSWERED_WITHOUT_EVIDENCE", q.id))
        if ans and status == "PARTIAL" and any(f in facts and facts[f] not in (None, "") for f in q.facts) and any(m.split(".")[1] in q.facts and facts.get(m.split(".")[1]) not in (None, "") for m in miss): iss.append(("ANSWERED_BEYOND_EVIDENCE", q.id))
        if not ans and status == "ANSWERABLE": iss.append(("REFUSED_BUT_AVAILABLE", q.id))
        if not ans: continue
        cites = a.get("cites") or []
        if q.id != "Q13" and not cites and status != "NOT_IN_EVIDENCE": iss.append(("NO_CITATION", q.id))
        for c in ([] if q.id == "Q13" else cites):  # Q13 is about the whole chain, not the payment's rows
            if c not in sc: iss.append(("CITED_ROW_NOT_IN_SCOPE", f"{q.id}:{c}"))
        crow = [sc[c] for c in cites if c in sc]
        for f, v in facts.items():
            if f == "chain_verified": continue
            if v in (None, "", [], "unknown"): continue
            if f not in q.facts: iss.append(("FACT_NOT_ASKED", f"{q.id}:{f}")); continue
            vals = v if isinstance(v, list) else [v]
            # a list of values (the hold and then the release, both agents of a hand-off) is supported if every element is held by some cited row
            if not all(any(_holds(r, f, x) for r in crow) for x in vals): iss.append(("FACT_NOT_IN_CITED_ROWS", f"{q.id}:{f}={v}"))
    return iss

def verify_segment(rows: list[dict], anchors: list[dict] | None = None, anchor_key_check=None) -> tuple[bool, str]:
    """Verify a retained segment of a chain (the older rows were purged under the retention rule).  Links and hashes are checked from the first retained row on; the first row's own prev is taken as given and reported.
    If anchors are given, every anchor whose seq lies in the segment must match the row hash at that seq (anchor MACs are the anchor service's to check)."""
    import hashlib
    from bulwark.evidence import canon
    if not rows: return False, "empty segment"
    for i, r in enumerate(rows):
        if hashlib.sha256(canon({k: v for k, v in r.items() if k != "hash"})).hexdigest() != r.get("hash"): return False, f"row {r.get('seq')} hash does not match its content"
        if i and (r.get("prev") != rows[i - 1]["hash"] or r.get("seq") != rows[i - 1]["seq"] + 1): return False, f"link broken at seq {r.get('seq')}"
    by = {r["seq"]: r for r in rows}
    for a in anchors or []:
        if a["seq"] in by and by[a["seq"]]["hash"] != a["head"]: return False, f"anchor mismatch at {a['seq']}"
    for a in anchors or []:
        if a["seq"] > rows[-1]["seq"]: return False, f"truncated: anchor at {a['seq']}, segment ends at {rows[-1]['seq']}"
    inside = [a["seq"] for a in (anchors or []) if a["seq"] in by]
    return True, f"segment seq {rows[0]['seq']}..{rows[-1]['seq']} verifies; first row's prev {rows[0]['prev'][:8]} unchecked; anchors inside: {inside}"
