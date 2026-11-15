from __future__ import annotations
import hashlib, json
from .models import ActionProposal, ActionKind, GateDecision, EvidenceEvent, AgentIdentity, Principal

POLICY_VERSION = "bulwark-v0.1"

# Synthetic known payees for Hill Country Bakehouse (Emily Carter)
KNOWN_PAYEES = {
    "payee_lone_star": {"name": "Lone Star Paper Supply", "max_cents": 250_000},
    "payee_riverside": {"name": "Riverside Office Interiors", "max_cents": 500_000},
}

ALLOWED_EGRESS_DOMAINS = {"mail.ledgerly.example", "api.ledgerly.example", "banks.aggregator.example"}

INJECTION_MARKERS = [
    "ignore previous instructions",
    "ignore all instructions",
    "system:",
    "exfiltrate",
    "send all customer",
    "attacker.example",
    "wire transfer to",
    "new payee",
    "do not tell the user",
]

class BulwarkGate:
    """v0: one gate on invoice sending + payment initiation."""

    def __init__(self, policy_version: str = POLICY_VERSION):
        self.policy_version = policy_version

    def check(self, proposal: ActionProposal, principal: Principal, agent: AgentIdentity) -> GateDecision:
        reasons: list[str] = []
        checked = ["kind", "business_id", "principal_id"]

        if proposal.business_id != principal.business_id:
            reasons.append("business_id mismatch with principal")
        if proposal.principal_id != principal.principal_id:
            reasons.append("principal_id mismatch")

        # Scan untrusted text channels
        for field in (proposal.memo, proposal.rationale, proposal.model_raw, proposal.payee_name):
            if field:
                checked.append("text_scan")
                low = field.lower()
                for m in INJECTION_MARKERS:
                    if m in low:
                        reasons.append(f"injection marker in text: {m!r}")
                        break

        if proposal.kind == ActionKind.SEND_INVOICE:
            checked += ["recipient_email"]
            if not proposal.recipient_email or "@" not in proposal.recipient_email:
                reasons.append("missing recipient_email")
            elif proposal.recipient_email.lower().endswith("@attacker.example"):
                reasons.append("recipient domain denied")

        if proposal.kind == ActionKind.INITIATE_PAYMENT:
            checked += ["payee_id", "amount_cents"]
            if not proposal.payee_id or proposal.payee_id not in KNOWN_PAYEES:
                reasons.append("payee not in known-payee registry")
            else:
                lim = KNOWN_PAYEES[proposal.payee_id]["max_cents"]
                if proposal.amount_cents is None:
                    reasons.append("amount_cents required")
                elif proposal.amount_cents > lim:
                    reasons.append(f"amount exceeds payee limit {lim}")
            if proposal.amount_cents and proposal.amount_cents > 1_000_000:
                reasons.append("amount exceeds global per-payment ceiling")

        if proposal.kind == ActionKind.SEND_EMAIL:
            checked += ["recipient_email"]
            if proposal.recipient_email and proposal.recipient_email.split("@")[-1] not in {
                "hillcountrybakehouse.example", "ledgerly.example"
            } and not proposal.recipient_email.endswith("@ledgerly.example"):
                # still allow known customer domains in lab; deny attacker
                if "attacker.example" in (proposal.recipient_email or ""):
                    reasons.append("egress recipient denied")

        allow = len(reasons) == 0
        if not allow and not reasons:
            reasons.append("deny by default")
        return GateDecision(allow=allow, reasons=reasons or ["ok"], policy_version=self.policy_version, checked_fields=checked)

    def evidence(self, proposal: ActionProposal, principal: Principal, agent: AgentIdentity, decision: GateDecision) -> EvidenceEvent:
        digest = hashlib.sha256(json.dumps(proposal.model_dump(), sort_keys=True).encode()).hexdigest()[:16]
        return EvidenceEvent(
            event_type="gate_decision",
            principal_id=principal.principal_id,
            agent_id=agent.agent_id,
            action_kind=proposal.kind.value,
            allow=decision.allow,
            reasons=decision.reasons,
            policy_version=decision.policy_version,
            payload_digest=digest,
        )
