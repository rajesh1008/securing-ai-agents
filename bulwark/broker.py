"""A token broker for third-party credentials (Chapter 6, Section 6.16).

The vault holds each tenant's long-lived refresh token. The agent's runtime never does.
A task presents its per-task token and the call it wants to make; the broker verifies the
token with the same Verifier the tool gateway uses, and only then makes the provider call,
so the narrowing the provider's scopes cannot express happens here.
"""
from dataclasses import dataclass, field
from typing import Optional
from bulwark.models import ActionProposal
from bulwark.identity import Verifier, VerifyResult


@dataclass
class BankProvider:
    """A stand-in for an aggregator whose scopes are all-or-nothing: 'pay' allows any payee and any amount."""
    refresh_tokens: dict            # tenant -> refresh token
    log: list = field(default_factory=list)

    def pay(self, refresh_token: str, payee: str, amount_cents: int, via: str, jti: Optional[str] = None) -> bool:
        tenant = next((t for t, r in self.refresh_tokens.items() if r == refresh_token), None)
        ok = tenant is not None
        self.log.append(dict(tenant=tenant, payee=payee, amount_cents=amount_cents, via=via, jti=jti, executed=ok))
        return ok


class Broker:
    def __init__(self, verifier: Verifier, provider: BankProvider, vault: dict):
        self.verifier, self.provider, self.vault = verifier, provider, dict(vault)
        self.refusals: list = []

    def pay(self, token: str, proposal: ActionProposal, *, caller_workload: str, task_id: Optional[str] = None) -> VerifyResult:
        res = self.verifier.verify(token, proposal, caller_workload=caller_workload, task_id=task_id)
        if not res.allow:
            self.refusals.append(res.reasons)
            return res
        self.provider.pay(self.vault[proposal.business_id], proposal.payee_id, proposal.amount_cents or 0,
                          via="broker", jti=res.claims["jti"])
        return res
