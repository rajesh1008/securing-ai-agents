"""Chapter 43: answering a bank's model-risk team about Quill.
Three things: an inventory that says, component by component, whether a component meets the definition of a model in the 2026 interagency guidance (OCC Bulletin 2026-13 / SR 26-2,
read 2026-11-15), and what follows if it does not; a materiality tier; and a validation pack that maps the elements the guidance names to evidence items, with the evidence level of each (Chapter 35).
The definition test is the author's reading of the fetched text, written as code so that it can be argued with.  It is not legal advice and the bank's own policy decides."""
from __future__ import annotations
from dataclasses import dataclass, field

# The guidance's terms, as fetched (OCC Bulletin 2026-13, 2026-04-17): a model is "a complex quantitative method, system, or approach that applies statistical, economic, or financial theories to process input data
# into quantitative estimates"; it excludes "simple arithmetic calculations" and "deterministic rule-based processes and software where there are no statistical, economic, or financial theories underpinning their
# design or use"; "Generative AI and agentic AI models ... are not within the scope of this guidance".
IN_SCOPE, EXCLUDED_RULES, OUT_GENAI, NOT_A_MODEL = "IN_SCOPE_MODEL", "EXCLUDED_DETERMINISTIC", "OUT_OF_SCOPE_GENAI_AGENTIC", "NOT_A_MODEL"

@dataclass
class Component:
    id: str; name: str; chapter: str
    method: str          # "llm" | "statistical" | "ml_classifier" | "rules" | "arithmetic" | "crypto" | "agent"
    output: str          # "estimate" | "label" | "text" | "decision" | "record"
    feeds: str           # what its output can change: "payment" | "hold" | "alert" | "release" | "evidence" | "text_only"
    vendor: bool = False; owner: str = ""; exposure_usd: float = 0.0; gate_after: bool = True
    evidence: tuple = ()  # evidence item ids (Chapter 35 E-numbers)

def classify(c: Component) -> tuple[str, str]:
    if c.method in ("llm", "agent"): return OUT_GENAI, "generative or agentic: outside the guidance's scope; the bank's broader risk management applies"
    if c.method in ("rules", "arithmetic", "crypto"): return EXCLUDED_RULES, "deterministic, no statistical theory in its design"
    if c.method in ("statistical", "ml_classifier") and c.output in ("estimate", "label"): return IN_SCOPE, "statistical method producing a quantitative estimate or a label from one"
    return NOT_A_MODEL, "does not produce a quantitative estimate"

def tier(c: Component) -> str:
    """Author's tiering: what the output can reach, with and without a deterministic gate after it.  HIGH: can move money or release a change with no gate after it.
    MEDIUM: can move money or change a release, but a gate after it decides.  LOW: alerts, holds or text a person reads.  The bank's tiering policy replaces this."""
    reach = c.feeds in ("payment", "release")
    if reach and not c.gate_after: return "HIGH"
    if reach: return "MEDIUM"
    return "LOW"

ELEMENTS = [  # the elements the guidance names (bulletin text), with what the author treats as evidence for each
 ("conceptual_soundness", "why the method is fit for its use, and its limits", ("REVIEW", "UNIT")),
 ("outcomes_analysis", "outputs compared with what actually happened, on data like the use", ("LAB_SIM", "LAB_LIVE", "PRODUCTION")),
 ("ongoing_monitoring", "performance and limitations watched as products, clients and data change", ("PRODUCTION",)),   # only production data is evidence of monitoring
 ("development_and_use_testing", "testing during development, including where it breaks", ("UNIT", "LAB_SIM", "LAB_LIVE")),
 ("governance_roles", "policies, roles and responsibilities, named people", ("REVIEW",)),
 ("third_party", "what the vendor supplies and what the user validates of a vendor product", ("REVIEW", "LAB_LIVE")),
]
RANK = {"REVIEW": 0, "UNIT": 1, "LAB_SIM": 2, "LAB_LIVE": 3, "PRODUCTION": 4}

@dataclass
class Pack:
    rows: list = field(default_factory=list)   # (component, element, status, items)
    def gaps(self): return [(c, e) for c, e, s, _ in self.rows if s == "MISSING"]
    def weak(self): return [(c, e) for c, e, s, _ in self.rows if s == "WEAK"]

def pack(components: list[Component], items: dict[str, tuple[str, tuple]], element_map: dict[tuple[str, str], tuple]) -> Pack:
    """items: id -> (kind, tags).  element_map: (component id, element) -> evidence ids.  A row is OK if some item has an accepted kind, WEAK if items exist but none has one, MISSING if none."""
    p = Pack()
    for c in components:
        if classify(c)[0] in (EXCLUDED_RULES, NOT_A_MODEL): continue
        for el, _, accepted in ELEMENTS:
            if el == "third_party" and not c.vendor: continue
            ids = element_map.get((c.id, el), ())
            kinds = [items[i][0] for i in ids if i in items]
            s = "MISSING" if not kinds else "OK" if any(k in accepted for k in kinds) else "WEAK"
            p.rows.append((c.id, el, s, ids))
    return p

# ---------------------------------------------------------------- outcomes helpers used by the labs
def field_accuracy(pred: list[dict], truth: list[dict], fields: list[str]) -> dict[str, float]:
    return {f: sum(1 for p, t in zip(pred, truth) if p is not None and norm(p.get(f)) == norm(t.get(f))) / len(truth) for f in fields}
def agreement(runs: list[list[dict]], fields: list[str]) -> float:
    """Share of (item, field) cells on which every run gave the same normalised value."""
    n = len(runs[0]); cells = same = 0
    for i in range(n):
        for f in fields:
            vals = {norm(r[i].get(f)) if r[i] else None for r in runs}; cells += 1; same += len(vals) == 1
    return same / cells
def norm(v):
    if v is None: return None
    if isinstance(v, bool): return v
    s = str(v).strip().lower().replace(",", "").replace("$", "")
    try: return round(float(s), 2)
    except ValueError: return " ".join(s.split())
