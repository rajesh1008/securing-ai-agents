"""Chapter 8: the money path. Checks that look at one payment against the records, the ledger and the clock.

Vendors        registry of payees with a bank account, a live-since day, a confirmation record and pending change requests.
Ledger         sqlite table with a unique key on invoice id and on idempotency key: reserve() is the atomic claim on an invoice.
PayRequest     what the agent proposes: ids and amounts only. Destination is never a field.
MoneyGate      the checks M1..M9. Returns ALLOW, HOLD (a person decides) or DENY, with reason codes.
Dispatcher     re-checks at dispatch against the state version recorded at decision time.
explain        builds the examiner's sentence list from the evidence rows for one payment.
"""
from __future__ import annotations
import hashlib, sqlite3, threading
from dataclasses import dataclass, field
from typing import Optional

HOLD_DAYS = 5            # a changed bank account may not receive money until it has been live this long
NEW_PAYEE_DAYS = 14      # first payments to a payee created inside this window go to a person
DUAL_CONTROL_CENTS = 200_000
LIKELY_DUP_WINDOW = 10   # days: same payee and same amount under a different invoice number
DOC_NOT_FOUND = -1       # Chapter 9: sentinel passed by the wrapper when the document parser found no amount; M3 holds on it

@dataclass
class Vendor:
    payee_id: str; name: str; account: str; limit_cents: int
    live_since: int = 0              # day the current account became usable
    created_day: int = -365
    confirmed_by: Optional[str] = None
    pending: Optional[dict] = None   # {"account":..., "requested_day":..., "source":...}; never used for payment
    version: int = 1                 # bumps on any change to the record
    previous_account: Optional[str] = None   # the account before the last confirmed change (Chapter 13: shown beside the new one on the approval screen)
    changed_day: Optional[int] = None

class Vendors:
    def __init__(self, vendors: dict[str, Vendor]): self.v = vendors
    def request_change(self, payee_id: str, new_account: str, day: int, source: str):
        """Any request, from any source, is only recorded. It cannot change where money goes."""
        self.v[payee_id].pending = dict(account=new_account, requested_day=day, source=source)
    def reject_change(self, payee_id: str):
        """The call-back failed or the vendor denies sending it: the pending record is discarded and the account is untouched."""
        self.v[payee_id].pending = None
    def confirm_change(self, payee_id: str, day: int, confirmer: str, callback_ok: bool):
        """A named person, after a call-back to a number held on file, activates the pending account. live_since starts now."""
        r = self.v[payee_id]
        if not r.pending or not callback_ok: return False
        r.previous_account, r.changed_day = r.account, day
        r.account, r.live_since, r.confirmed_by, r.pending = r.pending["account"], day, confirmer, None
        r.version += 1
        return True

@dataclass
class Invoice:
    inv_id: str; payee_id: str; amount_cents: int; status: str = "open"; number: str = ""; confirmed: bool = True

@dataclass
class PayRequest:
    invoice_id: str; payee_id: str; amount_cents: int
    doc_amount_cents: Optional[int] = None      # amount parsed from the document by code, never by the model
    day: int = 0; principal: str = "prin_emily"; approver: Optional[str] = None
    vendor_version: Optional[int] = None

@dataclass
class Decision:
    outcome: str                      # ALLOW | HOLD | DENY
    codes: list = field(default_factory=list)
    destination: Optional[str] = None
    key: Optional[str] = None
    vendor_version: Optional[int] = None

def idem_key(tenant: str, invoice_id: str, payee_id: str, amount_cents: int) -> str:
    return hashlib.sha256(f"{tenant}|{invoice_id}|{payee_id}|{amount_cents}".encode()).hexdigest()[:20]

class Ledger:
    """Payments the tenant has made or reserved. The unique constraints do the work a race would otherwise undo."""
    def __init__(self):
        self.db = sqlite3.connect(":memory:", check_same_thread=False); self.lock = threading.Lock()
        self.db.execute("create table pay(key text primary key, invoice_id text unique, payee_id text, amount_cents int, day int, state text, account text)")
    def reserve(self, key, invoice_id, payee_id, amount_cents, day, account) -> bool:
        with self.lock:
            try:
                self.db.execute("insert into pay values(?,?,?,?,?,?,?)", (key, invoice_id, payee_id, amount_cents, day, "reserved", account)); self.db.commit(); return True
            except sqlite3.IntegrityError: return False
    def release(self, key):
        with self.lock: self.db.execute("delete from pay where key=? and state='reserved'", (key,)); self.db.commit()
    def settle(self, key):
        with self.lock: self.db.execute("update pay set state='settled' where key=?", (key,)); self.db.commit()
    def recent(self, payee_id, since_day):
        with self.lock: return self.db.execute("select invoice_id, amount_cents, day from pay where payee_id=? and day>=?", (payee_id, since_day)).fetchall()
    def count(self):
        with self.lock: return self.db.execute("select count(*) from pay").fetchone()[0]

