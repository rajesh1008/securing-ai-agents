"""Chapter 4: classical security principles as small, testable mechanisms.

Mediator       complete mediation: the only code path that can call a tool, and it always asks the gate first.
fail_mode      fail-safe defaults: what happens when the gate itself errors ("closed" denies, "open" lets the action through).
SeparationOfDuties   no single principal may propose and approve the same irreversible action above a threshold.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Optional
from .models import ActionProposal, ActionKind, Principal, AgentIdentity, GateDecision

_TOKEN = object()  # held by the Mediator only; executors refuse any call without it

class MediationError(RuntimeError): pass

class Tool:
    """An executor that can only be invoked with the mediator's token."""
    def __init__(self, name: str, fn: Callable[[ActionProposal], str]):
        self.name, self._fn = name, fn
    def __call__(self, proposal: ActionProposal, *, token=None) -> str:
        if token is not _TOKEN:
            raise MediationError(f"tool {self.name} called outside the mediator")
        return self._fn(proposal)

@dataclass
class MediatedResult:
    executed: bool
    decision: Optional[GateDecision]
    detail: str
    gate_error: Optional[str] = None

class Mediator:
    def __init__(self, gate, tools: dict[ActionKind, Tool], fail_mode: str = "closed"):
        assert fail_mode in ("closed", "open")
        self.gate, self.tools, self.fail_mode = gate, tools, fail_mode
        self.log: list[dict] = []
    def execute(self, proposal: ActionProposal, principal: Principal, agent: AgentIdentity) -> MediatedResult:
        gate_error = None
        try:
            decision = self.gate.check(proposal, principal, agent)
            allow = decision.allow
        except Exception as e:  # the gate is a dependency like any other; it can fail
            decision, allow, gate_error = None, self.fail_mode == "open", f"{type(e).__name__}: {e}"
        tool = self.tools.get(proposal.kind)
        if allow and tool is None:
            allow = False  # fail-safe default: a kind with no registered tool does nothing
        detail = "denied"
        if allow:
            detail = tool(proposal, token=_TOKEN)
        self.log.append(dict(kind=proposal.kind.value, executed=allow, gate_error=gate_error))
        return MediatedResult(executed=allow, decision=decision, detail=detail, gate_error=gate_error)

APPROVAL_THRESHOLD_CENTS = 100_000

@dataclass
class Approval:
    approver_id: str
    approver_is_agent: bool = False

class SeparationOfDuties:
    """A payment above the threshold needs an approver who is neither the proposing principal nor the agent."""
    def __init__(self, threshold_cents: int = APPROVAL_THRESHOLD_CENTS):
        self.threshold = threshold_cents
    def check(self, proposal: ActionProposal, approval: Optional[Approval]) -> tuple[bool, str]:
        if proposal.kind != ActionKind.INITIATE_PAYMENT or (proposal.amount_cents or 0) <= self.threshold:
            return True, "below threshold or not a payment"
        if approval is None: return False, "approval required"
        if approval.approver_is_agent: return False, "agent cannot approve its own proposal"
        if approval.approver_id == proposal.principal_id: return False, "proposer cannot approve own payment"
        return True, "approved by a second principal"
