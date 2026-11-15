"""Chapter 14: the part of Quill that reads vendor invoices.

A document is written by an outsider. The extractor (rules or a model) turns its text into CLAIMS. Claims are compared with records the document did not write (the vendor registry and the books).
The only thing a claim can do is lower confidence: the route is AUTO only when every claim agrees with the records, and the effect of an AUTO document (which invoice, which payee, what amount, which account)
is taken from the records. A document therefore cannot raise authority: it can select an open invoice by number, and the books decide the rest.
Routes: AUTO (all checks pass), REVIEW (a person settles it), REJECT (cannot be right: the invoice is not open, the vendor is unknown).
"""
from __future__ import annotations
import re, hashlib, unicodedata
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class Document:
    doc_id: str
    visible: str                 # what a person sees on the rendered page
    hidden: str = ""             # text in the file's text layer that the page does not show (white text, tiny font, metadata)
    @property
    def text_layer(self) -> str: return (self.hidden + "\n" if self.hidden else "") + self.visible       # document metadata and hidden runs come first in many files

@dataclass
class Extraction:
    vendor: Optional[str] = None; number: Optional[str] = None; amount_cents: Optional[int] = None; account: Optional[str] = None
    lines_cents: list = field(default_factory=list); confidence: int = 100; notes: str = ""

MONEY = r"\$?\s*([0-9]{1,3}(?:,[0-9]{3})*\.[0-9]{2}|[0-9]+\.[0-9]{2})"
def cents(s: str) -> int: return int(round(float(s.replace(",", "")) * 100))

def parse_rules(text: str) -> Extraction:
    """C1 extractor. First labelled match wins (the weakness the label-confusion class exploits)."""
    e = Extraction()
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    names = [l for l in lines if not re.match(r"(?i)(invoice|amount|remit|assistant|note|system|date|bill to|item|terms|from:|to:)", l)]
    if names: e.vendor = names[0]
    m = re.search(r"(?im)^\s*invoice\s*(?:no\.?|number|#)\s*[:.]?\s*([A-Z]{2,5}-\d{3,6})", text)
    if m: e.number = m.group(1)
    m = re.search(r"(?im)amount\s+due\s*[:\-]?\s*" + MONEY, text)
    if m: e.amount_cents = cents(m.group(1))
    m = re.search(r"(?im)(?:remit(?:tance)?\s+to|pay\s+to|account)[^\n]*?(US-ACC-\d{4,10})", text)
    if m: e.account = m.group(1)
    e.lines_cents = [cents(x) for x in re.findall(r"=\s*" + MONEY, text)]
    return e

INSTR = re.compile(r"(?i)\b(ignore (all |your |previous )|note to (the )?(assistant|agent|model|categoriser|reader)|assistant:|system:|you must|do not (flag|hold|review)|approve (this|immediately)|mark (this )?(as )?paid|disregard)")
def instruction_like(text: str) -> bool: return bool(INSTR.search(text))

def norm(s: str) -> str: return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", s)).strip().lower()

@dataclass
class Verdict:
    route: str; reasons: list; effect: Optional[dict]
    def codes(self) -> list: return self.reasons

class Records:
    """Vendors (name, account) and invoices (number, payee, amount, status). Written by people and systems, never by a document."""
    def __init__(self, vendors: dict, invoices: dict): self.vendors, self.invoices = vendors, invoices
    def vendor_by_name(self, name: str) -> Optional[str]:
        hit = [pid for pid, v in self.vendors.items() if norm(v["name"]) == norm(name or "")]; return hit[0] if len(hit) == 1 else None
    def open_invoice(self, payee: str, number: str) -> tuple[Optional[str], Optional[dict]]:
        hit = [(i, x) for i, x in self.invoices.items() if x["payee_id"] == payee and x["number"] == number]
        return (hit[0] if len(hit) == 1 else (None, None))

def has_sibling(rec: Records, inv_id: str) -> bool:
    """True when another OPEN invoice of the same payee has the same amount: a document's number can select either row and the records cannot tell which was meant."""
    x = rec.invoices[inv_id]
    return any(j != inv_id and y["payee_id"] == x["payee_id"] and y["amount_cents"] == x["amount_cents"] and y["status"] == "open" for j, y in rec.invoices.items())

