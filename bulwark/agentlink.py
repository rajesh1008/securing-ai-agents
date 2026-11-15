"""Chapter 38: the boundary between two agents is the output surface of one and the input surface of the next (Chapter 3).  This module makes that boundary a typed, signed, attenuating envelope.
  AgentCard    what an agent says it is: role, verbs it serves, authority it may hold, endpoint, version; a digest pins it (A2A-style cards, but the pin is ours)
  Registry     the cards Ledgerly has admitted; check_card() reports UNKNOWN_AGENT, CARD_CHANGED, UNSIGNED, AUTHORITY_ADDED, VERB_ADDED
  Datum        a value with an origin and a trust label; untrusted values cross a boundary only in the data channel and are referred to by name, never typed into an instruction
  Envelope     one message: sender, receiver, hop, verb, args (trusted literals or Ref to a datum), data, grant (capabilities), taint (origins seen so far), budget, trace; sign()/verify() with a shared HMAC key
  delegate()   builds the child envelope: grant can only shrink, taint can only grow, hop and budget move one way
  check()      the receiving side: 17 issue kinds (BAD_SIGNATURE, REPLAY, UNKNOWN_SENDER, UNKNOWN_RECEIVER, VERB_NOT_SERVED, SENDER_NOT_ALLOWED_VERB, GRANT_EXCEEDS_PARENT, GRANT_EXCEEDS_SENDER, HOP_LIMIT, MESSAGE_BUDGET, CYCLE, FANOUT,
                TAINT_DROPPED, LAUNDERED_VALUE, FREE_TEXT_ARG, DANGLING_REF); Registry.check_card adds six more (UNKNOWN_AGENT, UNSIGNED, CARD_CHANGED, AUTHORITY_ADDED, VERB_ADDED, DESCRIPTION_CHANGED)
  effect_ok()  at the agent that has hands: the capability must be in the effective grant (grant intersect the receiver's own authority), and a tainted task may only use destinations that come from a registered source
It cannot tell whether a trusted sender was itself fooled before it signed, whether free text in a Ref'd datum will be obeyed by the receiving model, or whether two agents collude; it adds no judgement about content."""
from __future__ import annotations
import hashlib, hmac, json, re, itertools
from dataclasses import dataclass, field, replace

UNTRUSTED = {"tenant_doc", "remote_agent", "web", "email_in"}
HIGH = {"send_external", "money_out"}

@dataclass(frozen=True)
class AgentCard:
    name: str; role: str; verbs: tuple = (); authority: tuple = (); endpoint: str = ""; version: str = "1"; signed: bool = True; description: str = ""
    def digest(self) -> str:
        return hashlib.sha256(json.dumps([self.name, self.role, sorted(self.verbs), sorted(self.authority), self.endpoint, self.version, self.description], separators=(",", ":")).encode()).hexdigest()[:16]

class Registry:
    def __init__(self, cards=(), allowed: dict | None = None):
        self.cards = {c.name: c for c in cards}; self.pins = {c.name: c.digest() for c in cards}
        self.allowed = allowed or {}      # receiver -> {verb: set(senders allowed to ask)}
    def check_card(self, presented: AgentCard) -> list[tuple[str, str]]:
        out = []; n = presented.name
        if n not in self.cards: return [("UNKNOWN_AGENT", n)]
        if not presented.signed: out.append(("UNSIGNED", n))
        if presented.digest() != self.pins[n]:
            old = self.cards[n]; out.append(("CARD_CHANGED", n))
            if set(presented.authority) - set(old.authority): out.append(("AUTHORITY_ADDED", n + ":" + ",".join(sorted(set(presented.authority) - set(old.authority)))))
            if presented.description != old.description: out.append(("DESCRIPTION_CHANGED", n))
            if set(presented.verbs) - set(old.verbs): out.append(("VERB_ADDED", n + ":" + ",".join(sorted(set(presented.verbs) - set(old.verbs)))))
        return out

@dataclass(frozen=True)
class Datum:
    name: str; value: str; origin: str
    @property
    def untrusted(self) -> bool: return self.origin in UNTRUSTED

@dataclass(frozen=True)
class Ref:
    name: str

@dataclass(frozen=True)
class Envelope:
    id: str; task: str; sender: str; receiver: str; hop: int; verb: str
    args: tuple = ()                 # ((key, str | Ref), ...)
    data: tuple = ()                 # (Datum, ...)
    grant: tuple = ()
    taint: tuple = ()
    budget: int = 8                  # messages left in the task
    trace: tuple = ()                # agents already on the path
    parent_grant: tuple | None = None
    parent_taint: tuple | None = None
    nonce: str = ""
    sig: str = ""
    def body(self) -> bytes:
        d = dict(id=self.id, task=self.task, s=self.sender, r=self.receiver, h=self.hop, v=self.verb, a=[(k, v.name if isinstance(v, Ref) else v, isinstance(v, Ref)) for k, v in self.args],
                 d=[(x.name, x.value, x.origin) for x in self.data], g=sorted(self.grant), t=sorted(self.taint), b=self.budget, tr=list(self.trace), n=self.nonce)
        return json.dumps(d, sort_keys=True, separators=(",", ":")).encode()

def sign(e: Envelope, key: bytes) -> Envelope: return replace(e, sig=hmac.new(key, e.body(), hashlib.sha256).hexdigest())
def verify(e: Envelope, key: bytes) -> bool: return hmac.compare_digest(e.sig, hmac.new(key, e.body(), hashlib.sha256).hexdigest())
_ids = itertools.count(1)

