"""Chapter 7: least privilege at runtime.

compute_scope   turns a trusted task request plus trusted records into the narrowest Scope for that task type.
intersect       a role ceiling is applied last and can only narrow.
loadout_kinds   the tool menu the model is shown for a task: the kinds in scope, nothing else.
Session         a two-phase session: once an untrusted document has been read, the scope ratchets down to the act phase.
Lease           mid-task widening requests, decided by policy; narrowing is free, widening is an event.
mine_scope      scope learned from traces (the alternative this chapter argues against as a primary method).
reach           the numbers that say how much authority a scope really holds.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
from .identity import Scope

class ScopeRefused(Exception): pass

@dataclass
class Books:
    """Trusted records. Nothing in here is read from a document the agent processes."""
    payees: dict            # payee_id -> dict(name, domain)
    invoices: dict          # inv_id -> dict(payee_id, amount_cents, status "open"|"paid", due_day)
    customers: dict         # cust_id -> dict(name, domain, overdue)

@dataclass
class TaskRequest:
    task_type: str
    principal: str
    tenant: str
    params: dict = field(default_factory=dict)   # ids only: invoice_id, customer_ids, window_days
    source: str = "user"                         # "user" or "scheduler"

@dataclass
class Ceiling:
    """The role ceiling: the widest scope the principal's role may ever hold. A scope is clamped to it, never extended by it."""
    kinds: list
    payees: Optional[list] = None
    max_cents: Optional[int] = None
    mail_domains: Optional[list] = None

ALL_KINDS = ["query_books", "read_document", "draft_invoice", "send_invoice", "send_email", "initiate_payment"]

def intersect(s: Scope, c: Ceiling) -> Scope:
    """Clamp s to the ceiling. A constraint is only carried when the scope has a kind it governs: payees and max_cents for payments, mail_domains for mail."""
    kinds = [k for k in s.kinds if k in c.kinds]
    pays = "initiate_payment" in kinds; mails = any(k in kinds for k in ("send_email", "send_invoice"))
    payees, mx, md = s.payees, s.max_cents, s.mail_domains
    if pays:
        if c.payees is not None: payees = [p for p in (s.payees if s.payees is not None else c.payees) if p in c.payees]
        if c.max_cents is not None: mx = c.max_cents if mx is None else min(mx, c.max_cents)
    if mails and c.mail_domains is not None:
        md = [d for d in (s.mail_domains if s.mail_domains is not None else c.mail_domains) if d in c.mail_domains]
    return Scope(kinds=kinds, payees=payees, max_cents=mx, mail_domains=md)

TASK_TYPES = ("answer_question", "process_invoice", "pay_invoice", "send_reminders", "reconcile_month", "handle_vendor_email")
SPLIT_TYPES = ("match_bank_lines", "pay_matched")   # reconcile_month split into a reader and an actor (section 7.9)