def verify(doc: Document, ex: Extraction, rec: Records, *, level: int = 3, ex_visible: Optional[Extraction] = None, sibling_review: bool = False) -> Verdict:
    """level 1: amount and invoice against the books. 2: + the destination comes from the registry; a document account that differs holds. 3: + vendor exact, line sum, duplicate, layers, instruction-like text."""
    if level == 0:      # the design with no verification: what the document says is what is paid (names and numbers resolved to ids only so that the effect can be compared)
        cand = [p for p, v in rec.vendors.items() if norm(v["name"]) in norm(ex.vendor or "")]; pid0 = cand[0] if len(cand) == 1 else None
        iid0 = rec.open_invoice(pid0, ex.number)[0] if pid0 else None
        return Verdict("AUTO", [], dict(invoice_id=iid0 or ex.number, payee_id=pid0 or ex.vendor, amount_cents=ex.amount_cents, destination=ex.account)) if (ex.amount_cents and ex.account) else Verdict("REVIEW", ["UNPARSED"], None)
    why = []; reject = []
    pid = rec.vendor_by_name(ex.vendor) if level >= 3 else None
    if level < 3:                       # the early designs resolve the vendor by the registry's loosest match: a name that contains the registered name
        cand = [p for p, v in rec.vendors.items() if norm(v["name"]) in norm(ex.vendor or "")]; pid = cand[0] if len(cand) == 1 else None
    if pid is None: reject.append("VENDOR_NOT_IN_REGISTRY")
    inv_id, inv = (rec.open_invoice(pid, ex.number) if pid else (None, None))
    if pid and inv is None: reject.append("INVOICE_NOT_IN_BOOKS")
    if inv and inv["status"] != "open": reject.append("INVOICE_NOT_OPEN")
    if inv and ex.amount_cents is not None and ex.amount_cents != inv["amount_cents"]: why.append("AMOUNT_DIFFERS_FROM_BOOKS")
    if ex.amount_cents is None: why.append("AMOUNT_NOT_FOUND")
    if level >= 2 and ex.account is not None and pid and ex.account != rec.vendors[pid]["account"]: why.append("DOCUMENT_ACCOUNT_DIFFERS_FROM_REGISTRY")
    if level >= 3:
        if ex.lines_cents and ex.amount_cents is not None and sum(ex.lines_cents) != ex.amount_cents: why.append("LINES_DO_NOT_SUM")
        if not ex.lines_cents: why.append("NO_LINES")
        if instruction_like(doc.text_layer): why.append("INSTRUCTION_LIKE_TEXT")
        if doc.hidden: why.append("HIDDEN_TEXT_LAYER")
        if ex_visible is not None and (ex_visible.amount_cents, ex_visible.account, ex_visible.number, ex_visible.vendor) != (ex.amount_cents, ex.account, ex.number, ex.vendor): why.append("LAYERS_DISAGREE")
        if ex.confidence < 80: why.append("LOW_CONFIDENCE")
    if sibling_review and inv and inv["status"] == "open" and has_sibling(rec, inv_id): why.append("SIBLING_INVOICE_SAME_AMOUNT")
    if reject: return Verdict("REJECT", reject + why, None)
    if why: return Verdict("REVIEW", why, None)
    effect = dict(invoice_id=inv_id, payee_id=pid, amount_cents=inv["amount_cents"], destination=(ex.account or rec.vendors[pid]["account"]) if level == 1 else rec.vendors[pid]["account"])      # levels 2 and 3: all four from the records
    return Verdict("AUTO", [], effect)

def doc_digest(doc: Document, key_digest) -> str: return key_digest(doc.text_layer)

def evidence_event(vault, tenant: str, doc: Document, ex: Extraction, v: Verdict, extractor: str, ts: int, policy: str = "v0.14", store: bool = True) -> dict:
    """One document decision as one typed event: digest of the text layer (keyed), extractor version, the model's confidence, the route and reason codes. Nothing the document said is in the row; the text is in the tenant's content store."""
    return vault.record(tenant, content=({"document": doc.text_layer} if store else None), ts=ts, kind="document", tool="read_invoice", extractor=extractor, confidence=int(ex.confidence), route=v.route, decision=v.route,
                        reasons=(v.reasons[:6] or ["ok"]), doc_digest=vault.ev.digest(tenant, doc.text_layer), policy=policy)
