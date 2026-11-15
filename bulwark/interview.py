"""Chapter 46: a work-sample exercise for an AI security engineer, scored by the checker and not by the interviewer's impression.
An Exercise is a programme (bulwark.casestudy) at its weak stage plus, for each dangerous tool, a menu of fixes. Each option is a Gate.  The candidate picks one option per tool (and says whether memory writes are gated).
The score is what remains when the picks are applied to the programme and bulwark.casestudy.findings is re-run: residual unbounded paths.  A second, deliberately weak scorer counts interview vocabulary in the candidate's prose.
No model calls."""
from __future__ import annotations
import copy, re
from dataclasses import dataclass, field
from bulwark.casestudy import Gate, Programme, findings, DANGEROUS

KINDS = ["CAP", "MODEL", "HUMAN_BLIND", "HUMAN_EVID", "TRAP", "RECORD"]

@dataclass
class Option:
    id: str; kind: str; label: str; gate: Gate

@dataclass
class Exercise:
    name: str; programme: Programme; menu: dict          # tool id -> list[Option]
    def option(self, tool, oid):
        for o in self.menu.get(tool, []):
            if o.id == oid: return o
        return None
    def dangerous_tools(self): return [t.id for t in self.programme.tools if t.effect in DANGEROUS]

def apply(ex: Exercise, picks: dict, memory_gated: bool | None = None) -> Programme:
    """The programme with each picked option's gate replacing the tool's gates.  A tool with no valid pick keeps what it had."""
    p = copy.deepcopy(ex.programme)
    for t in p.tools:
        o = ex.option(t.id, picks.get(t.id)) if t.id in picks else None
        if o: t.gates = [o.gate]
    if memory_gated is not None and p.memory_write_gated is False: p.memory_write_gated = memory_gated
    return p

def score(ex: Exercise, answer: dict) -> dict:
    """answer: {'fixes': {tool: option_id}, 'memory': bool, 'findings': optional list of [source, tool]}"""
    before = findings(ex.programme); p = apply(ex, answer.get("fixes", {}), answer.get("memory"))
    after = findings(p); out = dict(before=len(before), residual=len(after), by_class={})
    for _, _, _, c in after: out["by_class"][c] = out["by_class"].get(c, 0) + 1
    claimed = {tuple(x) for x in answer.get("findings", [])}; truth = {(a, b) for a, b, _, _ in before}
    if claimed:
        out["recall"] = len(claimed & truth) / len(truth); out["precision"] = len(claimed & truth) / len(claimed)
    out["fixed_tools"] = sum(1 for t in ex.dangerous_tools() if t in answer.get("fixes", {}) and not [f for f in after if f[1] == t])
    out["pass"] = len(after) == 0
    return out

VOCAB = ["least privilege", "defense in depth", "defence in depth", "zero trust", "guardrail", "human in the loop", "human-in-the-loop", "allow-list", "allowlist", "sandbox", "rate limit",
         "monitoring", "audit", "red team", "prompt injection", "principle of least", "threat model", "validation", "sanitiz", "separation of duties", "observability", "least-privilege", "layered"]
def vocab_score(text: str) -> int:
    t = text.lower(); return len({v.replace("defence", "defense").replace("-", " ") for v in VOCAB if v.replace("-", " ") in t.replace("-", " ")})

