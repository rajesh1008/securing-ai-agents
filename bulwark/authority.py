"""Minimal authority path: principal -> identity -> loadout -> gate -> registry -> egress -> evidence (hash-chained)."""
from __future__ import annotations
import hashlib, json, time
from pathlib import Path
from .models import ActionProposal, ActionKind, Principal, AgentIdentity
from .policy_v02 import BulwarkGateV02
from .registry import Registry

TOOL_FOR_KIND = {ActionKind.DRAFT_INVOICE: "draft_invoice", ActionKind.SEND_INVOICE: "send_invoice",
                 ActionKind.SEND_EMAIL: "send_email", ActionKind.INITIATE_PAYMENT: "initiate_payment",
                 ActionKind.READ_DOCUMENT: "read_document", ActionKind.QUERY_BOOKS: "query_books"}

class EvidenceChain:
    """Append-only JSONL; each record carries the hash of the previous one."""
    def __init__(self, path: Path):
        self.path = Path(path); self.path.write_text("")
        self.prev = "0" * 16
    def append(self, rec: dict) -> dict:
        rec = dict(rec, seq=sum(1 for _ in open(self.path)), prev=self.prev)
        body = json.dumps(rec, sort_keys=True)
        rec["hash"] = hashlib.sha256(body.encode()).hexdigest()[:16]
        with open(self.path, "a") as f: f.write(json.dumps(rec, sort_keys=True) + "\n")
        self.prev = rec["hash"]
        return rec
    @staticmethod
    def verify(path: Path) -> tuple[bool, int | None]:
        prev = "0" * 16
        for i, line in enumerate(open(path)):
            rec = json.loads(line); h = rec.pop("hash")
            if rec["prev"] != prev or hashlib.sha256(json.dumps(rec, sort_keys=True).encode()).hexdigest()[:16] != h:
                return False, i
            prev = h
        return True, None

class AuthorityPath:
    def __init__(self, registry: Registry, chain: EvidenceChain, principal: Principal, agent: AgentIdentity, loadout: str):
        self.reg, self.chain, self.principal, self.agent, self.loadout = registry, chain, principal, agent, loadout
        self.gate = BulwarkGateV02()

    def attempt(self, tool: str, proposal: ActionProposal | None = None, args: dict | None = None) -> dict:
        t = self.reg.get(tool)
        rec = dict(principal=self.principal.principal_id, agent=self.agent.agent_id, workload=self.agent.workload_id,
                   loadout=self.loadout, tool=tool, policy=self.gate.policy_version)
        if t is None:
            out = dict(allow=False, executed=False, reason="unknown tool")
        elif self.loadout not in t.loadouts:
            out = dict(allow=False, executed=False, reason=f"tool not in loadout {self.loadout}")
        elif t.gated:
            if proposal is None:
                out = dict(allow=False, executed=False, reason="gated tool requires typed proposal")
            else:
                d = self.gate.check(proposal, self.principal, self.agent)
                if d.allow:
                    r = self.reg.call(tool, self.loadout, args or {}, gate_ok=True)
                    out = dict(allow=True, executed=r["executed"], reason="ok")
                else:
                    out = dict(allow=False, executed=False, reason="; ".join(d.reasons)[:120])
        else:
            r = self.reg.call(tool, self.loadout, args or {}, gate_ok=None)
            out = dict(allow=True, executed=r["executed"], reason="tool is not gated")
        rec.update(out)
        self.chain.append(rec)
        return out
