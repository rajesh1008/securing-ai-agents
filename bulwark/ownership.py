"""Chapter 44: decision rights for an agent security programme, written as data that can be checked.
A Person is someone who can be asked; a Decision is a kind of decision the programme has to make again and again, with one accountable person, the people who do the work,
who must be consulted, a deadline in days and what happens when the deadline passes.  `issues()` checks the register; `depart()` says what a departure orphans; `route()` is the deterministic router."""
from __future__ import annotations
from dataclasses import dataclass, field

@dataclass
class Person:
    id: str; name: str; title: str; internal: bool = True; budget: bool = False; risk_appetite: bool = False   # may accept risk on the company's behalf
    reports_to: str = ""
@dataclass
class Decision:
    id: str; name: str; accountable: str; responsible: tuple = (); consulted: tuple = (); requested_by: tuple = ()
    max_days: int = 0; on_timeout: str = ""   # "escalate:<person>" | "deny" | "hold" | "" (nothing) | "accept" (silent acceptance)
    needs_risk_appetite: bool = False; needs_budget: bool = False; delegate: tuple = ()   # (person, limit text) pairs for routine cases
    deputy: str = ""   # decides when the accountable person is away; added after the departure test of lab 1
@dataclass
class Register:
    people: dict; decisions: list; controls: dict = field(default_factory=dict); jobs: list = field(default_factory=list); k_concentration: int = 8; check_deputy: bool = True
    def p(self, x): return self.people.get(x)
    def issues(self) -> list[tuple[str, str]]:
        out = []
        for d in self.decisions:
            acc = d.accountable
            if not acc: out.append(("NO_ACCOUNTABLE", d.id)); continue
            if "," in acc or "+" in acc: out.append(("SHARED_ACCOUNTABLE", d.id))
            pa = self.p(acc)
            if pa is None: out.append(("ACCOUNTABLE_NOT_A_PERSON", f"{d.id}:{acc}")); continue
            if not pa.internal: out.append(("ACCOUNTABLE_OUTSIDE", f"{d.id}:{acc}"))
            if d.needs_risk_appetite and not pa.risk_appetite: out.append(("NO_AUTHORITY_TO_ACCEPT", f"{d.id}:{acc}"))
            if d.needs_budget and not pa.budget: out.append(("NO_BUDGET_AUTHORITY", f"{d.id}:{acc}"))
            if acc in d.requested_by: out.append(("SELF_APPROVAL", f"{d.id}:{acc}"))
            if self.check_deputy:
                if not d.deputy: out.append(("NO_DEPUTY", d.id))
                elif d.deputy == acc: out.append(("DEPUTY_IS_ACCOUNTABLE", d.id))
                elif d.deputy in d.requested_by: out.append(("DEPUTY_SELF_APPROVAL", f"{d.id}:{d.deputy}"))
                elif self.p(d.deputy) is None: out.append(("UNKNOWN_PERSON", f"{d.id}:{d.deputy}"))
                elif d.needs_risk_appetite and not self.p(d.deputy).risk_appetite: out.append(("DEPUTY_NO_AUTHORITY", f"{d.id}:{d.deputy}"))
            if not d.max_days: out.append(("NO_DEADLINE", d.id))
            if d.on_timeout in ("", "accept"): out.append(("SILENT_TIMEOUT" if d.on_timeout == "accept" else "NO_TIMEOUT_RULE", d.id))
            elif d.on_timeout.startswith("escalate:"):
                e = d.on_timeout.split(":", 1)[1]
                if e == acc or self.p(e) is None: out.append(("BAD_ESCALATION", f"{d.id}:{e}"))
            for x in d.responsible + d.consulted:
                if self.p(x) is None: out.append(("UNKNOWN_PERSON", f"{d.id}:{x}"))
        for c, owner in sorted(self.controls.items()):
            po = self.p(owner)
            if po is None: out.append(("CONTROL_OWNER_NOT_A_PERSON", f"{c}:{owner}"))
            elif not po.internal: out.append(("CONTROL_OWNER_OUTSIDE", f"{c}:{owner}"))
        for j in self.jobs:
            for who in (j.get("owner"), j.get("backup")):
                if who and self.p(who) is None: out.append(("JOB_PERSON_NOT_A_PERSON", f"{j['id']}:{who}"))
        load = {}
        for d in self.decisions: load[d.accountable] = load.get(d.accountable, 0) + 1
        for c, o in self.controls.items(): load[o] = load.get(o, 0) + 1
        for who, n in sorted(load.items()):
            if n > self.k_concentration: out.append(("CONCENTRATION", f"{who}:{n}"))
        return out
    def depart(self, who: str) -> dict:
        """What is orphaned if `who` leaves today: decisions they are accountable for with no delegate, controls they own, jobs where they are owner and the backup is also gone or absent."""
        dec = [d.id for d in self.decisions if d.accountable == who and (not d.deputy or d.deputy == who)]
        dep = [d.id for d in self.decisions if d.accountable == who and d.deputy and d.deputy != who]
        ctl = [c for c, o in self.controls.items() if o == who]
        jobs = [j["id"] for j in self.jobs if j.get("owner") == who and (not j.get("backup") or j.get("backup") == who)]
        backed = [j["id"] for j in self.jobs if j.get("owner") == who and j.get("backup") and j.get("backup") != who]
        return dict(decisions=dec, decisions_to_deputy=dep, controls=ctl, jobs_orphaned=jobs, jobs_to_backup=backed)
    def route(self, kind: str) -> tuple[str, bool]:
        """Deterministic router: the request form's kind field picks the decision; returns (accountable, approval_required).  An unknown kind goes to the head with approval required."""
        for d in self.decisions:
            if d.id == kind: return d.accountable, True
        head = [p.id for p in self.people.values() if p.risk_appetite]
        return (head[0] if head else ""), True
