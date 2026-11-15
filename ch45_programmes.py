#!/usr/bin/env python3
"""Chapter 45, lab 1 (no model): four programmes written as data, each at the stage it was first deployed and the stage a year later, checked with bulwark.casestudy.
A: Quill at Ledgerly (the book's running project, as built by Chapter 44).  B: Cedar Row Telecom support agent.  C: Fieldstone Software coding agent.  D: Harbour and Vale Mutual claims assistant (the breach).
B, C and D are composites invented for this chapter; their gates and controls are the author's description, not measurements.  Writes results/ch45_programmes.json and .log."""
import sys, json
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
from bulwark.casestudy import *
R = lambda b: Gate("deterministic", b, True)          # deterministic, trusted record
CAP = lambda b: Gate("deterministic", b, False)       # deterministic, but the record is a number the model or sender can shape
HUM = Gate("human", "approver sees span and effect", shows_evidence=True)
HUMB = Gate("human", "approver sees a model summary", shows_evidence=False)
MOD = Gate("model", "model checks")

SURF = {"C01": "Identity", "C02": "Tool call", "C03": "State", "C04": "Egress", "C05": "Tool call", "C06": "Tool call", "C07": "Memory", "C08": "Tool result", "C09": "Model", "C10": "Runtime",
        "C11": "Runtime", "C12": "Output", "C13": "Human", "C14": "Context assembly", "C15": "Identity", "C16": "Human", "C17": "State", "C18": "Runtime", "C19": "Input", "C20": "Model"}
LVL = {"measured_live_model": "lab-live", "measured_in_simulation": "lab-sim", "tested": "unit"}
def quill_controls():
    """The twenty controls of the Chapter 35 bundle with Chapter 44's owners; the surface assignment is this chapter's own reading."""
    import ch35_collect as C, ch44_org as O
    own = O.revised().controls
    return [Control(c[0], SURF[c[0]], own[c[0]], LVL.get(c[5], c[5])) for c in sorted(C.CONTROLS, key=lambda c: c[0])]
def A_day0():
    return Programme("A Quill", "day 0 (Chapter 1)", [Source("invoice", False), Source("ticket", False), Source("vendor_portal", False), Source("owner_chat", True)],
        [Tool("pay_invoice", "PAYMENT", [CAP("amount cap")]), Tool("send_email", "EGRESS"), Tool("http_fetch", "EGRESS"), Tool("issue_refund", "PAYMENT", [CAP("amount cap")]), Tool("read_ledger", "READ")],
        memory_write_gated=False, controls=[Control("C00", "Model", "Rajesh", "review")])
def A_final():
    return Programme("A Quill", "month 12 (Chapter 44)", [Source("invoice", False), Source("ticket", False), Source("vendor_portal", False), Source("owner_chat", True)],
        [Tool("pay_invoice", "PAYMENT", [R("payee registry"), R("invoice binding"), HUM]), Tool("send_email", "EGRESS", [R("contact book and allow-list")]), Tool("http_fetch", "EGRESS", [R("egress allow-list")]),
         Tool("issue_refund", "PAYMENT", [R("original payment destination"), HUM]), Tool("run_code", "EXEC", [R("sandbox rung R3")]), Tool("read_ledger", "READ")],
        memory_write_gated=True,
        controls=quill_controls())

def B_day0():
    return Programme("B Cedar Row", "launch", [Source("customer_chat", False), Source("ticket_history", False), Source("kb", True), Source("agent_console", True)],
        [Tool("issue_credit", "PAYMENT", [CAP("daily cap per account")]), Tool("change_contact", "ACCOUNT", [MOD]), Tool("send_sms", "EGRESS", [CAP("rate limit")]), Tool("lookup_account", "READ")],
        memory_write_gated=None, controls=[Control("B01", "Input", "Priya", "review"), Control("B02", "Model", "Priya", "scenario"), Control("B03", "Human", "Priya", "review")])
def B_final():
    return Programme("B Cedar Row", "month 12", [Source("customer_chat", False), Source("ticket_history", False), Source("kb", True), Source("agent_console", True)],
        [Tool("issue_credit", "PAYMENT", [R("original payment method"), CAP("daily cap per account")]), Tool("change_contact", "ACCOUNT", [R("verified second factor from the account record"), HUM]),
         Tool("send_sms", "EGRESS", [R("number on file and templates")]), Tool("lookup_account", "READ")],
        controls=[Control("B01", "Input", "Priya", "lab-live"), Control("B02", "Model", "Priya", "lab-live"), Control("B03", "Human", "Marcus", "scenario"), Control("B04", "Identity", "Marcus", "lab-sim"), Control("B05", "Tool call", "Marcus", "unit"),
                  Control("B06", "Egress", "Marcus", "unit"), Control("B07", "Output", "Priya", "unit"), Control("B08", "State", "Marcus", "scenario")])

