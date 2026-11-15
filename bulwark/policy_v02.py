"""Bulwark v0.2: egress allow-list and payee registry carry the decision; markers are advisory only."""
from __future__ import annotations
from .models import ActionProposal, ActionKind, GateDecision, AgentIdentity, Principal
from .policy import BulwarkGate, KNOWN_PAYEES

POLICY_VERSION = "bulwark-v0.2"

# Recipient domains a tenant may mail. Customer domains come from the tenant's own contact book.
TENANT_MAIL_DOMAINS = {"biz_hcb": {"hillcountrybakehouse.example", "ledgerly.example", "lonestarpaper.example"}}

IRREVERSIBLE = {ActionKind.INITIATE_PAYMENT, ActionKind.SEND_EMAIL, ActionKind.SEND_INVOICE}

class BulwarkGateV02(BulwarkGate):
    def __init__(self):
        super().__init__(policy_version=POLICY_VERSION)

    def check(self, proposal: ActionProposal, principal: Principal, agent: AgentIdentity) -> GateDecision:
        base = super().check(proposal, principal, agent)
        reasons = [r for r in base.reasons if r != "ok"]
        advisory = [r for r in reasons if r.startswith("injection marker")]
        hard = [r for r in reasons if not r.startswith("injection marker")]
        checked = list(base.checked_fields)

        if proposal.kind in (ActionKind.SEND_EMAIL, ActionKind.SEND_INVOICE):
            checked.append("egress_allow_list")
            domains = TENANT_MAIL_DOMAINS.get(proposal.business_id, set())
            dom = (proposal.recipient_email or "").rsplit("@", 1)[-1].lower()
            if dom not in domains:
                hard.append(f"recipient domain {dom or '(none)'} not on tenant allow-list")
        if proposal.kind == ActionKind.INITIATE_PAYMENT:
            checked.append("payee_registry_exact")
            reg = KNOWN_PAYEES.get(proposal.payee_id or "")
            if reg and proposal.payee_name and proposal.payee_name != reg["name"]:
                hard.append("payee_name does not match registry name for payee_id")
        # a marker hit on a reversible action is advisory; on an irreversible one it adds a human-review reason
        if advisory and proposal.kind in IRREVERSIBLE:
            hard.append("advisory marker on irreversible action: route to human")
        allow = not hard
        return GateDecision(allow=allow, reasons=(hard or ["ok"]) + [f"advisory: {a}" for a in advisory if allow],
                            policy_version=POLICY_VERSION, checked_fields=checked)