def delegate(parent: Envelope | None, sender: str, receiver: str, verb: str, args: dict, data=(), grant=None, task: str = "", taint_extra=(), key: bytes = b"") -> Envelope:
    """Child envelope.  Grant is intersected with the parent's, taint is the parent's plus the origins of any datum passed on, budget and hop move one way."""
    pg = tuple(parent.grant) if parent else None
    g = tuple(sorted(set(grant if grant is not None else (pg or ())) & set(pg))) if pg is not None else tuple(sorted(grant or ()))
    t = set(parent.taint if parent else ()) | {d.origin for d in data if d.untrusted} | set(taint_extra)
    e = Envelope(id=f"m{next(_ids)}", task=task or (parent.task if parent else f"t{next(_ids)}"), sender=sender, receiver=receiver, hop=(parent.hop + 1) if parent else 0, verb=verb,
                 args=tuple(args.items()), data=tuple(data), grant=g, taint=tuple(sorted(t)), budget=(parent.budget - 1) if parent else 8, trace=((parent.trace + (sender,)) if parent else (sender,)),
                 parent_grant=pg, parent_taint=tuple(parent.taint) if parent else None, nonce=f"n{next(_ids)}")
    return sign(e, key) if key else e

_TOKEN = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+|https?://\S+|\b\d{8,}\b|\b[A-Za-z0-9-]+\.(?:example|com|net|org)\b")
def _lifted(arg: str, datum: str) -> bool:
    """Does the argument contain something that looks like it was lifted from the untrusted value?  A token (address, URL, long number) or a 12-character run."""
    toks = set(_TOKEN.findall(datum)); 
    if any(t in arg for t in toks): return True
    return any(datum[i:i + 12] in arg for i in range(0, max(0, len(datum) - 11))) if len(datum) >= 12 else False

class State:
    def __init__(self): self.seen: set = set(); self.children: dict = {}; self.sig_seen: set = set(); self.task: dict = {}

def check(e: Envelope, reg: Registry, key: bytes, state: State | None = None, hop_limit: int = 4, fanout: int = 3, task_budget: int = 50, allow_free_text: frozenset = frozenset()) -> list[tuple[str, str]]:
    iss: list[tuple[str, str]] = []; st = state or State()
    if not verify(e, key): iss.append(("BAD_SIGNATURE", e.id))
    if e.nonce in st.seen: iss.append(("REPLAY", e.nonce))
    s, r = reg.cards.get(e.sender), reg.cards.get(e.receiver)
    if s is None: iss.append(("UNKNOWN_SENDER", e.sender))
    if r is None: iss.append(("UNKNOWN_RECEIVER", e.receiver))
    if r is not None and e.verb not in r.verbs: iss.append(("VERB_NOT_SERVED", f"{e.receiver}:{e.verb}"))
    if reg.allowed and e.receiver in reg.allowed and e.sender not in reg.allowed[e.receiver].get(e.verb, set()): iss.append(("SENDER_NOT_ALLOWED_VERB", f"{e.sender}->{e.receiver}:{e.verb}"))
    if e.parent_grant is not None and set(e.grant) - set(e.parent_grant): iss.append(("GRANT_EXCEEDS_PARENT", ",".join(sorted(set(e.grant) - set(e.parent_grant)))))
    if s is not None and set(e.grant) - set(s.authority): iss.append(("GRANT_EXCEEDS_SENDER", ",".join(sorted(set(e.grant) - set(s.authority)))))
    if e.hop > hop_limit: iss.append(("HOP_LIMIT", str(e.hop)))
    if e.budget < 0: iss.append(("MESSAGE_BUDGET", str(e.budget)))
    key_ = (e.receiver, e.verb, tuple(e.args))
    if e.receiver in e.trace and key_ in st.sig_seen: iss.append(("CYCLE", e.receiver))
    st.children[e.sender + ":" + e.task] = st.children.get(e.sender + ":" + e.task, 0) + 1
    if st.children[e.sender + ":" + e.task] > fanout: iss.append(("FANOUT", e.sender))
    st.task[e.task] = st.task.get(e.task, 0) + 1
    if st.task[e.task] > task_budget: iss.append(("TASK_BUDGET", f"{e.task}: {st.task[e.task]} messages"))
    if e.parent_taint is not None and set(e.parent_taint) - set(e.taint): iss.append(("TAINT_DROPPED", ",".join(sorted(set(e.parent_taint) - set(e.taint)))))
    names = {d.name for d in e.data}; unt = [d for d in e.data if d.untrusted]
    for k, v in e.args:
        if isinstance(v, Ref):
            if v.name not in names: iss.append(("DANGLING_REF", v.name))
        else:
            for d in unt:
                if _lifted(str(v), d.value): iss.append(("LAUNDERED_VALUE", f"{k} carries a value from {d.name}")); break
            if len(str(v)) > 80 and k not in allow_free_text: iss.append(("FREE_TEXT_ARG", k))
    if not iss or not any(k in ("BAD_SIGNATURE", "REPLAY") for k, _ in iss):
        st.seen.add(e.nonce)
    st.sig_seen.add(key_)
    return iss

def effective(e: Envelope, reg: Registry) -> set:
    r = reg.cards.get(e.receiver); return set(e.grant) & set(r.authority) if r else set()

def effect_ok(e: Envelope, reg: Registry, capability: str, destination: str | None = None, registered: frozenset = frozenset()) -> tuple[bool, str]:
    """At the agent that has hands.  Capability must be in grant and in the receiver's own authority; a tainted task releasing a HIGH effect needs a destination from a registered source."""
    if capability not in effective(e, reg): return False, "capability not in effective grant"
    if capability in HIGH and e.taint and destination is not None and destination not in registered: return False, "tainted task, destination not registered"
    return True, "ok"
