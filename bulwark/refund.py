"""W-05: refund destination bound to the registry. The destination is never read from the transaction or from the model."""
from __future__ import annotations
from dataclasses import dataclass, field

# Customer registry: account on file, captured at onboarding, not from any transaction.
CUSTOMERS = {
    "cust_barton": {"name": "Barton Creek Plumbing", "account": "GB29NWBK60161331926819"},
    "cust_riverside": {"name": "Riverside Office Interiors", "account": "DE89370400440532013000"},
}
OPEN_INVOICES = {"INV-2001": ("cust_barton", 18000), "INV-2002": ("cust_riverside", 52000)}

@dataclass
class Txn:
    txn_id: str; sender_account: str; amount_cents: int; memo: str

@dataclass
class RefundProposal:
    txn_id: str; customer_id: str; amount_cents: int; destination_account: str | None = None; invoice: str = ""

@dataclass
class Decision:
    allow: bool; reason: str; destination: str | None = None

@dataclass
class RefundGate:
    bound: bool = True
    refunded: set = field(default_factory=set)
    def check(self, p: RefundProposal, t: Txn) -> Decision:
        inv = OPEN_INVOICES.get(p.invoice)
        cust = CUSTOMERS.get(p.customer_id)
        if not self.bound:   # the naive design: refund goes to whoever the transaction or the proposal names
            dest = p.destination_account or t.sender_account
            return Decision(True, "naive: destination taken from proposal or transaction", dest)
        if not cust: return Decision(False, "unknown customer")
        if p.txn_id != t.txn_id: return Decision(False, "proposal does not match transaction")
        if p.txn_id in self.refunded: return Decision(False, "transaction already refunded")
        if not inv or inv[0] != p.customer_id: return Decision(False, "invoice does not belong to customer")
        over = t.amount_cents - inv[1]
        if over <= 0: return Decision(False, "no overpayment on this transaction")
        if p.amount_cents > over: return Decision(False, f"refund exceeds overpayment ({over})")
        if t.sender_account != cust["account"]: return Decision(False, "sender is not the account on file: route to human")
        self.refunded.add(p.txn_id)
        return Decision(True, "ok", cust["account"])   # destination comes from the registry, whatever the proposal said
