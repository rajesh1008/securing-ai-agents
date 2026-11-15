"""Chapter 10: creating a standing order is itself a held action.

OrderProposal   what is being asked for: payee, amount (or none), cadence, cap, expiry, and who proposed it.
OrderService    renders the proposal from the fields (never from free text), takes a decision only from an authenticated
                person other than the proposer whose authority covers the cap, binds the decision to the digest of the
                proposal, and activates exactly that order. Anything that changes after approval does not activate.
Limits that need no model: a cap above MAX_CAP_CENTS, an expiry beyond MAX_DAYS, or a missing amount and cadence together
(payee-wide scope) are refused for every proposer.
"""
from __future__ import annotations
import hashlib, hmac, json
from dataclasses import dataclass, asdict
from typing import Optional
from .approval import StandingOrder, ApprovalService, Refusal
from .tenancy import safe_text

MAX_CAP_CENTS = 500_000
MAX_DAYS = 400

@dataclass(frozen=True)
class OrderProposal:
    payee_id: str; amount_cents: Optional[int]; every_days: Optional[int]; cap_cents: int; expires_day: int; proposed_by: str
    def digest(self) -> str:
        return hashlib.sha256(json.dumps(asdict(self), sort_keys=True, separators=(",", ":")).encode()).hexdigest()

class OrderService:
    def __init__(self, approvals: ApprovalService, vendor_names: dict[str, str]):
        self.ap, self.names = approvals, vendor_names
        self.pending: dict[str, OrderProposal] = {}; self.active: list[StandingOrder] = []; self.log: list[dict] = []
    def propose(self, p: OrderProposal, day: int) -> str | Refusal:
        if p.payee_id not in self.names: return Refusal("unknown_payee")
        if p.cap_cents > MAX_CAP_CENTS: return Refusal("cap_above_policy")
        if p.expires_day - day > MAX_DAYS: return Refusal("expiry_above_policy")
        if p.amount_cents is None and p.every_days is None: return Refusal("scope_too_wide")
        if p.amount_cents is not None and p.amount_cents > p.cap_cents: return Refusal("amount_above_cap")
        self.pending[p.digest()] = p; self.log.append(dict(ev="order_proposed", digest=p.digest(), by=p.proposed_by)); return p.digest()
    def render(self, p: OrderProposal) -> str:
        amt = f"exactly ${p.amount_cents/100:,.2f}" if p.amount_cents is not None else "any amount up to the cap"
        cad = f"every {p.every_days} days (plus or minus one)" if p.every_days is not None else "at any time"
        return "\n".join([f"STANDING ORDER FOR APPROVAL  (digest {p.digest()[:12]})",
            f"Payee      {safe_text(self.names[p.payee_id], 60)}", f"Amount     {amt}", f"Cadence    {cad}",
            f"Cap        ${p.cap_cents/100:,.2f} per payment", f"Expires    day {p.expires_day}",
            "Effect     a payment that matches is no longer held for being a likely duplicate. Every other hold still applies."])
    def decide(self, digest: str, shown: OrderProposal, token: str, day: int) -> StandingOrder | Refusal:
        p = self.pending.get(digest)
        if p is None: return Refusal("no_pending_proposal")
        if shown.digest() != digest or p != shown: return Refusal("proposal_changed_since_shown")
        s = self.ap.sessions.get(token)
        if s is None: return Refusal("no_human_session")
        pid, exp = s
        if day > exp: return Refusal("session_expired")
        if pid == p.proposed_by: return Refusal("proposer_cannot_approve")
        if self.ap.people[pid].limit_cents < p.cap_cents: return Refusal("above_approver_authority")
        del self.pending[digest]
        o = StandingOrder(p.payee_id, p.amount_cents, p.every_days, p.cap_cents, pid, p.expires_day)
        self.active.append(o); self.log.append(dict(ev="order_active", digest=digest, by=pid)); return o
