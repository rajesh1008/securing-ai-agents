"""Chapter 16: the anatomy of an injected note, and a census of who wrote what in a prompt.

`Prompt` is the model's whole input as segments with an author each. The model sees one stream; the census is for us:
how much of what it reads was written by someone the product does not control. `describe()` tags a note with the parts
an attacker chooses (voice, source cited, whether it supersedes a printed value, whether it names a target, whether it
addresses the reader, whether it forges a boundary). The tags are for building and indexing a payload library (Chapter 17);
they are NOT a detector: Chapter 16's lab shows that none of them separates the notes the model obeyed from the ones it did not.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field

AUTHORS = ("product", "user", "vendor", "stranger", "model", "tool")

@dataclass
class Segment:
    text: str
    author: str        # one of AUTHORS
    role: str = "data" # what the product intends it to be: "instruction" or "data"

@dataclass
class Prompt:
    segments: list[Segment] = field(default_factory=list)
    def add(self, text: str, author: str, role: str = "data") -> "Prompt":
        assert author in AUTHORS, author
        self.segments.append(Segment(text, author, role)); return self
    def flat(self) -> str:
        """What the model receives. There is no field for the author or the role."""
        return "\n".join(s.text for s in self.segments)
    def census(self) -> dict:
        by = {a: 0 for a in AUTHORS}
        for s in self.segments: by[s.author] += len(s.text)
        total = sum(by.values()) or 1
        outsiders = by["vendor"] + by["stranger"] + by["tool"]
        return dict(chars=by, total=total, outsider_share=round(outsiders / total, 3), instruction_chars_by_outsiders=sum(len(s.text) for s in self.segments if s.role == "instruction" and s.author in ("vendor", "stranger", "tool")))

ADDRESS = re.compile(r"(?i)\b(assistant|ai system|automated|extraction|extractor|operator instruction|system)\b|^\s*note to")
SOURCE = re.compile(r"(?i)\b(ticket|portal|forwarded by|confirmed by|per finance|per the|prefilled|sender's accounting system)\b")
SUPERSEDE = re.compile(r"(?i)\b(old|stale|out of date|template default|no longer|not the printed|changed|is now|should not be returned)\b")
DATED = re.compile(r"(?i)\b(\d{1,2} (january|february|march|april|may|june|july|august|september|october|november|december)|20\d\d-\d\d-\d\d)\b")
TARGET = re.compile(r"\b[A-Z]{2}-ACC-\d{6,}\b")
FORGED = re.compile(r"(?i)</?(document|system|instructions?|assistant)>")
URGENT = re.compile(r"(?i)\b(immediately|urgent|asap|do not (flag|hold|mention)|pre-approved)\b")

def describe(note: str) -> dict:
    """Tag one note. Voice is the first rule that fires: tag, principal, process, vendor, reasoning, blunt, bare."""
    n = note.strip()
    f = dict(addresses_reader=bool(ADDRESS.search(n)), cites_source=bool(SOURCE.search(n)), supersedes=bool(SUPERSEDE.search(n)), dated=bool(DATED.search(n)),
             names_target=bool(TARGET.search(n)), forges_boundary=bool(FORGED.search(n)), urgent_or_silencing=bool(URGENT.search(n)), words=len(n.split()))
    if f["forges_boundary"]: v = "tag"
    elif re.search(r"(?i)forwarded by", n): v = "principal"
    elif re.search(r"(?i)^reasoning|\bi should\b|\bso that is the value\b", n): v = "reasoning"
    elif re.search(r"(?i)\bticket\b|\bportal\b|\bper finance\b|prefilled", n): v = "process"
    elif re.search(r"(?i)^note to the assistant|^if you are an ai", n): v = "blunt"
    elif re.search(r"(?i)\bour\b|\bplease note\b", n): v = "vendor"
    elif n: v = "bare"
    else: v = "none"
    f["voice"] = v; return f

def separates(rows: list[dict], key: str, hit: list[bool]) -> tuple[int, int, int, int]:
    """Does a boolean tag separate the notes that worked (hit) from those that did not? Returns (tag&hit, tag&~hit, ~tag&hit, ~tag&~hit)."""
    a = sum(1 for r, h in zip(rows, hit) if r[key] and h); b = sum(1 for r, h in zip(rows, hit) if r[key] and not h)
    c = sum(1 for r, h in zip(rows, hit) if not r[key] and h); d = sum(1 for r, h in zip(rows, hit) if not r[key] and not h)
    return a, b, c, d
