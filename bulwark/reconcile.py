"""Chapter 15: the reconciliation flow. A document (invoice) goes through the controls of Part II in the order the data meets them:
   extract (rules, a model, or an obedient stand-in)  ->  V verify against records (Ch14)  ->  G money gate (Ch8)  ->  dispatch with D recheck (Ch8, Ch10)  ->  evidence event at every step (Ch13).
A change of bank details that a document asks for is handled by R (Ch7/Ch8): recorded as pending, never applied from a document. T is the tenant line (Ch11): the books the flow can see are its own tenant's.
Five switches (V, G, R, D, T) exist so that the workshop can remove one control at a time and count what gets through. All on is the product."""
from __future__ import annotations
import re, copy, hashlib
from dataclasses import dataclass, field
from typing import Optional, Callable
from bulwark.docagent import Document, Extraction, Records, parse_rules, verify, norm
from bulwark.moneypath import Vendors, Vendor, Invoice, PayRequest, MoneyGate, Ledger, Decision, idem_key, DOC_NOT_FOUND
from bulwark.evidence import Vault
from bulwark.failclosed import hard_money

CHANGE = re.compile(r"(?i)(receiving account is now|bank (details|has) changed|new bank|account (has )?changed|bank_account field)")
OBEY = [re.compile(r"receiving account is now (US-ACC-\d+)"), re.compile(r"bank_account field for this document is (US-ACC-\d+)")]

def parse_obedient(text: str) -> Extraction:
    """A stand-in for a reader that takes a plausible administrative note as fact (Table 14.11: 59 of 60 and 60 of 60). Deterministic. It is NOT a model; the live lab of this chapter uses the real one."""
    e = parse_rules(text)
    for p in OBEY:
        m = p.search(text)
        if m: e.account = m.group(1)
    return e

def books_from(rec: Records, limit_cents=1_000_000):
    vs = {p: Vendor(p, v["name"], v["account"], limit_cents, live_since=-300, created_day=-365, confirmed_by="nina") for p, v in rec.vendors.items()}
    inv = {i: Invoice(i, x["payee_id"], x["amount_cents"], x["status"], x["number"]) for i, x in rec.invoices.items()}
    return Vendors(vs), inv

def records_view(vendors: Vendors, invoices: dict) -> Records:
    """The Chapter 14 Records interface over the live books, so verification always reads what the gate reads."""
    r = Records({p: dict(name=v.name, account=v.account) for p, v in vendors.v.items()}, {i: dict(payee_id=x.payee_id, number=x.number, amount_cents=x.amount_cents, status=x.status) for i, x in invoices.items()})
    return r

@dataclass
class Result:
    doc_id: str; route: str = ""; outcome: str = ""; codes: list = field(default_factory=list); sent: Optional[tuple] = None; effect: Optional[dict] = None; req: Optional[PayRequest] = None; dec: Optional[Decision] = None

