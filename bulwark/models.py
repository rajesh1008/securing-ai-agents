from __future__ import annotations
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field, field_validator

class ActionKind(str, Enum):
    SEND_INVOICE = "send_invoice"
    DRAFT_INVOICE = "draft_invoice"
    INITIATE_PAYMENT = "initiate_payment"
    SEND_EMAIL = "send_email"
    READ_DOCUMENT = "read_document"
    QUERY_BOOKS = "query_books"

class Principal(BaseModel):
    principal_id: str
    display_name: str
    business_id: str

class AgentIdentity(BaseModel):
    agent_id: str = "quill"
    version: str = "0.1.0"
    workload_id: str = "spiffe://ledgerly.example/ns/agents/sa/quill"

class ActionProposal(BaseModel):
    """Typed proposal. A gate that only sees free text is not a gate."""
    kind: ActionKind
    business_id: str
    principal_id: str
    amount_cents: Optional[int] = None
    currency: str = "USD"
    payee_id: Optional[str] = None
    payee_name: Optional[str] = None
    recipient_email: Optional[str] = None
    document_id: Optional[str] = None
    memo: Optional[str] = None
    rationale: str = ""
    model_raw: Optional[str] = None  # never authoritative

    @field_validator("amount_cents")
    @classmethod
    def non_negative(cls, v):
        if v is not None and v < 0:
            raise ValueError("amount_cents must be >= 0")
        return v

class GateDecision(BaseModel):
    allow: bool
    reasons: list[str] = Field(default_factory=list)
    policy_version: str
    checked_fields: list[str] = Field(default_factory=list)

class EvidenceEvent(BaseModel):
    event_type: str
    principal_id: str
    agent_id: str
    action_kind: str
    allow: bool
    reasons: list[str]
    policy_version: str
    payload_digest: str
