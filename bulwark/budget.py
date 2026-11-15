"""Per-task budget: a counter the model cannot talk to. Slots into AuthorityPath as one more question."""
from __future__ import annotations
from collections import Counter
from dataclasses import dataclass, field
import json, time

@dataclass
class Budget:
    max_calls: int = 12            # all tool calls in one task
    max_egress: int = 3            # calls to tools with effect egress or money
    max_repeat: int = 3            # identical (tool, args) calls
    max_tokens: int = 20000        # model tokens charged to the task
    calls: int = 0
    egress: int = 0
    tokens: int = 0
    seen: Counter = field(default_factory=Counter)
    tripped: str | None = None

    def charge_tokens(self, n: int):
        self.tokens += n

    def check(self, tool: str, effect: str, args: dict) -> tuple[bool, str]:
        key = tool + json.dumps(args, sort_keys=True, default=str)
        if self.tripped:
            return False, f"budget already tripped: {self.tripped}"
        if self.calls >= self.max_calls: self.tripped = "max_calls"
        elif effect in ("egress", "money") and self.egress >= self.max_egress: self.tripped = "max_egress"
        elif self.seen[key] >= self.max_repeat: self.tripped = "max_repeat"
        elif self.tokens >= self.max_tokens: self.tripped = "max_tokens"
        if self.tripped:
            return False, f"budget exceeded: {self.tripped}"
        self.calls += 1; self.seen[key] += 1
        if effect in ("egress", "money"): self.egress += 1
        return True, "ok"