def compute_scope(req: TaskRequest, books: Books, ceiling: Optional[Ceiling] = None, trust_agent_drafts: bool = False) -> Scope:
    t, p = req.task_type, req.params
    if t == "answer_question":
        s = Scope(kinds=["query_books", "read_document"])
    elif t == "process_invoice":
        # read a vendor document and draft an entry; no payment, no mail
        s = Scope(kinds=["read_document", "query_books", "draft_invoice"])
    elif t == "pay_invoice":
        inv = books.invoices.get(p.get("invoice_id"))
        if inv is None: raise ScopeRefused("unknown invoice")
        if inv["status"] != "open": raise ScopeRefused("invoice is not open")
        if inv.get("origin") == "agent_draft" and not inv.get("confirmed_by") and not trust_agent_drafts:
            raise ScopeRefused("invoice was drafted by an agent and nobody has confirmed it")
        s = Scope(kinds=["query_books", "initiate_payment"], payees=[inv["payee_id"]], max_cents=inv["amount_cents"])
    elif t == "send_reminders":
        cids = p.get("customer_ids") or []
        doms = sorted({books.customers[c]["domain"] for c in cids if c in books.customers and books.customers[c]["overdue"]})
        if not doms: raise ScopeRefused("no overdue customers in the request")
        s = Scope(kinds=["query_books", "draft_invoice", "send_email"], mail_domains=doms)
    elif t == "handle_vendor_email":
        v = books.payees.get(p.get("payee_id"))
        if v is None: raise ScopeRefused("unknown vendor")
        s = Scope(kinds=["read_document", "query_books", "draft_invoice", "send_email"], mail_domains=[v["domain"]])
    elif t == "match_bank_lines":
        s = Scope(kinds=["query_books", "read_document"])
    elif t == "pay_matched":
        ids = p.get("matched_invoice_ids") or []
        inv = [books.invoices[i] for i in ids if i in books.invoices and books.invoices[i]["status"] == "open"]
        if not inv: raise ScopeRefused("no open invoices in the matched list")
        s = Scope(kinds=["query_books", "initiate_payment"], payees=sorted({i["payee_id"] for i in inv}), max_cents=max(i["amount_cents"] for i in inv))
    elif t == "reconcile_month":
        day, win = p.get("today", 0), p.get("window_days", 7)
        due = [i for i in books.invoices.values() if i["status"] == "open" and i["due_day"] <= day + win]
        if not due: raise ScopeRefused("nothing due in the window")
        s = Scope(kinds=["query_books", "read_document", "initiate_payment"], payees=sorted({i["payee_id"] for i in due}), max_cents=max(i["amount_cents"] for i in due))
    else:
        raise ScopeRefused(f"unknown task type {t!r}")
    if ceiling is not None:
        s = intersect(s, ceiling)
        if not s.kinds: raise ScopeRefused("scope empty after role ceiling")
    return s

def normalise(s: Scope) -> Scope:
    """Make absent-because-irrelevant explicit: a scope with no payment kind holds an empty payee list and a zero ceiling, so Scope.within compares like with like."""
    pays = "initiate_payment" in s.kinds; mails = any(k in s.kinds for k in ("send_email", "send_invoice"))
    return Scope(kinds=list(s.kinds), payees=s.payees if pays else [], max_cents=s.max_cents if pays else 0, mail_domains=s.mail_domains if mails else [])

def loadout_kinds(scope: Scope) -> list: return list(scope.kinds)

def admits(scope: Scope, kind: str, payee=None, amount=None, recipient=None) -> bool:
    """The scope check alone (what Verifier does for scope claims), for simulation without signing."""
    if kind not in scope.kinds: return False
    if kind == "initiate_payment":
        if scope.payees is not None and payee not in scope.payees: return False
        if scope.max_cents is not None and (amount or 0) > scope.max_cents: return False
    if kind in ("send_email", "send_invoice") and scope.mail_domains is not None:
        if (recipient or "").rsplit("@", 1)[-1].lower() not in scope.mail_domains: return False
    return True

@dataclass
class PhasePolicy:
    """Per task type: which kinds survive once an untrusted document has been read."""
    act_kinds: dict
    default: tuple = ("query_books",)

DEFAULT_PHASES = PhasePolicy(act_kinds={
    "answer_question": ("query_books",),
    "process_invoice": ("draft_invoice", "query_books"),
    "pay_invoice": ("query_books", "initiate_payment"),
    "send_reminders": ("query_books", "draft_invoice", "send_email"),
    "reconcile_month": ("query_books", "initiate_payment"),
    "handle_vendor_email": ("query_books", "draft_invoice"),
})

class Session:
    """Holds the scope for one task. read_untrusted() is called by the wrapper (never the model) when a document enters context."""
    def __init__(self, req: TaskRequest, scope: Scope, phases: PhasePolicy = DEFAULT_PHASES, ratchet: bool = True):
        self.req, self.scope, self.phases, self.ratchet, self.tainted = req, scope, phases, ratchet, False
        self.events: list[str] = []
    def read_untrusted(self):
        self.tainted = True
        if not self.ratchet: return
        keep = self.phases.act_kinds.get(self.req.task_type, self.phases.default)
        new = Scope(kinds=[k for k in self.scope.kinds if k in keep], payees=self.scope.payees, max_cents=self.scope.max_cents, mail_domains=self.scope.mail_domains)
        if not new.within(self.scope): raise AssertionError("ratchet widened scope")
        dropped = sorted(set(self.scope.kinds) - set(new.kinds))
        if dropped: self.events.append("ratchet dropped " + ",".join(dropped))
        self.scope = new
    def check(self, kind, **kw) -> bool: return admits(self.scope, kind, **kw)

