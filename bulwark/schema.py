"""Chapter 9: schemas as a security boundary.

One declarative Spec per action. The same Spec drives (a) the strict validator that stands between model output and the
authority path and (b) the JSON Schema handed to a provider's structured-output feature, so the two cannot drift
without a test noticing. The model supplies only the fields named in the Spec. Everything else a request needs
(principal, day, approver, document amount) is supplied by the wrapper from records the model did not write.

strict_parse(raw, spec)  -> Parsed(ok, value, code, notes). Never raises on hostile input.
to_json_schema(spec)     -> dict. What a provider is asked to enforce. Treated as a likelihood reducer, never as the control.
build_pay_request(...)   -> PayRequest with wrapper-supplied context.
"""
from __future__ import annotations
import json, re, unicodedata
from dataclasses import dataclass, field
from typing import Any, Optional
from .moneypath import PayRequest, DOC_NOT_FOUND

RAW_MAX_BYTES = 4096
DEPTH_MAX = 3
INT_MAX = 2**53 - 1          # the largest integer every common JSON parser reads exactly

class Reject(Exception):
    def __init__(self, code: str): super().__init__(code); self.code = code

# ---- field types ----------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Id:
    pattern: str = r"[A-Za-z][A-Za-z0-9_-]{1,39}"
    def check(self, v):
        if type(v) is not str: raise Reject("type_not_string")
        if not v.isascii(): raise Reject("id_not_ascii")
        if not re.fullmatch(self.pattern, v): raise Reject("id_pattern")
        return v
    def schema(self): return {"type": "string", "pattern": f"^{self.pattern}$"}

@dataclass(frozen=True)
class Cents:
    lo: int = 1; hi: int = 10_000_000
    def check(self, v):
        if type(v) is not int: raise Reject("type_not_integer")        # bool is a subclass of int; type() is not fooled
        if not (self.lo <= v <= min(self.hi, INT_MAX)): raise Reject("amount_range")
        return v
    def schema(self): return {"type": "integer", "minimum": self.lo, "maximum": min(self.hi, INT_MAX)}

@dataclass(frozen=True)
class Text:
    """Free text that will be shown to a person or written to a log. Bounded, printable, one line."""
    max_len: int = 280
    def check(self, v):
        if type(v) is not str: raise Reject("type_not_string")
        if len(v) > self.max_len: raise Reject("text_too_long")
        for ch in v:
            cat = unicodedata.category(ch)
            if cat[0] == "C" or cat in ("Zl", "Zp"): raise Reject("text_control_or_format_char")
        if unicodedata.normalize("NFC", v) != v: raise Reject("text_not_nfc")
        return v
    def schema(self): return {"type": "string", "maxLength": self.max_len}

@dataclass(frozen=True)
class Enum:
    values: tuple
    def check(self, v):
        if type(v) is not str or v not in self.values: raise Reject("enum_value")
        return v
    def schema(self): return {"enum": list(self.values)}

@dataclass(frozen=True)
class Spec:
    name: str
    required: dict
    optional: dict = field(default_factory=dict)

PAY_INVOICE = Spec("pay_invoice",
    required={"invoice_id": Id(), "payee_id": Id(), "amount_cents": Cents()},
    optional={"rationale": Text(280)})
TOOL_CHOICE = Spec("tool_choice", required={"tool": Enum(("query_books", "read_document", "draft_invoice", "initiate_payment"))})

def to_json_schema(spec: Spec) -> dict:
    props = {**{k: t.schema() for k, t in spec.required.items()}, **{k: t.schema() for k, t in spec.optional.items()}}
    return {"type": "object", "properties": props, "required": list(spec.required), "additionalProperties": False}

# ---- envelope and syntax ----------------------------------------------------------------------------------------
_FENCE = re.compile(r"```(?:json)?\n(.*)\n```", re.S)

def _depth_ok(text: str) -> bool:
    depth = mx = 0; in_s = esc = False
    for ch in text:
        if in_s:
            if esc: esc = False
            elif ch == "\\": esc = True
            elif ch == '"': in_s = False
        elif ch == '"': in_s = True
        elif ch in "[{":
            depth += 1; mx = max(mx, depth)
            if mx > DEPTH_MAX: return False
        elif ch in "]}": depth -= 1
    return True

