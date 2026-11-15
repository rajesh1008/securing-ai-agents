"""Chapter 44: Ledgerly's people and two versions of the decision-rights register for Quill's security programme.
DRAFT is the register as it can be reconstructed from Chapters 1-43 (who the chapters say decided each kind of thing); REVISED is the one this chapter proposes.
People and titles are the book's composite roster plus two named here (Maya Brooks, Daniel Ortiz).  Nothing is from a real organisation."""
import sys, copy
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
from bulwark.ownership import Person, Decision, Register
import ch35_collect as B, ch41_rota as R41
P = {p.id: p for p in [
    Person("Ian", "Ian Walsh", "CISO", budget=True, risk_appetite=True, reports_to="Daniel"),
    Person("Rajesh", "the author", "security lead for Quill", reports_to="Ian"),
    Person("Kevin", "Kevin Brandt", "staff engineer, Quill platform", reports_to="Maya"),
    Person("Sophie", "Sophie Adler", "product owner, Quill payments", reports_to="Maya"),
    Person("Emily", "Emily Carter", "ML lead, prompts and models", reports_to="Maya"),
    Person("Maya", "Maya Brooks", "VP engineering", budget=True, reports_to="Daniel"),
    Person("Daniel", "Daniel Ortiz", "CFO", budget=True, risk_appetite=True),
    Person("Nina", "Nina Cole", "external red-team lead (contract)", internal=False),
]}
ALIAS = {"Ian Walsh": "Ian", "Sophie Adler": "Sophie", "Kevin Brandt": "Kevin", "Nina Cole": "Nina", "Emily Carter": "Emily", "security": "security"}
def controls_draft():
    return {c[0]: ALIAS.get(c[2], c[2]) for c in B.CONTROLS}
def jobs_draft():
    return [dict(id=j.id, owner=ALIAS.get(j.owner, j.owner), backup=ALIAS.get(j.backup, j.backup)) for j in R41.build("C").jobs]
