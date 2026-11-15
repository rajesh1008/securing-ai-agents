"""Chapter 45: a programme described as data, and a checker that asks the book's one non-negotiable question of it.
Never give an untrusted instruction a direct path to credential disclosure, unrestricted egress, privileged execution or irreversible payment.
A Programme lists the sources the model reads (each trusted or not), the tools it can call (each with an effect class) and the gates on each tool.
A gate is deterministic (code that reads a record the attacker did not write), human (a person who sees something), or model (another model call).
Only a deterministic gate bound to a trusted record bounds a dangerous tool.  Memory that accepts writes from an untrusted source becomes an untrusted source itself.
No model calls."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

DANGEROUS = {"PAYMENT", "EGRESS", "EXEC", "CREDENTIAL", "ACCOUNT"}   # ACCOUNT: changes who controls an account (takeover)
SURFACES = ["Input", "Context assembly", "Model", "Output", "Tool call", "Tool result", "Memory", "State", "Egress", "Identity", "Runtime", "Human"]
LEVELS = ["review", "unit", "scenario", "lab-sim", "lab-live", "production"]

@dataclass
class Gate:
    kind: str                    # 'deterministic' | 'human' | 'model'
    binds: str = ""              # what the gate compares against, e.g. 'payee registry'
    trusted_record: bool = False # the record it compares against is one the attacker cannot write
    shows_evidence: bool = True  # human gates only: does the approver see the source span and the effect, or a model's summary
    writable_from: tuple = ()    # ids of sources whose text can change the record this gate compares against (through any workflow, however indirect)

@dataclass
class Source:
    id: str; trusted: bool; note: str = ""

@dataclass
class Tool:
    id: str; effect: str; gates: list = field(default_factory=list); note: str = ""

@dataclass
class Control:
    id: str; surface: str; owner: str; level: str   # level: highest evidence kind attached

@dataclass
class Programme:
    name: str; stage: str
    sources: list; tools: list
    memory_write_gated: Optional[bool] = None       # None: no memory
    controls: list = field(default_factory=list)
    unreadable: list = field(default_factory=list)  # tool ids a given source cannot influence (split reader / planner, Chapter 20)

    def effective_sources(self):
        out = list(self.sources)
        if self.memory_write_gated is False: out.append(Source("memory", False, "writable from untrusted text"))
        return out

def classify(tool: Tool, source: Optional[str] = None) -> str:
    """BOUNDED / HUMAN_ONLY / MODEL_ONLY / OPEN for a dangerous tool.  With a source id, a deterministic gate whose record that source can write (writable_from) does not bound the path."""
    if tool.effect not in DANGEROUS: return "NOT_DANGEROUS"
    if any(g.kind == "deterministic" and g.trusted_record and (source is None or source not in g.writable_from) for g in tool.gates): return "BOUNDED"
    if any(g.kind == "deterministic" and g.trusted_record for g in tool.gates): return "RECORD_WRITABLE"
    if any(g.kind == "human" and g.shows_evidence for g in tool.gates): return "HUMAN_ONLY"
    if any(g.kind == "human" for g in tool.gates): return "HUMAN_BLIND"
    if any(g.kind == "model" for g in tool.gates): return "MODEL_ONLY"
    return "OPEN"

def findings(p: Programme) -> list:
    """One finding per (untrusted source, dangerous tool) path that is not bounded by a deterministic gate on a trusted record."""
    out = []
    for s in p.effective_sources():
        if s.trusted: continue
        for t in p.tools:
            if t.effect not in DANGEROUS or (s.id, t.id) in {(u[0], u[1]) for u in p.unreadable}: continue
            c = classify(t, s.id)
            if c != "BOUNDED": out.append((s.id, t.id, t.effect, c))
    return out

def surface_coverage(p: Programme) -> dict:
    cov = {s: [] for s in SURFACES}
    for c in p.controls: cov[c.surface].append(c)
    return cov

def summary(p: Programme) -> dict:
    f = findings(p); cov = surface_coverage(p)
    lv = {l: sum(c.level == l for c in p.controls) for l in LEVELS}
    dang = [t for t in p.tools if t.effect in DANGEROUS]
    return dict(programme=p.name, stage=p.stage, sources=len(p.effective_sources()), untrusted=sum(not s.trusted for s in p.effective_sources()),
                tools=len(p.tools), dangerous=len(dang), bounded=sum(classify(t) == "BOUNDED" for t in dang), paths_unbounded=len(f),
                by_class={k: sum(1 for x in f if x[3] == k) for k in ("OPEN", "MODEL_ONLY", "HUMAN_BLIND", "HUMAN_ONLY", "RECORD_WRITABLE")},
                controls=len(p.controls), surfaces_covered=sum(1 for v in cov.values() if v), surfaces_empty=[s for s, v in cov.items() if not v],
                evidence_levels=lv, owners=len({c.owner for c in p.controls}))

def check_owners(p: Programme) -> list:
    """Controls whose owner is a role, not a person (Chapter 44's first finding)."""
    ROLES = {"security", "platform", "engineering", "ops", "the team", "it", "support", "claims", ""}
    return [c.id for c in p.controls if c.owner.strip().lower() in ROLES]
