"""Chapter 10: human approval that means something.

Effect          the exact thing that will happen: tenant, invoice, payee, amount, destination account, vendor record version.
digest()        SHA-256 over a canonical encoding of the Effect. An approval is for one digest.
ApprovalService opens tickets for held payments, renders the screen from records (never from model text), takes decisions from
                authenticated people under separation-of-duties rules, and signs a Grant bound to the digest.
Grant           (ticket, digest, approver, waived hold families, expiry, nonce) plus an HMAC the agent cannot compute.
Release         recomputes the Effect from the CURRENT records, checks the grant, spends it once, re-runs the gate with the waiver
                and the approver taken from the grant, and only then hands the payment to the Dispatcher.
StandingOrder   a narrow, owner-created exemption for recurring invoices (M7 only), with scope, cap and expiry.
"""
from __future__ import annotations
import hashlib, hmac, json, itertools
from dataclasses import dataclass, field, asdict
from typing import Optional
from .moneypath import MoneyGate, PayRequest, Decision, Dispatcher
from .tenancy import safe_text

def canonical(effect: dict) -> bytes:
    for k, v in effect.items():
        if type(v) not in (int, str): raise ValueError(f"effect field {k} must be int or str")
    return json.dumps(effect, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()

@dataclass(frozen=True)
class Effect:
    tenant: str; invoice_id: str; payee_id: str; amount_cents: int; destination: str; vendor_version: int; currency: str = "USD"
    def d(self) -> dict: return asdict(self)
    def digest(self) -> str: return hashlib.sha256(canonical(self.d())).hexdigest()

HOLD_PHRASES = {   # fixed text per hold family: the screen never uses model words to explain a hold
    "M3_document_amount_differs_from_books": "The amount printed on the document differs from the amount in your books.",
    "M3_document_amount_not_found": "The amount on the document could not be read.",
    "M4_bank_change_pending": "A change of bank details for this vendor is waiting for confirmation. This payment goes to the account already on file.",
    "M4_account_not_yet_seasoned": "This vendor's bank details changed recently.",
    "M4_account_never_confirmed": "This vendor's bank details were never confirmed by call-back.",
    "M5_payee_daily_count": "This vendor has already been paid today.",
    "M5_payee_daily_cents": "Payments to this vendor today are above the daily limit.",
    "M5_tenant_daily_cap": "Total payments today are above the daily cap.",
    "M6_new_payee": "This vendor was added recently.",
    "M7_likely_duplicate": "This looks like an invoice you already paid.",
    "M8_dual_control_missing": "A second person must approve payments of this size.",
}
QUEUES = {"callback": ("M4_",), "dual": ("M8_",)}
def route(codes: list) -> str:
    """Which queue a held payment goes to. Bank-detail codes go to the call-back queue (a person who phones a number from the vendor master); the dual-control code goes to a second approver; the rest to the general review queue."""
    fams = [family(c) for c in codes]
    if any(f.startswith("M4_") for f in fams): return "callback"
    if any(f.startswith("M8_") for f in fams): return "dual"
    return "review"
def family(code: str) -> str: return code.split("_of_")[0]

@dataclass
class Person:
    pid: str; name: str; limit_cents: int = 0; can_edit_vendors: bool = False

@dataclass
class Ticket:
    tid: str; effect: Effect; digest: str; codes: list; requester: str; created_day: int; expires_day: int; state: str = "open"
    note: Optional[str] = None            # the agent's note, untrusted display text

@dataclass(frozen=True)
class Grant:
    tid: str; digest: str; approver: str; waived: tuple; expires_day: int; nonce: str; mac: str
    def body(self) -> bytes: return f"{self.tid}|{self.digest}|{self.approver}|{','.join(self.waived)}|{self.expires_day}|{self.nonce}".encode()

@dataclass
class Refusal:
    reason: str

class ApprovalService:
    def __init__(self, key: bytes, people: dict[str, Person], tenant: str, ticket_days: int = 3, grant_days: int = 1):
        self._key, self.people, self.tenant = key, people, tenant
        self.sessions: dict[str, str] = {}          # session token -> person id (human sessions only)
        self.tickets: dict[str, Ticket] = {}; self.spent: set[str] = set(); self._n = itertools.count(1)
        self.ticket_days, self.grant_days = ticket_days, grant_days; self.log: list[dict] = []
        self.show_previous = False                    # Chapter 13: True shows the previous account beside the new one and names the invoice a duplicate hold refers to (False keeps the Chapter 10 screen, so its tables reproduce)
        self.sanitise = True                          # Chapter 11: every attacker-writable string passes safe_text before it is drawn
        self.pending_change_authors: dict[str, str] = {}    # payee id -> person id who requested the pending bank change
    def _mac(self, g: Grant) -> str: return hmac.new(self._key, g.body(), hashlib.sha256).hexdigest()
    def login(self, token: str, pid: str, day: int, ttl: int = 1): self.sessions[token] = (pid, day + ttl)
    # --- tickets ---
    def open_ticket(self, req: PayRequest, dec: Decision, vendors, note: Optional[str] = None) -> Ticket:
        assert dec.outcome == "HOLD", "only a HOLD becomes a ticket; a DENY has no approval path"
        eff = Effect(self.tenant, req.invoice_id, req.payee_id, req.amount_cents, dec.destination, dec.vendor_version)
        t = Ticket(f"T{next(self._n):05d}", eff, eff.digest(), list(dec.codes), req.principal, req.day, req.day + self.ticket_days, note=note)
        self.tickets[t.tid] = t; self.log.append(dict(ev="ticket_opened", tid=t.tid, digest=t.digest, codes=t.codes)); return t
    # --- the screen ---
    def render(self, t: Ticket, vendors, invoices, ledger, day: int) -> str:
        v = vendors.v[t.effect.payee_id]; inv = invoices[t.effect.invoice_id]
        S = (lambda s, n=80: safe_text(str(s), n)) if self.sanitise else (lambda s, n=80: str(s))
        today = [a for p in vendors.v for _, a, _ in ledger.recent(p, day)]
        pay_today = ledger.recent(t.effect.payee_id, day)
        lines = [f"PAYMENT FOR APPROVAL  ticket {t.tid}",
                 f"Pay        {S(v.name)}  (vendor record v{v.version}, bank account ending {S(t.effect.destination[-4:], 4)})",
                 f"Amount     ${t.effect.amount_cents/100:,.2f} USD",
                 f"Invoice    {S(inv.number or inv.inv_id, 40)}  books ${inv.amount_cents/100:,.2f}, {S(inv.status, 20)}",
                 f"Today      {len(pay_today)} earlier payment(s) to this vendor totalling ${sum(a for _, a, _ in pay_today)/100:,.2f}; all vendors ${sum(today)/100:,.2f}",
                 f"Bank       confirmed by {S(v.confirmed_by or 'nobody', 40)}; live since day {v.live_since}" + ("; CHANGE PENDING" if v.pending else ""),
                 "Why it stopped:"]
        if self.show_previous:
            if v.pending: lines.insert(6, f"Account    on file ends {S(v.account[-4:], 4)}; the change requested (by {S(v.pending.get('source', '?'), 24)}, day {v.pending.get('requested_day')}) would end {S(v.pending['account'][-4:], 4)}")
            elif v.previous_account and v.changed_day is not None and day - v.changed_day <= 30: lines.insert(6, f"Account    now ends {S(v.account[-4:], 4)}; before day {v.changed_day} it ended {S(v.previous_account[-4:], 4)}")
        for c in t.codes:
            if family(c) == "M7_likely_duplicate" and "_of_" in c and self.show_previous:
                old = c.split("_of_", 1)[1]; oi = invoices.get(old)
                lines.append("  - " + HOLD_PHRASES["M7_likely_duplicate"][:-1] + (f": {S(oi.number or oi.inv_id, 40)} (${oi.amount_cents/100:,.2f}, {S(oi.status, 20)})." if oi else "."))
            else: lines.append("  - " + HOLD_PHRASES.get(family(c), "A check held this payment."))
        if t.note: lines += ["Agent's note (written by the assistant, not checked):", "  | " + (S(t.note, 280) if self.sanitise else t.note[:280].replace("\n", " "))]
        lines.append(f"Approving releases this exact payment (digest {t.digest[:12]}). It cannot change the amount or the account.")
        return "\n".join(lines)
    # --- decisions ---
    def decide(self, tid: str, token: str, verdict: str, day: int, callback_ok: bool = False) -> Grant | Refusal:
        t = self.tickets.get(tid)
        if t is None or t.state != "open": return Refusal("no_open_ticket")
        if day > t.expires_day: t.state = "expired"; return Refusal("ticket_expired")
        s = self.sessions.get(token)
        if s is None: return Refusal("no_human_session")          # agent credentials and email replies never appear here
        pid, exp = s
        if day > exp: return Refusal("session_expired")
        who = self.people[pid]
        if pid == t.requester: return Refusal("requester_cannot_approve")
        if t.effect.amount_cents > who.limit_cents: return Refusal("above_approver_authority")
        fams = {family(c) for c in t.codes}
        if self.pending_change_authors.get(t.effect.payee_id) == pid and any(f.startswith("M4") for f in fams): return Refusal("author_of_vendor_change")
        if fams & {"M4_account_not_yet_seasoned", "M4_account_never_confirmed"} and not callback_ok: return Refusal("callback_required")
        if verdict != "approve": t.state = "rejected"; self.log.append(dict(ev="rejected", tid=tid, by=pid)); return Refusal("rejected_by_person")
        g = Grant(tid, t.digest, pid, tuple(sorted(fams)), day + self.grant_days, hashlib.sha256(f"{tid}{pid}{day}".encode()).hexdigest()[:16], "")
        g = Grant(g.tid, g.digest, g.approver, g.waived, g.expires_day, g.nonce, self._mac(g))
        t.state = "approved"; self.log.append(dict(ev="approved", tid=tid, by=pid, digest=t.digest, waived=g.waived)); return g
    def verify(self, g: Grant, effect_now: Effect, day: int) -> tuple[bool, str]:
        if not hmac.compare_digest(g.mac, self._mac(g)): return False, "grant_mac_invalid"
        if day > g.expires_day: return False, "grant_expired"
        if g.nonce in self.spent: return False, "grant_already_spent"
        if effect_now.digest() != g.digest: return False, "effect_changed_since_approval"
        return True, "ok"

class Release:
    """Spend a grant: recompute the effect from current records, verify, spend once, re-run the gate with the grant's waiver and approver."""
    def __init__(self, svc: ApprovalService, gate: MoneyGate, disp: Dispatcher): self.svc, self.gate, self.disp = svc, gate, disp
    def release(self, req: PayRequest, g: Grant) -> tuple[bool, str, Optional[Decision]]:
        ven = self.gate.vendors.v.get(req.payee_id)
        if ven is None: return False, "unknown_payee", None
        eff = Effect(self.svc.tenant, req.invoice_id, req.payee_id, req.amount_cents, ven.account, ven.version)
        ok, why = self.svc.verify(g, eff, req.day)
        if not ok: return False, why, None
        self.svc.spent.add(g.nonce)                                         # spent before the gate runs: a failed release is not retried on the same grant
        r2 = PayRequest(req.invoice_id, req.payee_id, req.amount_cents, doc_amount_cents=req.doc_amount_cents, day=req.day, principal=req.principal, approver=g.approver)
        d = self.gate.check(r2, waived=frozenset(g.waived))
        if d.outcome != "ALLOW": return False, "gate_" + d.outcome.lower() + ":" + ",".join(d.codes), d
        sent, why = self.disp.dispatch(r2, d)
        return sent, why, d

# ---- standing orders: the narrow answer to approval fatigue ------------------------------------------------------
@dataclass(frozen=True)
class StandingOrder:
    payee_id: str; amount_cents: Optional[int]; every_days: Optional[int]; cap_cents: int; created_by: str; expires_day: int
    def covers(self, payee_id: str, amount_cents: int, day: int, last_day: Optional[int]) -> bool:
        if payee_id != self.payee_id or day > self.expires_day or amount_cents > self.cap_cents: return False
        if self.amount_cents is not None and amount_cents != self.amount_cents: return False
        if self.every_days is not None and (last_day is None or abs((day - last_day) - self.every_days) > 1): return False
        return True