@dataclass
class LeasePolicy:
    mode: str = "human"            # "never" | "auto_within_ceiling" | "human"
    max_requests: int = 3          # per task, then the task is closed
    ceiling: Optional[Ceiling] = None

@dataclass
class LeaseDecision:
    granted: bool
    needs_human: bool
    reason: str

class Lease:
    """A widening request is a request for a different scope, made through the wrapper, decided by policy, and recorded."""
    def __init__(self, scope: Scope, policy: LeasePolicy):
        self.scope, self.policy, self.requests = scope, policy, 0
        self.log: list[dict] = []
    def request(self, wider: Scope, *, reason: str, trusted_origin: bool) -> LeaseDecision:
        self.requests += 1
        if self.requests > self.policy.max_requests: d = LeaseDecision(False, False, "request budget spent")
        elif wider.within(self.scope): d = LeaseDecision(True, False, "not wider")
        elif self.policy.mode == "never": d = LeaseDecision(False, False, "widening disabled")
        elif self.policy.mode == "auto_within_ceiling":
            c = self.policy.ceiling
            ok = c is not None and intersect(wider, c).to_json() == wider.to_json() and wider.within(Scope(kinds=c.kinds, payees=c.payees if "initiate_payment" in wider.kinds else None, max_cents=c.max_cents if "initiate_payment" in wider.kinds else None, mail_domains=c.mail_domains if any(k in wider.kinds for k in ("send_email", "send_invoice")) else None))
            d = LeaseDecision(ok, False, "within ceiling" if ok else "above ceiling")
        else:
            d = LeaseDecision(False, True, "queued for a person")
        self.log.append(dict(n=self.requests, reason=reason, trusted_origin=trusted_origin, granted=d.granted, needs_human=d.needs_human, why=d.reason))
        return d
    def approve(self, wider: Scope, approver: str):
        self.scope = wider
        self.log.append(dict(event="approved", approver=approver))

def mine_scope(traces: list[dict], min_count: int = 1) -> Scope:
    """Scope learned from observed behaviour: every kind, payee and domain seen at least min_count times, ceiling at the largest amount seen."""
    from collections import Counter
    kc, pc, dc, mx = Counter(), Counter(), Counter(), 0
    for t in traces:
        kc[t["kind"]] += 1
        if t.get("payee"): pc[t["payee"]] += 1
        if t.get("recipient"): dc[t["recipient"].rsplit("@", 1)[-1]] += 1
        mx = max(mx, t.get("amount") or 0)
    ok = lambda c: sorted(k for k, n in c.items() if n >= min_count)
    return Scope(kinds=ok(kc), payees=ok(pc) if pc else None, max_cents=mx or None, mail_domains=ok(dc) if dc else None)

def reach(s: Scope, books: Books) -> dict:
    """What the scope can do at most, in the units a reviewer cares about."""
    pay = "initiate_payment" in s.kinds
    payees = (books.payees.keys() if s.payees is None else s.payees) if pay else []
    cap = s.max_cents if s.max_cents is not None else 10**9
    mail = [k for k in ("send_email", "send_invoice") if k in s.kinds]
    doms = None if (s.mail_domains is None and mail) else (s.mail_domains or [])
    return dict(kinds=len(s.kinds), payees=len(list(payees)), per_action_cents=(cap if pay else 0), mail_domains=("any" if doms is None and mail else len(doms or [])),
                irreversible_kinds=len([k for k in s.kinds if k in ("initiate_payment", "send_email", "send_invoice")]))

