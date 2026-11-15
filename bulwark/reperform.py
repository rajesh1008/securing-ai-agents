"""Chapter 48: the auditor's re-performance. Written to share no code with the writer side: the chain check is re-implemented here, the decision is replayed against records the auditor holds, and every claim in the evidence is tied to a second source.
Sources the auditor holds besides the exported rows: APPROVALS (the approval service's own log), BANK (the bank statement), MASTER (the vendor-master history), POLICIES (released policy versions).
Each procedure returns findings: (code, seq or None, text). An empty list is a pass for that procedure only."""
from __future__ import annotations
import hashlib, json, math
from dataclasses import dataclass

GENESIS = "0" * 64
def _h(row: dict) -> str:
    body = {k: v for k, v in row.items() if k != "hash"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()

def p1_chain(rows: list[dict]) -> list[tuple]:
    f, prev = [], GENESIS
    for i, r in enumerate(rows):
        if r.get("seq") != i: f.append(("P1_SEQ_GAP", i, f"row {i} carries seq {r.get('seq')}")); break
        if r.get("prev") != prev: f.append(("P1_BROKEN_LINK", i, "previous hash does not match")); break
        if _h(r) != r.get("hash"): f.append(("P1_HASH_MISMATCH", i, "row content does not match its hash")); break
        prev = r["hash"]
    return f

def p2_anchor(rows: list[dict], anchors: list[dict], check) -> list[tuple]:
    """check(rows) is the anchor service's own verdict (the auditor has no key); we also require that the last row is covered by an anchor."""
    ok, why = check(rows)
    f = [] if ok else [("P2_ANCHOR_FAIL", None, why)]
    if anchors and max(a["seq"] for a in anchors) < len(rows) - 1: f.append(("P2_TAIL_UNANCHORED", len(rows) - 1, "rows after the last anchor are not covered"))
    return f

def p3_scope(rows: list[dict], tenant: str) -> list[tuple]:
    return [("P3_FOREIGN_ROW", r["seq"], f"row for tenant {r.get('tenant')} in the export for {tenant}") for r in rows if r.get("tenant") != tenant]

def p4_order(rows: list[dict]) -> list[tuple]:
    f, last = [], None
    for r in rows:
        if last is not None and r.get("ts", 0) < last: f.append(("P4_TIME_BACKWARDS", r["seq"], f"ts {r['ts']} after {last}"))
        last = max(last or r.get("ts", 0), r.get("ts", 0))
    return f

def _by_task(rows):
    d: dict = {}
    for r in rows: d.setdefault(r.get("task"), []).append(r)
    return d

def p5_lifecycle(rows: list[dict], policies: set) -> list[tuple]:
    """Every SENT dispatch has, for the same task, an ALLOW from the gate before it, and (above the dual-control line) an approval before that; policy versions are released ones; no invoice is sent twice."""
    f, sent, bt = [], {}, _by_task(rows)
    for r in rows:
        if r["kind"] == "money_gate" and r.get("policy") not in policies: f.append(("P5_UNRELEASED_POLICY", r["seq"], f"policy {r.get('policy')} is not a released version"))
        if r["kind"] != "dispatch" or r.get("decision") != "SENT": continue
        prior = [x for x in bt.get(r.get("task"), []) if x["seq"] < r["seq"]]
        if not any(x["kind"] == "money_gate" and x.get("decision") == "ALLOW" for x in prior): f.append(("P5_SENT_WITHOUT_ALLOW", r["seq"], f"task {r.get('task')} sent with no ALLOW before it"))
        if r.get("amount_cents", 0) >= 200_000 and not any(x["kind"] == "approval" and x.get("decision") == "APPROVE" for x in prior): f.append(("P5_SENT_WITHOUT_APPROVAL", r["seq"], "above the dual-control line with no approval row"))
        if r["invoice"] in sent: f.append(("P5_PAID_TWICE", r["seq"], f"{r['invoice']} already sent at row {sent[r['invoice']]}"))
        sent.setdefault(r["invoice"], r["seq"])
    return f

def p6_separation(rows: list[dict]) -> list[tuple]:
    f, bt = [], _by_task(rows)
    for r in rows:
        if r["kind"] != "approval": continue
        req = next((x for x in bt.get(r.get("task"), []) if x["seq"] < r["seq"] and x["kind"] == "proposal"), None)
        if req and req.get("principal") == r.get("approver"): f.append(("P6_SELF_APPROVAL", r["seq"], f"approver {r.get('approver')} is the requester"))
    return f

def p7_effect(rows: list[dict]) -> list[tuple]:
    f, bt = [], _by_task(rows)
    for r in rows:
        if r["kind"] != "dispatch" or "effect_digest" not in r: continue
        ap = [x for x in bt.get(r.get("task"), []) if x["seq"] < r["seq"] and x["kind"] == "approval"]
        if ap and ap[-1].get("effect_digest") != r["effect_digest"]: f.append(("P7_EFFECT_DIFFERS", r["seq"], "what was dispatched is not what was approved"))
    return f

def p8_second_sources(rows: list[dict], approvals: list[dict], bank: list[dict], keyed) -> list[tuple]:
    """Log to second source: each logged approval and each SENT dispatch has a matching record outside the writer. Second source to log: every bank line has a logged dispatch."""
    f = []
    ap = {(a["task"], a["approver"], a["effect_digest"]) for a in approvals}
    for r in rows:
        if r["kind"] == "approval" and (r.get("task"), r.get("approver"), r.get("effect_digest")) not in ap: f.append(("P8_APPROVAL_NOT_IN_SERVICE_LOG", r["seq"], f"task {r.get('task')}: no matching entry in the approval service"))
    bk = {(b["invoice"], b["amount_cents"]) for b in bank}
    for r in rows:
        if r["kind"] == "dispatch" and r.get("decision") == "SENT" and (r["invoice"], r["amount_cents"]) not in bk: f.append(("P8_SENT_NOT_ON_BANK_STATEMENT", r["seq"], f"{r['invoice']} {r['amount_cents']} has no matching bank line"))
    logged = {(r["invoice"], r["amount_cents"]) for r in rows if r["kind"] == "dispatch" and r.get("decision") == "SENT"}
    for b in bank:
        if (b["invoice"], b["amount_cents"]) not in logged: f.append(("P8_BANK_LINE_NOT_LOGGED", None, f"bank paid {b['invoice']} {b['amount_cents']} with no dispatch row"))
    return f

def p9_replay(rows: list[dict], decide) -> list[tuple]:
    """decide(row) -> outcome the current code gives on the facts the auditor holds for that gate row. A disagreement is a finding in one direction or the other."""
    f = []
    for r in rows:
        if r["kind"] != "money_gate": continue
        want = decide(r)
        if want != r.get("decision"): f.append(("P9_REPLAY_DISAGREES", r["seq"], f"logged {r.get('decision')}, replay gives {want}"))
    return f

def attr_n(tol: float, conf: float = 0.95, dev: int = 0) -> int:
    """Smallest sample size n such that, if the true deviation rate were `tol`, seeing at most `dev` deviations has probability <= 1 - conf."""
    n = max(dev, 1)
    while True:
        if sum(math.comb(n, k) * tol ** k * (1 - tol) ** (n - k) for k in range(dev + 1)) <= 1 - conf: return n
        n += 1

def upper_bound(n: int, dev: int, conf: float = 0.95) -> float:
    """One-sided Clopper-Pearson upper limit for the deviation rate after `dev` deviations in `n`."""
    lo, hi = dev / n, 1.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if sum(math.comb(n, k) * mid ** k * (1 - mid) ** (n - k) for k in range(dev + 1)) > 1 - conf: lo = mid
        else: hi = mid
    return hi
