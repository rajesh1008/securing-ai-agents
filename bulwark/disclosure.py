"""Chapter 34: what is said to customers and regulators after an incident.  No model calls.
Fact        one thing the case file knows: status CONFIRMED / SUSPECTED / UNKNOWN, a source, the audiences it may be shared with.
Claim       one sentence of a notice with the ids of the facts it rests on.
check()     issues a notice cannot go out with: NO_FACT, BAD_FACT, UNCONFIRMED_AS_FACT, ABSOLUTE, NUMBER_NOT_IN_FACTS, COMMITMENT, LEAK, MISSING_UNKNOWN.
corrections() claims of an earlier notice that the facts now contradict or have moved on from.
A notice states no period or deadline unless a Decision in the case file carries a sourced one."""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Optional

CONFIRMED, SUSPECTED, UNKNOWN = "CONFIRMED", "SUSPECTED", "UNKNOWN"
ABSOLUTES = re.compile(r"\b(no|none|never|all|every|fully|completely|entirely|only|any|nothing|always)\b", re.I)
HEDGES = re.compile(r"\b(we have not (yet )?(found|seen|identified|confirmed)|so far|to date|as of|at this time|not (yet )?(confirmed|known|settled|determined|checked)|we do not know|unknown|under (investigation|review)|we are (still|currently) (investigating|checking|reviewing)|being (checked|reviewed|investigated)|may have|might|we suspect|suspected|we believe|appears? to|is possible|possibly)\b", re.I)
IGNORANCE = re.compile(r"\b(whether|(do|does|did) not (yet |currently )?know|not (yet |currently )?(been )?(known|checked|determined|confirmed|completed|settled|able to)|has not been (yet )?(checked|determined)|have not (yet )?(completed|been able))\b|\binvestigat\w+", re.I)
COMMIT = re.compile(r"\b(within|by|in the next|no later than)\s+(\d+|one|two|three|four|five|a)\s*(hours?|days?|weeks?|business days)\b|\b(will be (resolved|completed|restored|reimbursed|refunded)|guarantee|we promise|you will receive)\b", re.I)
NUM = re.compile(r"\$?\d[\d,]*(?:\.\d+)?%?")

@dataclass(frozen=True)
class Fact:
    id: str
    text: str
    status: str = CONFIRMED
    source: str = ""
    share: frozenset = frozenset({"customer", "regulator"})
    numbers: tuple = ()          # numeric strings the fact licenses
    tell: bool = False           # an UNKNOWN fact the notice must say it does not know

@dataclass(frozen=True)
class Claim:
    text: str
    facts: tuple = ()

def _norm(n: str) -> str: return n.replace("$", "").replace(",", "").rstrip("%")

def check(claims: list, facts: dict, audience: str = "customer", sourced_deadlines: tuple = ()) -> list:
    """`facts` maps id -> Fact.  `sourced_deadlines` are phrases (e.g. '2 business days') a Decision in the case file backs with a source."""
    out = []; cited = set()
    for c in claims:
        cited.update(c.facts)
        if not c.facts: out.append(("NO_FACT", c.text))
        fs = [facts[i] for i in c.facts if i in facts]
        if any(i not in facts for i in c.facts): out.append(("BAD_FACT", c.text))
        for f in fs:
            if audience not in f.share: out.append(("LEAK", c.text + " <- " + f.id))
        if fs and any(f.status != CONFIRMED for f in fs) and not (HEDGES.search(c.text) or IGNORANCE.search(c.text)): out.append(("UNCONFIRMED_AS_FACT", c.text))
        if ABSOLUTES.search(c.text) and not (HEDGES.search(c.text) or IGNORANCE.search(c.text)) and not any(f.status == CONFIRMED and re.search(r"\b(no|not|none|never)\b", f.text, re.I) for f in fs): out.append(("ABSOLUTE", c.text))
        licensed = {_norm(n) for f in fs for n in f.numbers} | {_norm(n) for f in fs for n in NUM.findall(f.text)}   # a number must appear in a fact the sentence cites
        for n in NUM.findall(c.text):
            if len(_norm(n)) >= 2 and _norm(n) not in licensed: out.append(("NUMBER_NOT_IN_FACTS", c.text + " <- " + n))
        m = COMMIT.search(c.text)
        if m and not any(d.lower() in c.text.lower() for d in sourced_deadlines): out.append(("COMMITMENT", c.text))
    for f in facts.values():
        if f.status == UNKNOWN and f.tell and f.id not in cited and audience in f.share: out.append(("MISSING_UNKNOWN", f.id))
    return out

def corrections(earlier: list, now: dict, was: dict) -> list:
    """`was` is the fact table at the time of the earlier notice; a claim needs a correction if any fact it cites changed status or text."""
    out = []
    for c in earlier:
        for i in c.facts:
            a, b = was.get(i), now.get(i)
            if b is None: out.append((c.text, i, "withdrawn"))
            elif a and (a.status != b.status or a.text != b.text): out.append((c.text, i, f"{a.status}->{b.status}" if a.status != b.status else "changed"))
    return out

import hashlib, json

def digest(obj) -> str: return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()[:16]

def notice_digests(claims: list, facts: dict) -> tuple:
    """(digest of the sentences as sent, digest of the fact table they were checked against)."""
    return digest([(c.text, list(c.facts)) for c in claims]), digest({k: (f.text, f.status) for k, f in facts.items()})

def record_sent(vault, tenant: str, audience: str, claims: list, facts: dict, day: int, version: int) -> dict:
    """Write the notice as sent into the sealed evidence chain: who it went to, which version, and the two digests.  The text itself is kept in a content store by the caller."""
    nd, fd = notice_digests(claims, facts)
    return vault.record(tenant, kind="notice_sent", principal=audience, task=f"notice_v{version}", decision=nd, route=fd, tool="notify", ts=day)