class Flow:
    def __init__(self, tenant: str, books: dict, vault: Vault, V=True, G=True, R=True, D=True, T=True, extractor: Callable = parse_rules, record: bool = True):
        """books: {tenant: (Vendors, invoices)}. With T off the flow sees every tenant's books merged."""
        self.tenant, self.books, self.vault, self.V, self.G, self.R, self.D, self.T, self.extract, self.record = tenant, books, vault, V, G, R, D, T, extractor, record
        self.vendors, self.invoices = books[tenant]
        if not T:
            vs = {}; inv = {}
            for t, (v, i) in books.items(): vs.update(v.v); inv.update(i)
            self.vendors, self.invoices = Vendors(vs), inv
        self.ledger = Ledger(); self.gate = MoneyGate(tenant, self.vendors, self.invoices, self.ledger, tenant_daily_cap=10**9, payee_daily_cents=10**9, payee_daily_count=5)
        self.sent: list = []; self.decisions = 0; self.events = 0; self.queue: list = []
    # ---- evidence: one event per decision, in the path of the decision ----
    def ev(self, **f):
        self.decisions += 1
        if self.record: self.vault.record(self.tenant, ts=f.pop("ts", 0), principal="prin_emily", **f); self.events += 1
    # ---- the registry change a document asks for ----
    def note_change(self, doc: Document, ex: Extraction, day: int):
        if not (ex.account and CHANGE.search(doc.text_layer)): return None
        cand = [p for p, v in self.vendors.v.items() if norm(v.name) in norm(ex.vendor or "")]
        if len(cand) != 1: return None
        p = cand[0]; v = self.vendors.v[p]
        if ex.account == v.account: return None
        if self.R: self.vendors.request_change(p, ex.account, day, "document"); self.ev(kind="registry", tool="vendor_change", decision="PENDING", reasons=["CHANGE_REQUEST_FROM_DOCUMENT"], ts=day)
        else:
            v.previous_account, v.account, v.version, v.confirmed_by = v.account, ex.account, v.version + 1, "document"; self.ev(kind="registry", tool="vendor_change", decision="APPLIED", reasons=["CHANGE_APPLIED_FROM_DOCUMENT"], ts=day)
        return p
    # ---- the flow, in three stages so that a race and a stale decision can be staged ----
    def run(self, docs: list, day: int = 100, between: Optional[Callable] = None) -> list:
        res = []; rec = None
        for d in docs:
            r = Result(d.doc_id); res.append(r); ex = self.extract(d.text_layer); self.note_change(d, ex, day)
            rec = records_view(self.vendors, self.invoices)
            v = verify(d, ex, rec, level=3 if self.V else 0, ex_visible=self.extract(d.visible) if self.V else None)
            r.route, r.codes, r.effect = v.route, list(v.reasons), v.effect
            self.ev(kind="document", tool="read_invoice", extractor="x", confidence=int(ex.confidence), route=v.route, decision=v.route, reasons=(v.reasons[:6] or ["ok"]), ts=day)
            if v.route != "AUTO": r.outcome = "stopped_" + v.route.lower(); continue
            e = v.effect; amt = e["amount_cents"]
            r.req = PayRequest(e["invoice_id"], e["payee_id"], amt, doc_amount_cents=(ex.amount_cents if ex.amount_cents is not None else DOC_NOT_FOUND), day=day)
        for r in res:
            if r.req is None: continue
            if self.G: r.dec = hard_money(self.gate, r.req)
            else:
                ven = self.vendors.v.get(r.req.payee_id); r.dec = Decision("ALLOW", ["gate_off"], r.effect["destination"], idem_key(self.tenant, r.req.invoice_id, r.req.payee_id, r.req.amount_cents), ven.version if ven else None)
            self.ev(kind="gate", tool="pay_invoice", decision=r.dec.outcome, reasons=[c[:48] for c in r.dec.codes[:6]], ts=day)
            if r.dec.outcome != "ALLOW": r.outcome = "gate_" + r.dec.outcome.lower(); r.codes = r.dec.codes; (self.queue.append(r) if r.dec.outcome == "HOLD" else None)
        if between: between(self)
        for r in res:
            if r.dec is None or r.dec.outcome != "ALLOW": continue
            ok, why = self._dispatch(r); r.outcome = "sent" if ok else "dispatch_blocked:" + why
            self.ev(kind="dispatch", tool="pay_invoice", decision="SENT" if ok else "BLOCKED", reasons=[why.replace(" ", "_")[:48]], ts=day)
        return res
    def _dispatch(self, r: Result):
        q, d = r.req, r.dec; ven = self.vendors.v.get(q.payee_id); inv = self.invoices.get(q.invoice_id)
        if self.D:
            if ven and d.vendor_version is not None and (ven.version != d.vendor_version or ven.account != d.destination or ven.pending): self.ledger.release(d.key); return False, "vendor record changed since decision"
            if inv is None or inv.status != "open" or inv.amount_cents != q.amount_cents: self.ledger.release(d.key); return False, "invoice not open or changed"
        r.sent = (q.invoice_id, d.destination, q.amount_cents); self.sent.append(r.sent)
        if inv: inv.status = "paid"
        self.ledger.settle(d.key); return True, "sent"
