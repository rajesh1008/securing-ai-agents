"""Runtime tool registry: the object an inventory is generated from, and the only door to execution."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Any

@dataclass
class Tool:
    name: str
    effect: str            # "read" | "write" | "egress" | "money"
    irreversible: bool
    fn: Callable[..., Any]
    gated: bool = True     # does the call pass through BulwarkGate before fn runs?
    loadouts: set[str] = field(default_factory=set)

class Registry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}
        self.executed: list[tuple[str, dict]] = []

    def register(self, tool: Tool):
        self._tools[tool.name] = tool

    def inventory(self) -> list[dict]:
        return [dict(name=t.name, effect=t.effect, irreversible=t.irreversible, gated=t.gated,
                     loadouts=sorted(t.loadouts)) for t in self._tools.values()]

    def ungated_privileged(self) -> list[str]:
        return [t.name for t in self._tools.values() if t.effect in ("write", "egress", "money") and not t.gated]

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def call(self, name: str, loadout: str, args: dict, gate_ok: bool | None):
        t = self._tools.get(name)
        if t is None:
            return {"executed": False, "why": "unknown tool"}
        if loadout not in t.loadouts:
            return {"executed": False, "why": f"tool not in loadout {loadout}"}
        if t.gated and gate_ok is not True:
            return {"executed": False, "why": "gate did not allow"}
        self.executed.append((name, args))
        return {"executed": True, "result": t.fn(**args)}