@dataclass
class MoneyGate:
    tenant: str; vendors: Vendors; invoices: dict; ledger: Ledger
    tenant_daily_cap: int = 600_000
    payee_daily_count: int = 2
    payee_daily_cents: int = 500_000
    def _dup_like(self, r: PayRequest, inv: Invoice):
        for iid, amt, day in self.ledger.recent(r.payee_id, r.day - LIKELY_DUP_WINDOW):
            if iid != r.invoice_id and amt == r.amount_cents: return iid
        return None
    def check(self, r: PayRequest, reserve: bool = True, waived: frozenset = frozenset()) -> Decision:
        """waived: hold-code families a valid, unspent approval grant covers (Chapter 10). A DENY code is never waivable."""
        deny, hold = [], []
        inv = self.invoices.get(r.invoice_id); ven = self.vendors.v.get(r.payee_id)
        if inv is None: return Decision("DENY", ["M1_unknown_invoice"])
        if ven is None: return Decision("DENY", ["M1_unknown_payee"])
        if not inv.confirmed: deny.append("M1_invoice_not_confirmed")
        if inv.payee_id != r.payee_id: deny.append("M1_payee_differs_from_invoice")
        if inv.status != "open": deny.append("M2_invoice_not_open")
        if inv.amount_cents != r.amount_cents: deny.append("M3_amount_differs_from_books")
        if r.doc_amount_cents == DOC_NOT_FOUND: hold.append("M3_document_amount_not_found")
        elif r.doc_amount_cents is not None and r.doc_amount_cents != inv.amount_cents: hold.append("M3_document_amount_differs_from_books")
        if r.amount_cents > ven.limit_cents: deny.append("M5_over_payee_limit")
        # bank account
        if ven.pending: hold.append("M4_bank_change_pending")
        if r.day - ven.live_since < HOLD_DAYS and ven.live_since > ven.created_day: hold.append("M4_account_not_yet_seasoned")
        if ven.confirmed_by is None and ven.live_since > ven.created_day: hold.append("M4_account_never_confirmed")
        if r.day - ven.created_day < NEW_PAYEE_DAYS: hold.append("M6_new_payee")
        # velocity
        rec = self.ledger.recent(r.payee_id, r.day)
        if len(rec) >= self.payee_daily_count: hold.append("M5_payee_daily_count")
        if sum(a for _, a, _ in rec) + r.amount_cents > self.payee_daily_cents: hold.append("M5_payee_daily_cents")
        day_total = sum(a for p in self.vendors.v for _, a, _ in self.ledger.recent(p, r.day))
        if day_total + r.amount_cents > self.tenant_daily_cap: hold.append("M5_tenant_daily_cap")
        like = self._dup_like(r, inv)
        if like: hold.append(f"M7_likely_duplicate_of_{like}")
        if r.amount_cents >= DUAL_CONTROL_CENTS and (r.approver is None or r.approver == r.principal): hold.append("M8_dual_control_missing")
        hold = [h for h in hold if h.split('_of_')[0] not in waived]
        if deny: return Decision("DENY", deny + hold)
        key = idem_key(self.tenant, r.invoice_id, r.payee_id, r.amount_cents)
        if hold: return Decision("HOLD", hold, ven.account, key, ven.version)
        if reserve and not self.ledger.reserve(key, r.invoice_id, r.payee_id, r.amount_cents, r.day, ven.account):
            return Decision("DENY", ["M2_invoice_already_reserved_or_paid"], None, key)
        return Decision("ALLOW", ["ok"], ven.account, key, ven.version)

class Dispatcher:
    """Last step before the rail. The decision is stale if the vendor record or the invoice changed after it was made."""
    def __init__(self, gate: MoneyGate, recheck: bool = True): self.g, self.recheck, self.sent = gate, recheck, []
    def dispatch(self, r: PayRequest, d: Decision) -> tuple[bool, str]:
        if d.outcome != "ALLOW": return False, "not allowed"
        ven = self.g.vendors.v[r.payee_id]; inv = self.g.invoices[r.invoice_id]
        if self.recheck:
            if ven.version != d.vendor_version or ven.account != d.destination or ven.pending: self.g.ledger.release(d.key); return False, "vendor record changed since decision"
            if inv.status != "open" or inv.amount_cents != r.amount_cents: self.g.ledger.release(d.key); return False, "invoice changed since decision"
        self.sent.append((r.invoice_id, d.destination, r.amount_cents)); self.g.ledger.settle(d.key); inv.status = "paid"
        return True, "sent"

def explain(rows: list[dict]) -> list[str]:
    """One sentence per fact, each tied to an evidence row id. Missing facts produce a gap line, never an inference."""
    need = ["task_token", "invoice_binding", "money_gate", "destination_source", "dispatch"]
    by = {r["step"]: r for r in rows}; out = []
    for s in need:
        if s in by: out.append(f"[{by[s]['id']}] {by[s]['text']}")
        else: out.append(f"[gap] no evidence row for step {s}")
    return out