def C_day0():
    return Programme("C Fieldstone", "pilot", [Source("issue_text", False), Source("web_docs", False), Source("mcp_tool_descriptions", False), Source("dependency_readme", False), Source("developer", True)],
        [Tool("shell", "EXEC", [HUMB]), Tool("env_tokens", "CREDENTIAL"), Tool("http_get", "EGRESS"), Tool("git_push", "READ" if False else "EGRESS", [R("branch protection")]), Tool("read_repo", "READ")],
        memory_write_gated=None, controls=[Control("F01", "Human", "Tomasz", "review")])
def C_final():
    return Programme("C Fieldstone", "month 12", [Source("issue_text", False), Source("web_docs", False), Source("mcp_tool_descriptions", False), Source("dependency_readme", False), Source("developer", True)],
        [Tool("shell", "EXEC", [R("sandbox rung R3 with no network")]), Tool("env_tokens", "CREDENTIAL", [R("no credential in the box; brokered per task")]), Tool("http_get", "EGRESS", [R("proxy allow-list")]), Tool("git_push", "EGRESS", [R("branch protection"), R("push to agent branches only")]), Tool("read_repo", "READ")],
        controls=[Control("F01", "Human", "Tomasz", "scenario"), Control("F02", "Runtime", "Tomasz", "lab-sim"), Control("F03", "Tool result", "Aisha", "lab-sim"), Control("F04", "Identity", "Aisha", "unit"), Control("F05", "Egress", "Aisha", "lab-sim"),
                  Control("F06", "Tool call", "Aisha", "unit"), Control("F07", "Context assembly", "Tomasz", "lab-live")])

def D_deployed():
    return Programme("D Harbour and Vale", "as deployed (day 0 of the breach)", [Source("claimant_email", False), Source("attachments", False), Source("adjuster_console", True), Source("policy_system", True)],
        [Tool("send_correspondence", "EGRESS", [MOD, CAP("max 5 attachments")]), Tool("fetch_url", "EGRESS"), Tool("read_claim", "READ"), Tool("write_note", "READ")],
        memory_write_gated=False, controls=[Control("H01", "Input", "Louise", "scenario"), Control("H02", "Model", "Louise", "review"), Control("H03", "Output", "Louise", "scenario"), Control("H04", "Human", "Louise", "review")])
def D_fixed():
    return Programme("D Harbour and Vale", "after the breach (day 120)", [Source("claimant_email", False), Source("attachments", False), Source("adjuster_console", True), Source("policy_system", True)],
        [Tool("send_correspondence", "EGRESS", [R("parties named on the claim record"), CAP("max 5 attachments")]), Tool("fetch_url", "EGRESS", [R("proxy allow-list")]), Tool("read_claim", "READ"), Tool("write_note", "READ")],
        memory_write_gated=True, controls=[Control("H01", "Input", "Louise", "scenario"), Control("H02", "Model", "Louise", "lab-live"), Control("H03", "Output", "Louise", "scenario"), Control("H04", "Human", "Louise", "scenario"),
                  Control("H05", "Memory", "Ravi", "lab-sim"), Control("H06", "Egress", "Ravi", "lab-sim"), Control("H07", "Tool call", "Ravi", "unit"), Control("H08", "Identity", "Ravi", "unit")])

STAGES = [A_day0, A_final, B_day0, B_final, C_day0, C_final, D_deployed, D_fixed]
def main():
    L = []; out = []
    L.append(f"{'programme':20} {'stage':34} src untr tools dang bound open model h-blind h-ev ctrl surf owners")
    for f in STAGES:
        p = f(); s = summary(p); out.append(s); c = s["by_class"]
        L.append(f"{p.name:20} {p.stage:34} {s['sources']:3} {s['untrusted']:4} {s['tools']:5} {s['dangerous']:4} {s['bounded']:5} {c['OPEN']:4} {c['MODEL_ONLY']:5} {c['HUMAN_BLIND']:7} {c['HUMAN_ONLY']:4} {s['controls']:4} {s['surfaces_covered']:4} {s['owners']:6}")
    L.append("")
    for f in STAGES:
        p = f(); fi = findings(p)
        L.append(f"{p.name} / {p.stage}: " + ("; ".join(f"{a}->{b} ({e}, {c})" for a, b, e, c in fi) if fi else "no unbounded dangerous path") + (f"; surfaces with no control: {', '.join(summary(p)['surfaces_empty'])}"))
    L.append("")
    for f in (A_final, B_final, C_final, D_fixed):
        p = f(); lv = summary(p)["evidence_levels"]; L.append(f"{p.name}: evidence levels {lv}; role owners {check_owners(p)}")
    (here / "results/ch45_programmes.json").write_text(json.dumps(out, indent=1)); (here / "results/ch45_programmes.log").write_text("\n".join(L) + "\n"); print("\n".join(L))
if __name__ == "__main__": main()
