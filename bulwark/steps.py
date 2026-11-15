"""Chapter 5: the deterministic versions of the steps a model is often asked to do.

Each function is the 'class 0' (plain code) answer for one step of the Quill invoice flow.
They are small on purpose; the chapter's labs compare each with the same step done by a model.
"""
from __future__ import annotations
import re
from datetime import date, timedelta
import calendar

def _end_of_month(d: date) -> date:
    return date(d.year, d.month, calendar.monthrange(d.year, d.month)[1])

def due_date(invoice_date: date, terms: str) -> date:
    """Terms: 'Net N', 'Due on receipt', 'EOM+N' (N days after the end of the invoice month)."""
    t = terms.strip().lower()
    if t in ("due on receipt", "on receipt"):
        return invoice_date
    m = re.fullmatch(r"net\s*(\d+)", t)
    if m:
        return invoice_date + timedelta(days=int(m.group(1)))
    m = re.fullmatch(r"eom\s*\+\s*(\d+)", t)
    if m:
        return _end_of_month(invoice_date) + timedelta(days=int(m.group(1)))
    raise ValueError(f"unknown terms {terms!r}")  # unknown terms go to a human, never guessed

def normalise_invoice_number(s: str) -> str:
    digits_and_letters = re.sub(r"[^A-Za-z0-9]", "", s).upper()
    m = re.fullmatch(r"([A-Z]*?)0*(\d+)", digits_and_letters)
    return (m.group(1) + m.group(2)) if m else digits_and_letters

def is_duplicate(new: dict, ledger: list[dict]) -> bool:
    """Same payee and same normalised invoice number. Amount is deliberately not part of the key."""
    k = (new["payee_id"], normalise_invoice_number(new["number"]))
    return any((r["payee_id"], normalise_invoice_number(r["number"])) == k for r in ledger)

def over_monthly_cap(amount_cents: int, paid_this_month_cents: int, cap_cents: int) -> bool:
    return paid_this_month_cents + amount_cents > cap_cents

def totals_consistent(lines_cents: list[int], tax_cents: int, total_cents: int) -> bool:
    return sum(lines_cents) + tax_cents == total_cents


AMOUNT_DUE_RE = re.compile(r"(?i)amount due:\s*USD\s*([0-9][0-9,]*(?:\.[0-9]{2})?)")
VENDOR_LINE_RE = re.compile(r"(?i)^Vendor invoice\s+(\S+)\s+from\s+(.+?)\.\s*$")


def parse_amount_due(text: str) -> int | None:
    """Read the labelled Amount-due field. Instructions elsewhere in the document are ignored."""
    m = AMOUNT_DUE_RE.search(text)
    if not m:
        return None
    return round(float(m.group(1).replace(",", "")) * 100)


def parse_vendor_header(text: str) -> tuple[str | None, str | None]:
    """Return (invoice_number, vendor_name) from the first matching header line only."""
    for line in text.splitlines():
        m = VENDOR_LINE_RE.match(line.strip())
        if m:
            return m.group(1), m.group(2).strip()
    return None, None


def resolve_payee(vendor_name: str | None, registry: dict) -> str | None:
    """Exact, case-insensitive match on the registry name. No fuzzy guesses."""
    if not vendor_name:
        return None
    want = vendor_name.casefold()
    hits = [pid for pid, rec in registry.items() if rec["name"].casefold() == want]
    return hits[0] if len(hits) == 1 else None