def make_books(seed: int = 7, n_payees: int = 8, n_invoices: int = 40, n_customers: int = 25) -> Books:
    import random
    r = random.Random(seed)
    names = ["Lone Star Paper Supply", "Riverside Office Interiors", "Capitol Flour Mills", "Zilker Packaging", "Barton Springs Dairy", "Mueller Equipment Leasing", "Pecan Street Utilities", "Hyde Park Cleaning"]
    doms = ["lonestar-paper.example", "riverside-oi.example", "capitolflour.example", "zilkerpack.example", "bsdairy.example", "mueller-lease.example", "pecanst-util.example", "hydeparkclean.example"]
    ids = ["payee_lone_star", "payee_riverside", "payee_capitol", "payee_zilker", "payee_bsdairy", "payee_mueller", "payee_pecan", "payee_hydepark"]
    payees = {ids[i]: dict(name=names[i], domain=doms[i]) for i in range(n_payees)}
    invs = {}
    for k in range(n_invoices):
        invs[f"INV-{1000 + k}"] = dict(payee_id=r.choice(ids[:n_payees]), amount_cents=r.randrange(8_000, 249_000, 100), status="open" if r.random() < 0.8 else "paid", due_day=r.randrange(1, 45))
    cust = {f"cust_{k:02d}": dict(name=f"Customer {k:02d}", domain=f"cust{k:02d}.example", overdue=r.random() < 0.5) for k in range(n_customers)}
    return Books(payees, invs, cust)

class SpendMeter:
    """Magnitude over the whole task. cap_cents bounds the sum; invoice_ids (optional) bind each payment to an open invoice, once, at its exact amount."""
    def __init__(self, cap_cents: int, invoices: Optional[dict] = None):
        self.cap, self.spent, self.invoices, self.paid = cap_cents, 0, invoices, set()
    def try_pay(self, amount_cents: int, invoice_id: Optional[str] = None, payee: Optional[str] = None) -> tuple[bool, str]:
        if self.invoices is not None:
            inv = self.invoices.get(invoice_id)
            if inv is None: return False, "invoice not in this task"
            if invoice_id in self.paid: return False, "invoice already paid in this task"
            if inv["amount_cents"] != amount_cents or inv["payee_id"] != payee: return False, "amount or payee differs from the invoice"
        if self.spent + amount_cents > self.cap: return False, "task total exceeded"
        self.spent += amount_cents
        if invoice_id is not None: self.paid.add(invoice_id)
        return True, "ok"

@dataclass
class ReadScope:
    """Which fields a read kind may return for a task type. A field outside the list is not returned, whatever the query asked for."""
    tables: dict            # table -> list of allowed columns

READ_SCOPES = {
    "answer_question":     ReadScope({"invoices": ["inv_id", "payee_id", "amount_cents", "status", "due_day"], "payees": ["payee_id", "name"], "customers": ["cust_id", "name", "overdue"]}),
    "process_invoice":     ReadScope({"invoices": ["inv_id", "payee_id", "amount_cents", "status"], "payees": ["payee_id", "name"]}),
    "pay_invoice":         ReadScope({"invoices": ["inv_id", "payee_id", "amount_cents", "status"]}),
    "send_reminders":      ReadScope({"invoices": ["inv_id", "amount_cents", "due_day"], "customers": ["cust_id", "name", "domain", "overdue"]}),
    "reconcile_month":     ReadScope({"invoices": ["inv_id", "payee_id", "amount_cents", "status", "due_day"], "payees": ["payee_id", "name"], "bank_lines": ["line_id", "amount_cents", "ref"]}),
    "handle_vendor_email": ReadScope({"invoices": ["inv_id", "payee_id", "amount_cents", "status"], "payees": ["payee_id", "name", "domain"]}),
}

def read_filter(task_type: str, table: str, columns: list) -> tuple[list, list]:
    """Returns (allowed_columns, refused_columns) for a requested read."""
    rs = READ_SCOPES.get(task_type)
    allowed = rs.tables.get(table, []) if rs else []
    return [c for c in columns if c in allowed], [c for c in columns if c not in allowed]
