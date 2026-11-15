"""Chapter 37: the crosswalk.  A mapping from the controls of a bundle (Chapter 35) to the items of published frameworks, with the edition of the framework recorded on every row.
A Standard says which edition was read, on what date, how (full text, titles only, secondary page) and whether the catalogue of its items is complete.
A Row says: this control, this item of this standard AS OF this edition, this relation, this limit sentence.  `check` returns the reasons a mapping should not be shown to an auditor.
Relations are deliberately weak words.  A control can ADDRESS a risk, cover PART of it, be EVIDENCE_FOR a requirement, or be ALIGNED_WITH a text that does not apply yet.  There is no word for 'complies':
that is a conclusion for the party the text binds, and `check` flags any attempt to claim it from a lab."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date

RELS = {"ADDRESSES": "tested", "PARTIAL": "designed", "EVIDENCE_FOR": "tested", "ALIGNED_WITH": "designed", "NA": "designed"}   # relation -> weakest control claim level allowed
LEVELS = ("designed", "tested", "measured_in_simulation", "measured_live_model", "operating")
READ = ("FULL_TEXT", "TITLES", "SECONDARY")          # how the book's author read the edition

@dataclass(frozen=True)
class Standard:
    id: str; name: str; edition: str; edition_date: str; status: str; source: str; read: str; retrieved: str; complete: bool = True; binding: bool = False
@dataclass(frozen=True)
class Item:
    std: str; id: str; title: str; from_date: str = ""          # from_date: first day the text applies, for binding texts
@dataclass
class Row:
    control: str; std: str; item: str; edition: str; rel: str; limit: str; title: str = ""; reason: str = ""

def ref(std: str, item: str) -> str: return f"{std}:{item}"

class Catalogue:
    def __init__(self, standards: list[Standard], items: list[Item]):
        self.std = {s.id: s for s in standards}; self.items = {ref(i.std, i.id): i for i in items}
    def of(self, std: str) -> list[Item]: return [i for i in self.items.values() if i.std == std]

def check(rows: list[Row], cat: Catalogue, control_levels: dict[str, str], *, as_of: str, max_read_days: int = 90, claims_compliance: set | None = None) -> list[tuple[str, str]]:
    """Issues in a mapping.  `control_levels` is control id -> claim level from the bundle."""
    out: list[tuple[str, str]] = []; d0 = date.fromisoformat(as_of); seen = set()
    for r in rows:
        key = (r.control, r.std, r.item)
        if key in seen: out.append(("DUPLICATE_ROW", "%s %s" % (r.control, ref(r.std, r.item))))
        seen.add(key)
        if r.control not in control_levels and not (r.rel == "NA" and r.control == "-"): out.append(("UNKNOWN_CONTROL", r.control)); continue
        if r.std not in cat.std: out.append(("UNKNOWN_STANDARD", r.std)); continue
        s = cat.std[r.std]; it = cat.items.get(ref(r.std, r.item))
        if it is None: out.append(("UNKNOWN_ITEM", f"{r.control} -> {ref(r.std, r.item)}")); continue
        if r.edition != s.edition: out.append(("EDITION_MISMATCH", f"{r.control} -> {ref(r.std, r.item)}: row says '{r.edition}', catalogue is '{s.edition}'"))
        if r.title and r.title.strip().lower() != it.title.strip().lower(): out.append(("TITLE_DRIFT", f"{ref(r.std, r.item)}: row '{r.title}' vs source '{it.title}'"))
        if r.rel not in RELS: out.append(("BAD_RELATION", f"{r.control} -> {ref(r.std, r.item)}: {r.rel}")); continue
        if r.rel == "NA":
            if not r.reason.strip(): out.append(("NA_NO_REASON", f"{r.control} -> {ref(r.std, r.item)}"))
        else:
            if not r.limit.strip(): out.append(("NO_LIMIT", f"{r.control} -> {ref(r.std, r.item)}"))
            if LEVELS.index(control_levels[r.control]) < LEVELS.index(RELS[r.rel]): out.append(("RELATION_ABOVE_EVIDENCE", f"{r.control} ({control_levels[r.control]}) {r.rel} {ref(r.std, r.item)}"))
        if s.read == "SECONDARY" and r.rel in ("ADDRESSES", "EVIDENCE_FOR"): out.append(("READ_FROM_SECONDARY", f"{ref(r.std, r.item)}: edition read only through a secondary page"))
        if (d0 - date.fromisoformat(s.retrieved)).days > max_read_days: out.append(("READ_TOO_OLD", f"{r.std}: retrieved {s.retrieved}"))
        if it.from_date and date.fromisoformat(it.from_date) > d0 and r.rel in ("ADDRESSES", "EVIDENCE_FOR"): out.append(("NOT_YET_APPLICABLE", f"{ref(r.std, r.item)} applies from {it.from_date}; row says {r.rel}"))
    for c in (claims_compliance or set()): out.append(("COMPLIANCE_CLAIM", c))
    return out

def gaps(rows: list[Row], cat: Catalogue) -> dict[str, list[str]]:
    """Items of each complete catalogue that no row mentions (as mapped or as NA with a reason)."""
    seen = {ref(r.std, r.item) for r in rows if r.rel != "NA" or r.reason.strip()}
    return {sid: [i.id for i in cat.of(sid) if ref(sid, i.id) not in seen] for sid, s in cat.std.items() if s.complete}

def unmapped_controls(rows: list[Row], control_levels: dict[str, str]) -> list[str]:
    have = {r.control for r in rows if r.rel != "NA"}
    return sorted(c for c in control_levels if c not in have)

def coverage(rows: list[Row], cat: Catalogue) -> dict[str, dict]:
    """Per complete standard: items with at least one non-NA row, items marked NA with a reason, items with nothing."""
    out = {}
    for sid, s in cat.std.items():
        if not s.complete: continue
        its = [i.id for i in cat.of(sid)]
        mapped = {r.item for r in rows if r.std == sid and r.rel != "NA"}; na = {r.item for r in rows if r.std == sid and r.rel == "NA" and r.reason.strip()} - mapped
        out[sid] = dict(items=len(its), mapped=len(mapped & set(its)), na=len(na & set(its)), empty=len([i for i in its if i not in mapped and i not in na]))
    return out

def rendered(r: Row, cat: Catalogue, level: str) -> str:
    """The sentence an auditor reads.  The relation word, the control's claim level and the edition are all in it."""
    it = cat.items[ref(r.std, r.item)]; s = cat.std[r.std]
    return f"{r.control} ({level.replace('_', ' ')}) {r.rel.replace('_', ' ').lower()} {s.name} {r.item} {it.title} [{s.edition}]. Limit: {r.limit}"