D = Decision
DRAFT = [  # reconstructed from the chapters: what the text says, or what it implies by who acted
 D("D01", "accept a residual risk", "security", requested_by=("Sophie", "Kevin"), max_days=0, on_timeout="", needs_risk_appetite=True),
 D("D02", "grant a waiver on a control", "Kevin", responsible=("Kevin",), requested_by=("Kevin", "Sophie"), max_days=0, on_timeout=""),
 D("D03", "ship a prompt release the gate marked REVIEW", "Emily", requested_by=("Emily", "Sophie"), max_days=2, on_timeout="accept"),
 D("D04", "move the model alias or adopt a new model version", "Emily", responsible=("Kevin",), requested_by=("Emily",), max_days=0, on_timeout=""),
 D("D05", "add a tool or MCP server to a loadout", "Kevin", requested_by=("Kevin", "Sophie"), max_days=0, on_timeout=""),
 D("D06", "add a new effect kind (refunds, payroll)", "Sophie", requested_by=("Sophie",), max_days=0, on_timeout=""),
 D("D07", "onboard a tenant with a non-standard configuration", "Sophie", requested_by=("Sophie",), max_days=5, on_timeout="accept"),
 D("D08", "enter or leave a degraded mode", "Kevin", max_days=1, on_timeout="escalate:Ian"),
 D("D09", "close an incident case", "Ian", responsible=("Rajesh",), max_days=30, on_timeout="escalate:Ian"),
 D("D10", "send a customer or regulator notice", "Ian, Sophie", consulted=("legal",), max_days=3, on_timeout="escalate:Daniel"),
 D("D11", "answer a customer security questionnaire or model-risk pack", "security", responsible=("Rajesh",), requested_by=("Sophie",), max_days=10, on_timeout=""),
 D("D12", "change an egress allow-list entry", "Kevin", requested_by=("Kevin", "Sophie"), max_days=2, on_timeout="accept"),
 D("D13", "acknowledge a detector baseline change", "Ian", requested_by=("Sophie",), max_days=7, on_timeout=""),
 D("D14", "fund or staff the programme (budget, headcount)", "Ian", requested_by=("Rajesh",), max_days=0, on_timeout="", needs_budget=True),
 D("D15", "accept a model or tool vendor", "Kevin", requested_by=("Kevin", "Emily"), max_days=0, on_timeout=""),
]
def revised_decisions():
    d = [
     D("D01", "accept a residual risk", "Ian", responsible=("Rajesh",), consulted=("Sophie",), requested_by=("Sophie", "Kevin", "Emily"), max_days=10, on_timeout="escalate:Daniel", needs_risk_appetite=True, delegate=(("Rajesh", "below the low-impact line in the risk register, with a review date"),)),
     D("D02", "grant a waiver on a control", "Rajesh", responsible=("Rajesh",), consulted=("Kevin",), requested_by=("Kevin", "Sophie", "Emily"), max_days=5, on_timeout="deny"),
     D("D03", "ship a prompt release the gate marked REVIEW", "Rajesh", responsible=("Emily",), consulted=("Sophie",), requested_by=("Emily", "Sophie"), max_days=3, on_timeout="hold"),
     D("D04", "move the model alias or adopt a new model version", "Rajesh", responsible=("Emily", "Kevin"), requested_by=("Emily",), max_days=5, on_timeout="hold"),
     D("D05", "add a tool or MCP server to a loadout", "Emily", responsible=("Kevin",), consulted=("Rajesh",), requested_by=("Kevin", "Sophie"), max_days=5, on_timeout="hold"),
     D("D06", "add a new effect kind (refunds, payroll)", "Ian", responsible=("Rajesh", "Kevin"), consulted=("Sophie",), requested_by=("Sophie",), max_days=15, on_timeout="hold", needs_risk_appetite=True),
     D("D07", "onboard a tenant with a non-standard configuration", "Rajesh", responsible=("Kevin",), requested_by=("Sophie",), max_days=5, on_timeout="hold", delegate=(("Kevin", "configurations inside the published options"),)),
     D("D08", "enter or leave a degraded mode", "Kevin", responsible=("Kevin",), consulted=("Rajesh",), max_days=1, on_timeout="escalate:Ian"),
     D("D09", "close an incident case", "Ian", responsible=("Rajesh",), requested_by=("Rajesh",), max_days=30, on_timeout="escalate:Daniel"),
     D("D10", "send a customer or regulator notice", "Ian", responsible=("Rajesh", "Sophie"), consulted=("Daniel",), max_days=3, on_timeout="escalate:Daniel"),
     D("D11", "answer a customer security questionnaire or model-risk pack", "Rajesh", responsible=("Rajesh", "Emily"), requested_by=("Sophie",), max_days=10, on_timeout="escalate:Ian"),
     D("D12", "change an egress allow-list entry", "Rajesh", responsible=("Kevin",), requested_by=("Kevin", "Sophie"), max_days=2, on_timeout="deny"),
     D("D13", "acknowledge a detector baseline change", "Sophie", responsible=("Sophie",), consulted=("Rajesh",), requested_by=("Kevin",), max_days=7, on_timeout="escalate:Rajesh"),
     D("D14", "fund or staff the programme (budget, headcount)", "Maya", responsible=("Ian",), requested_by=("Rajesh", "Ian"), max_days=30, on_timeout="escalate:Daniel", needs_budget=True),
     D("D15", "accept a model or tool vendor", "Ian", responsible=("Rajesh", "Kevin"), consulted=("Daniel",), requested_by=("Kevin", "Emily"), max_days=20, on_timeout="hold", needs_risk_appetite=True),
    ]
    return d
def controls_rev1():
    c = controls_draft(); c.update({"C07": "Kevin", "C19": "Kevin"})   # first fix: Nina (external) owned two controls; moved to Kevin
    return c
def controls_revised():
    c = controls_draft(); c.update({"C07": "Emily", "C19": "Rajesh", "C10": "Emily", "C05": "Rajesh", "C08": "Emily"})   # second fix: spread so that nobody holds more than eight
    return c
def jobs_revised():
    j = jobs_draft()
    for x in j:
        if x["owner"] == "security": x["owner"] = "Rajesh"
        if x["backup"] == "security": x["backup"] = "Rajesh"
        if x["id"] == "J12": x["owner"], x["backup"] = "Rajesh", "Kevin"   # red-team exercise: owned inside, Nina runs it
    j += [dict(id="J31", owner="Sophie", backup="Kevin"), dict(id="J32", owner="Sophie", backup="Ian")]
    return j
DEPUTY = {"D01": "Daniel", "D02": "Ian", "D03": "Ian", "D04": "Ian", "D05": "Rajesh", "D06": "Daniel", "D07": "Ian", "D08": "Rajesh", "D09": "Daniel", "D10": "Daniel",
          "D11": "Ian", "D12": "Ian", "D13": "Rajesh", "D14": "Daniel", "D15": "Daniel"}
def draft(): return Register(P, copy.deepcopy(DRAFT), controls_draft(), jobs_draft())
def rev1():
    d = revised_decisions(); [x.__setattr__("accountable", "Rajesh") for x in d if x.id == "D05"]
    return Register(P, d, controls_rev1(), jobs_revised())
def rev2(): return Register(P, revised_decisions(), controls_revised(), jobs_revised())
def revised():
    d = revised_decisions()
    for x in d: x.deputy = DEPUTY[x.id]
    return Register(P, d, controls_revised(), jobs_revised())
