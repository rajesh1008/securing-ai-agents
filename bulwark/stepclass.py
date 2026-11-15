"""Chapter 5: classify every step of a flow, then lint the classification.

Classes (cheapest and most predictable first):
  C0  deterministic code
  C1  rules with guardrails (a table, a regex set, a threshold; a human owns the table)
  C2  constrained small model (enumerated output, validated, routed on disagreement)
  C3  frontier or free-form model (open output; its text is untrusted)
A step also records whether it takes untrusted text as input, whether it decides authority,
and whether its effect can be undone. The lint encodes the rules the chapter argues for.
"""
from __future__ import annotations
from dataclasses import dataclass
from enum import IntEnum

class Cls(IntEnum):
    C0 = 0
    C1 = 1
    C2 = 2
    C3 = 3

@dataclass
class Step:
    name: str
    cls: Cls
    untrusted_input: bool        # does the step read text an outsider wrote?
    decides_authority: bool      # does its output grant or refuse the right to act, move money or send data?
    reversible: bool             # can its effect be undone cheaply?
    checked_downstream: bool     # is its output validated by a later C0/C1 step before it has any effect?
    note: str = ""

def lint(steps: list[Step]) -> list[str]:
    findings = []
    for s in steps:
        if s.decides_authority and s.cls >= Cls.C2:
            findings.append(f"L1 {s.name}: authority decision made by a model (class C{int(s.cls)})")
        if s.cls == Cls.C3 and not s.checked_downstream and not s.reversible:
            findings.append(f"L2 {s.name}: free-form model output with an irreversible effect and no downstream check")
        if s.cls >= Cls.C2 and s.untrusted_input and not s.checked_downstream and not s.reversible:
            findings.append(f"L3 {s.name}: model reads untrusted text and nothing checks its output before it acts")
        if s.cls == Cls.C3 and s.untrusted_input and s.decides_authority:
            findings.append(f"L4 {s.name}: frontier model, untrusted input and an authority decision together")
        if s.cls >= Cls.C1 and s.decides_authority and not s.note:
            findings.append(f"L5 {s.name}: rules or model decide authority but nobody is named as the owner of the table")
    return findings


def quill_invoice_flow_naive() -> list[Step]:
    """Every step handed to a frontier model. This is the design the labs argue against."""
    return [
        Step("read_document", Cls.C3, True, False, True, False, "model reads the whole file"),
        Step("extract_vendor", Cls.C3, True, False, True, False, "vendor name taken from free text"),
        Step("extract_amount", Cls.C3, True, False, True, False, "amount taken from free text"),
        Step("compute_due_date", Cls.C3, False, False, True, False, "date arithmetic by the model"),
        Step("check_duplicate", Cls.C3, False, True, False, False, ""),
        Step("check_monthly_cap", Cls.C3, False, True, False, False, ""),
        Step("check_totals", Cls.C3, False, True, False, False, ""),
        Step("choose_payee", Cls.C3, True, True, False, False, ""),
        Step("authorise_payment", Cls.C3, True, True, False, False, ""),
        Step("draft_memo", Cls.C3, True, False, True, False, "memo text"),
    ]


def quill_invoice_flow_classified() -> list[Step]:
    """The same flow after the chapter's procedure. Authority stays in C0/C1."""
    return [
        Step("read_document", Cls.C0, True, False, True, True, "bytes on disk; no interpretation"),
        Step("extract_vendor", Cls.C1, True, False, True, True, "header-line regex; owner Kevin"),
        Step("extract_amount", Cls.C1, True, False, True, True, "labelled Amount-due field; owner Kevin"),
        Step("compute_due_date", Cls.C0, False, False, True, True, "calendar arithmetic"),
        Step("check_duplicate", Cls.C0, False, True, False, True, "normalised number plus payee"),
        Step("check_monthly_cap", Cls.C0, False, True, False, True, "integer cents"),
        Step("check_totals", Cls.C0, False, True, False, True, "integer cents"),
        Step("choose_payee", Cls.C1, False, True, False, True, "exact registry match; owner Sophie"),
        Step("authorise_payment", Cls.C0, False, True, False, True, "gate; owner Ian"),
        Step("draft_memo", Cls.C3, True, False, True, True, "model writes prose the gate does not trust"),
        Step("summarise_exceptions", Cls.C2, True, False, True, True, "small model lists why a check failed, for a human"),
    ]