def drift(rows: list[Row], old: Catalogue, new: Catalogue, std_old: str, std_new: str) -> dict:
    """What happens to rows written against one edition when the same item id is read in another edition.  Same id, same title; same id, different title; id absent."""
    same = changed = gone = 0; detail = []
    for r in rows:
        if r.std != std_old: continue
        a = old.items.get(ref(std_old, r.item)); b = new.items.get(ref(std_new, r.item))
        if b is None: gone += 1; detail.append((r.control, r.item, a.title if a else "?", None)); continue
        if a and a.title.strip().lower() == b.title.strip().lower(): same += 1
        else: changed += 1; detail.append((r.control, r.item, a.title if a else "?", b.title))
    return dict(same=same, changed=changed, gone=gone, detail=detail)

def digest(rows: list[Row], cat: Catalogue) -> str:
    """One hash over the rows and the editions they were written against.  It goes beside the bundle digest; a row edit, an edition change or a different catalogue edition changes it."""
    import hashlib, json
    d = dict(rows=[(r.control, r.std, r.item, r.edition, r.rel, r.limit, r.reason) for r in sorted(rows, key=lambda r: (r.control, r.std, r.item))], editions={k: (s.edition, s.retrieved, s.read) for k, s in sorted(cat.std.items())})
    return hashlib.sha256(json.dumps(d, sort_keys=True).encode()).hexdigest()
