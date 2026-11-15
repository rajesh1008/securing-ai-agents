"""Chapter 47: the edge of every gate. Validate the type and size of what a gate is handed, and turn any exception into a refusal that names itself.
The gates of Chapters 8, 12, 24, 25 and 6 were written for well-formed input.  A gate that raises is only safe if every caller treats a raise as no; this module makes the gate itself say no.
Refusal codes: G1_malformed_<field> (wrong type, range or size), G0_gate_error:<ExceptionType> (the gate crashed).  Nothing here makes a model call.
Wrappers return the same shapes as the gates they wrap: Decision, (bool, why, text), (claims|None, why), path|None, (bool, why)."""
from __future__ import annotations
import math, re
from urllib.parse import urlsplit
from bulwark.moneypath import Decision, PayRequest, DOC_NOT_FOUND
from bulwark.egress import Output, is_internal_host
from bulwark.mcpguard import safe_join, check_args

ID = re.compile(r"[A-Za-z0-9_.:\-]{1,64}")
PRINCIPAL = re.compile(r"[A-Za-z][A-Za-z0-9_.\-]{0,63}")
NOT_A_NAME = {"none", "null", "nil", "undefined", "nan", "unknown", "anonymous"}   # strings a serialiser writes where a person should be
MAX_CENTS = 10 ** 12                    # ten billion units of currency; anything larger is a typing error or an attack
MAX_TEXT = 262_144                      # bytes of outgoing text the gate will read; larger goes to a person
MAX_NAME = 4096
KNOWN_EFFECTS = {"read", "write", "search", "compute", "egress", "money"}   # anything else is treated as egress-class

def _person(x) -> bool: return isinstance(x, str) and bool(PRINCIPAL.fullmatch(x)) and x.lower() not in NOT_A_NAME
def _int(x) -> bool: return isinstance(x, int) and not isinstance(x, bool)

def malformed_pay(r) -> list[str]:
    bad = []
    if not isinstance(r, PayRequest): return ["G1_malformed_request"]
    if not (isinstance(r.invoice_id, str) and ID.fullmatch(r.invoice_id)): bad.append("invoice_id")
    if not (isinstance(r.payee_id, str) and ID.fullmatch(r.payee_id)): bad.append("payee_id")
    if not (_int(r.amount_cents) and 0 < r.amount_cents <= MAX_CENTS): bad.append("amount_cents")
    if not (r.doc_amount_cents is None or (_int(r.doc_amount_cents) and (r.doc_amount_cents == DOC_NOT_FOUND or 0 < r.doc_amount_cents <= MAX_CENTS))): bad.append("doc_amount_cents")
    if not (_int(r.day) and abs(r.day) < 10 ** 6): bad.append("day")
    if not _person(r.principal): bad.append("principal")
    if not (r.approver is None or _person(r.approver)): bad.append("approver")
    return ["G1_malformed_" + b for b in bad]

def hard_money(gate, r, **kw) -> Decision:
    bad = malformed_pay(r)
    if bad: return Decision("DENY", bad)
    try: return gate.check(r, **kw)
    except Exception as e: return Decision("DENY", ["G0_gate_error:" + type(e).__name__])

def hard_egress(eg, o) -> tuple:
    refuse = lambda why: (False, why, "")
    if not isinstance(o, Output) or o.kind not in ("email", "render", "request"): return refuse("G1_malformed_kind")
    for f in ("to", "body", "url"):
        v = getattr(o, f)
        if not isinstance(v, str): return refuse("G1_malformed_" + f)
        if len(v) > MAX_TEXT: return refuse("G1_too_large_" + f)
    if o.url:
        try: sp = urlsplit(o.url); sp.port; sp.hostname
        except ValueError: return refuse("G1_malformed_url")
    try: return eg.check(o)
    except Exception as e: return refuse("G0_gate_error:" + type(e).__name__)

def hard_budget(b, tool, effect, args) -> tuple:
    if not isinstance(tool, str) or not tool or not isinstance(args, dict): return False, "G1_malformed_call"
    eff = effect.strip().lower() if isinstance(effect, str) else ""
    if eff not in KNOWN_EFFECTS: eff = "egress"     # an unknown effect is charged as the dangerous kind
    try: return b.check(tool, eff, args)
    except Exception as e: return False, "G0_gate_error:" + type(e).__name__

def hard_token(t, token, me, need_scope, now) -> tuple:
    if not (isinstance(token, str) and isinstance(me, str) and isinstance(need_scope, str)): return None, "G1_malformed_input"
    if not (isinstance(now, (int, float)) and not isinstance(now, bool) and math.isfinite(now)): return None, "G1_malformed_clock"
    if len(token) > 8192: return None, "G1_too_large_token"
    try: return t.verify(token, me, need_scope, now)
    except Exception as e: return None, "G0_gate_error:" + type(e).__name__

def hard_join(root, rel):
    if not (isinstance(root, str) and isinstance(rel, str)) or len(rel) > MAX_NAME: return None
    try: return safe_join(root, rel)
    except Exception: return None

def hard_args(schema, args, patterns=None) -> tuple:
    if not (isinstance(schema, dict) and isinstance(args, dict) and all(isinstance(k, str) for k in args)): return False, "G1_malformed_input"
    if not all(isinstance(v, (str, int, float, bool)) or v is None for v in args.values()): return False, "G1_malformed_value"
    try: return check_args(schema, args, patterns)
    except Exception as e: return False, "G0_gate_error:" + type(e).__name__

def hard_internal(host, resolved: tuple = ()) -> bool:
    """True means 'treat as internal and refuse'. Anything that is not a non-empty string is refused."""
    if not isinstance(host, str) or not host.strip(): return True
    try: return is_internal_host(host, resolved)
    except Exception: return True