def exercises() -> list:
    import ch45_programmes as P
    G = Gate
    def O(i, k, label, g): return Option(i, k, label, g)
    B = Exercise("Cedar Row support agent (launch)", P.B_day0(), {
        "issue_credit": [O("a", "CAP", "daily cap per account", G("deterministic", "daily cap", False)), O("b", "MODEL", "a second model reads the customer's plea", G("model", "model checks")),
                         O("c", "HUMAN_BLIND", "a supervisor approves the agent's one-line summary", G("human", "summary", shows_evidence=False)),
                         O("d", "RECORD", "credit only to the original payment method on the billing record", G("deterministic", "original payment method", True))],
        "change_contact": [O("a", "MODEL", "a model confirms the caller is the account holder", G("model", "model checks")),
                           O("b", "TRAP", "caller must quote the date of birth and address, matched to the facts held in the ticket history", G("deterministic", "facts from ticket history", True, writable_from=("ticket_history", "customer_chat"))),
                           O("c", "HUMAN_EVID", "an agent sees the request and the verification result and approves", G("human", "approver sees span and effect", shows_evidence=True)),
                           O("d", "RECORD", "a one-time code to the second factor already on the account record", G("deterministic", "second factor on the account record", True))],
        "send_sms": [O("a", "CAP", "rate limit of 5 texts per account per day", G("deterministic", "rate limit", False)), O("b", "RECORD", "send only to the number on file, using fixed templates", G("deterministic", "number on file and templates", True))]})
    C = Exercise("Fieldstone coding agent (pilot)", P.C_day0(), {
        "shell": [O("a", "HUMAN_BLIND", "the developer approves each command in a one-line prompt", G("human", "prompt", shows_evidence=False)), O("b", "HUMAN_EVID", "the developer sees the full command, the working directory and the diff of what it will touch", G("human", "approver sees span and effect", shows_evidence=True)),
                  O("c", "MODEL", "a second model screens commands for danger", G("model", "model checks")), O("d", "RECORD", "run in a sandbox with no network and a read-only home", G("deterministic", "sandbox rung R3 with no network", True))],
        "env_tokens": [O("a", "MODEL", "the system prompt forbids reading tokens", G("model", "prompt")), O("b", "TRAP", "redact strings that look like tokens from tool output", G("deterministic", "pattern list", False)), O("c", "RECORD", "no credential in the box; a broker issues one per task", G("deterministic", "brokered per task", True))],
        "http_get": [O("a", "TRAP", "block a list of known bad domains", G("deterministic", "blocklist", False)), O("b", "MODEL", "a model judges whether the URL is safe", G("model", "model checks")), O("c", "RECORD", "proxy allow-list of package hosts and the project's documentation", G("deterministic", "proxy allow-list", True))],
        "git_push": [O("a", "RECORD", "branch protection plus push to agent branches only", G("deterministic", "branch protection", True)), O("b", "MODEL", "a model reviews the diff before push", G("model", "model checks"))]})
    D = Exercise("Harbour and Vale claims assistant (as deployed)", P.D_deployed(), {
        "send_correspondence": [O("a", "MODEL", "a second model confirms every recipient is legitimate", G("model", "model checks")), O("b", "CAP", "at most 5 attachments per letter", G("deterministic", "max attachments", False)),
                                O("c", "TRAP", "recipients must appear in the claim file (all text on the claim, including the claimant's emails and notes)", G("deterministic", "addresses in the claim file", True, writable_from=("claimant_email", "attachments", "memory"))),
                                O("d", "RECORD", "recipients must be parties named on the policy-system claim record", G("deterministic", "parties named on the claim record", True))],
        "fetch_url": [O("a", "MODEL", "a model checks the URL", G("model", "model checks")), O("b", "RECORD", "proxy allow-list", G("deterministic", "proxy allow-list", True))]})
    return [B, C, D]

def pick_kind(ex: Exercise, kinds: list) -> dict:
    """An answer that, for each dangerous tool, takes the first option whose kind is in kinds (in order of preference)."""
    fixes = {}
    for t in ex.dangerous_tools():
        for k in kinds:
            o = next((o for o in ex.menu[t] if o.kind == k), None)
            if o: fixes[t] = o.id; break
    return fixes

ARCHETYPES = {   # name -> (kind preference, gate memory writes?)
    "reciter (model review everywhere)": (["MODEL", "HUMAN_BLIND", "CAP"], False),
    "cap-fan (limits and rates)": (["CAP", "MODEL", "TRAP"], False),
    "approver (a person looks)": (["HUMAN_EVID", "HUMAN_BLIND", "MODEL"], False),
    "pattern-matcher (lists and records)": (["TRAP", "RECORD"], False),
    "careful": (["RECORD"], True)}
def archetype_answer(ex: Exercise, name: str) -> dict:
    kinds, mem = ARCHETYPES[name]; return dict(fixes=pick_kind(ex, kinds), memory=mem)
