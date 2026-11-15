"""Chapter 20: architectural defences, as small executable designs.  A design decides, for a sequence of proposed tool calls, which calls execute.  The designs here do not look at wording.
  Flat        every tool is always available (the starting point of Chapters 1 to 3 without the controls of Part II)
  Fence       after the first read of untrusted text, tools that act (send, pay, write, http) are revoked and never granted back (the fence of 2611.11506)
  PlanLock    the plan is fixed before any untrusted text is read: which tools, in what order, with which arguments bound to a constant, to the registry or to a typed field; any other call is refused
  Split       a reader with no tools turns the document into typed fields; the planner never sees the document; the planner's calls are the plan's calls with arguments filled from the fields
A proposal is a Call(tool, args).  A Plan is a list of Step(tool, bind) with bind mapping each argument to ("const", v), ("registry", key) or ("field", name)."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

ACTS = {"send_email", "pay_invoice", "update_vendor", "raw_http"}
READS = {"read_invoice", "search_books"}

@dataclass
class Call: tool: str; args: dict = field(default_factory=dict)
@dataclass
class Step: tool: str; bind: dict = field(default_factory=dict)

class Flat:
    name = "flat"
    def __init__(self, **kw): self.log = []
    def allow(self, c: Call, plan=None, registry=None, fields=None) -> tuple[bool, str]:
        self.log.append((c.tool, True)); return True, "ok"
    def read(self): pass

class Fence(Flat):
    name = "fence"
    def __init__(self, **kw): self.tainted = False; self.log = []
    def read(self): self.tainted = True
    def allow(self, c: Call, plan=None, registry=None, fields=None):
        if self.tainted and c.tool in ACTS: self.log.append((c.tool, False)); return False, "REVOKED_AFTER_UNTRUSTED_READ"
        self.log.append((c.tool, True)); return True, "ok"

class PlanLock(Flat):
    name = "planlock"
    def __init__(self, plan: list[Step], registry: dict, fields: Optional[dict] = None): self.plan, self.registry, self.fields, self.pos, self.log = plan, registry, fields or {}, 0, []
    def read(self): pass
    def expected(self, step: Step) -> dict:
        out = {}
        for a, (kind, v) in step.bind.items(): out[a] = v if kind == "const" else (self.registry.get(v) if kind == "registry" else self.fields.get(v))
        return out
    def allow(self, c: Call, plan=None, registry=None, fields=None):
        if self.pos >= len(self.plan): self.log.append((c.tool, False)); return False, "PLAN_EXHAUSTED"
        st = self.plan[self.pos]
        if c.tool != st.tool: self.log.append((c.tool, False)); return False, "NOT_IN_PLAN"
        exp = self.expected(st)
        if c.args != exp: self.log.append((c.tool, False)); return False, "ARGUMENT_NOT_BOUND_TO_PLAN"
        self.pos += 1; self.log.append((c.tool, True)); return True, "ok"

class Split(PlanLock):
    """The planner sees fields, never text.  A hostile document can change a field's value; it cannot propose a call, so the only calls are the plan's.  The deterministic checks on field values (against books) are the caller's."""
    name = "split"
    def propose(self, hostile_call: Optional[Call], plan_call: Call) -> Call:
        return plan_call        # the document's influence is on field values only; a call it asked for is never formed

def run(design, calls: list[Call], reads_first: bool = True):
    """Feed calls in order; return list of (call, allowed, reason).  reads_first: the first call is the read of the document."""
    out = []
    for c in calls:
        if c.tool in READS: design.read()
        ok, why = design.allow(c); out.append((c, ok, why))
    return out