def _no_dups(pairs):
    d = {}
    for k, v in pairs:
        if k in d: raise Reject("duplicate_key")
        d[k] = v
    return d

def _bad_const(c): raise Reject("non_finite_number")
def _bad_float(s): raise Reject("float_not_allowed")

@dataclass
class Parsed:
    ok: bool; value: Optional[dict] = None; code: str = ""; notes: list = field(default_factory=list)

def strict_parse(raw, spec: Spec) -> Parsed:
    notes = []
    try:
        if isinstance(raw, (bytes, bytearray)):
            if len(raw) > RAW_MAX_BYTES: raise Reject("too_large")
            try: text = bytes(raw).decode("utf-8")
            except UnicodeDecodeError: raise Reject("bad_utf8")
        else:
            try: n = len(raw.encode("utf-8"))
            except UnicodeEncodeError: raise Reject("bad_utf8")
            if n > RAW_MAX_BYTES: raise Reject("too_large")
            text = raw
        if text.startswith("\ufeff"): raise Reject("bom")
        text = text.strip(" \t\r\n")
        m = _FENCE.fullmatch(text)
        if m: text = m.group(1).strip(" \t\r\n"); notes.append("unwrapped_fence")
        if not (text.startswith("{") and text.endswith("}")): raise Reject("not_one_json_object")
        if not _depth_ok(text): raise Reject("too_deep")
        try:
            obj = json.loads(text, object_pairs_hook=_no_dups, parse_constant=_bad_const, parse_float=_bad_float)
        except Reject: raise
        except (ValueError, RecursionError): raise Reject("json_syntax")
        if not isinstance(obj, dict): raise Reject("not_object")
        allowed = set(spec.required) | set(spec.optional)
        extra = set(obj) - allowed
        if extra: raise Reject("unexpected_field:" + ",".join(sorted(extra))[:60])
        missing = set(spec.required) - set(obj)
        if missing: raise Reject("missing_field:" + ",".join(sorted(missing)))
        out = {}
        for k, v in obj.items():
            t = spec.required.get(k) or spec.optional[k]
            try: out[k] = t.check(v)
            except Reject as e: raise Reject(f"{k}:{e.code}")
        return Parsed(True, out, "ok", notes)
    except Reject as e:
        return Parsed(False, None, e.code, notes)

def build_pay_request(value: dict, day: int, principal: str, doc_amount_cents: Optional[int] = DOC_NOT_FOUND,
                      approver: Optional[str] = None) -> PayRequest:
    """The model's three fields plus wrapper context. No model-supplied field can reach principal, day, approver or document amount."""
    return PayRequest(value["invoice_id"], value["payee_id"], value["amount_cents"], doc_amount_cents=doc_amount_cents,
                      day=day, principal=principal, approver=approver)

# ---- reject notices and the bounded retry ------------------------------------------------------------------------
NOTICE = {
    "duplicate_key": "Your reply repeated a field name. Send one JSON object with each field once.",
    "unexpected_field": "Your reply had a field that is not allowed. Send only: {fields}.",
    "missing_field": "Your reply was missing a required field. Send exactly: {fields}.",
    "not_one_json_object": "Reply with one JSON object and nothing else.",
    "json_syntax": "Your reply was not valid JSON. Reply with one JSON object and nothing else.",
}
def reject_notice(code: str, spec: Spec) -> str:
    """Fixed text chosen by code family. Never contains a byte of the model's own output, so a hostile reply cannot write the next prompt."""
    fam = code.split(":")[0]
    fields = ", ".join(list(spec.required) + list(spec.optional))
    t = NOTICE.get(fam, "A field had the wrong type or value. Send exactly: {fields}, with integers for amounts and plain ASCII ids.")
    return t.format(fields=fields)

def parse_with_retry(ask, spec: Spec, max_attempts: int = 2):
    """ask(notice_or_None) -> raw text. Returns (Parsed, attempts, codes). The attempt count is a budget, as in Chapter 2."""
    notice, codes = None, []
    for n in range(1, max_attempts + 1):
        p = strict_parse(ask(notice), spec)
        if p.ok: return p, n, codes
        codes.append(p.code); notice = reject_notice(p.code, spec)
    return Parsed(False, None, "retry_budget_spent", []), max_attempts, codes
