"""Chapter 36: degradation by design.  What Quill does when something it depends on is not answering correctly, decided in advance and testable.
  Dependency   a named thing on the authority path: role (PREVENT = a gate that can stop an effect, DETECT = a monitor that can only notice, PROVIDE = a model or data provider, APPROVE = the people/queue, RECORD = the evidence log, PEER = another agent whose answer feeds this one (Chapter 38)), its failure policy, and who owns it
  guarded()    call a dependency with a hard deadline and a validator; returns a Result whose status is OK, ERROR, TIMEOUT or MALFORMED, never an exception and never a default verdict
  decide()     pure function: (dependency statuses, action class) -> Disposition (ALLOW, HOLD, REFUSE, QUEUE) and the reasons; the table is data, so it can be diffed, signed and tested
  Breaker      opens after k failures in a window, half-opens after a cooldown, closes after n consecutive probe successes (hysteresis, so a flapping dependency does not flap the mode)
  OpenBudget   a detective control may be down for at most `limit` released effects or `minutes` of time; past either the mode tightens (a degraded mode with no end is the normal mode)
  cells()/untested()  the grid of (dependency, fault kind) and which cells a drill has exercised
  scan_handlers()     AST scan for broad exception handlers and what they do (pass, continue, return a literal, re-raise): the places a fault is turned into a verdict by accident
It cannot tell whether a failure is an attack, cannot know a validator is complete, and says nothing about what happens inside a dependency that answers wrongly while looking healthy."""
from __future__ import annotations
import ast, threading, time
from dataclasses import dataclass, field
from enum import Enum

class Role(str, Enum): PREVENT = "PREVENT"; DETECT = "DETECT"; PROVIDE = "PROVIDE"; APPROVE = "APPROVE"; RECORD = "RECORD"; PEER = "PEER"
class Disp(str, Enum): ALLOW = "ALLOW"; HOLD = "HOLD"; REFUSE = "REFUSE"; QUEUE = "QUEUE"
FAULTS = ("ERROR", "TIMEOUT", "MALFORMED", "STALE")
ORDER = {Disp.ALLOW: 0, Disp.QUEUE: 1, Disp.HOLD: 2, Disp.REFUSE: 3}

@dataclass
class Dependency:
    name: str; role: Role; owner: str; open_limit_effects: int = 0; open_limit_minutes: int = 0; fallback: str | None = None

@dataclass
class Result:
    status: str; value: object = None; seconds: float = 0.0; note: str = ""
    @property
    def ok(self) -> bool: return self.status == "OK"

def guarded(fn, *args, deadline: float = 2.0, validate=lambda v: v is not None, **kw) -> Result:
    box: dict = {}
    def run():
        try: box["v"] = fn(*args, **kw)
        except BaseException as e: box["e"] = e
    t0 = time.monotonic(); th = threading.Thread(target=run, daemon=True); th.start(); th.join(deadline); dt = time.monotonic() - t0
    if th.is_alive(): return Result("TIMEOUT", None, dt, f"no answer in {deadline}s")
    if "e" in box: return Result("ERROR", None, dt, type(box["e"]).__name__)
    try: good = bool(validate(box["v"]))
    except Exception: good = False
    return Result("OK" if good else "MALFORMED", box["v"] if good else None, dt, "" if good else "validator rejected the answer")

# action classes, from most to least consequential
MONEY, SEND, DRAFT, READ = "money_out", "send_external", "draft_internal", "read_only"
CLASSES = (MONEY, SEND, DRAFT, READ)

def default_table() -> dict:
    """(role of the failing dependency, action class) -> disposition.  Written as a table so a reviewer can read it in a minute."""
    t = {}
    for r in Role:
        for c in CLASSES: t[(r.value, c)] = Disp.ALLOW
    t.update({(Role.PREVENT.value, MONEY): Disp.HOLD, (Role.PREVENT.value, SEND): Disp.HOLD, (Role.PREVENT.value, DRAFT): Disp.ALLOW, (Role.PREVENT.value, READ): Disp.ALLOW,
              (Role.PROVIDE.value, MONEY): Disp.QUEUE, (Role.PROVIDE.value, SEND): Disp.QUEUE, (Role.PROVIDE.value, DRAFT): Disp.QUEUE, (Role.PROVIDE.value, READ): Disp.ALLOW,
              (Role.APPROVE.value, MONEY): Disp.QUEUE, (Role.APPROVE.value, SEND): Disp.QUEUE,
              (Role.RECORD.value, MONEY): Disp.REFUSE, (Role.RECORD.value, SEND): Disp.REFUSE, (Role.RECORD.value, DRAFT): Disp.HOLD,
              (Role.PEER.value, MONEY): Disp.HOLD, (Role.PEER.value, SEND): Disp.HOLD, (Role.PEER.value, DRAFT): Disp.QUEUE,
              (Role.DETECT.value, MONEY): Disp.ALLOW, (Role.DETECT.value, SEND): Disp.ALLOW})   # detective: allowed, but only inside an OpenBudget
    return t

def decide(deps: dict[str, Dependency], status: dict[str, str], action: str, table: dict | None = None, over_budget: frozenset = frozenset()) -> tuple[Disp, list[str]]:
    table = table or default_table(); worst = Disp.ALLOW; why: list[str] = []
    for name, st in status.items():
        if st == "OK": continue
        d = deps[name]; disp = table[(d.role.value, action)]
        if d.role == Role.DETECT and name in over_budget and action in (MONEY, SEND): disp = Disp.HOLD
        if st == "STALE" and d.role == Role.PREVENT: disp = max(disp, Disp.HOLD, key=ORDER.get)
        if ORDER[disp] > ORDER[worst]: worst = disp
        why.append(f"{name}:{st}:{d.role.value}->{disp.value}")
    return worst, why

@dataclass
class Breaker:
    k: int = 3; window: float = 60.0; cooldown: float = 120.0; need: int = 3
    state: str = "CLOSED"; fails: list = field(default_factory=list); opened: float = 0.0; probes: int = 0
    def allow(self, now: float) -> bool:
        if self.state == "OPEN" and now - self.opened >= self.cooldown: self.state, self.probes = "HALF", 0
        return self.state != "OPEN"
    def record(self, ok: bool, now: float):
        if self.state == "HALF":
            if ok:
                self.probes += 1
                if self.probes >= self.need: self.state, self.fails = "CLOSED", []
            else: self.state, self.opened = "OPEN", now
            return
        if ok: return
        self.fails = [t for t in self.fails if now - t <= self.window] + [now]
        if len(self.fails) >= self.k: self.state, self.opened = "OPEN", now

@dataclass
class OpenBudget:
    effects: int; minutes: float; used: int = 0; since: float | None = None
    def spend(self, now_min: float) -> bool:
        """True if one more effect may be released while the detector is down."""
        if self.since is None: self.since = now_min
        if self.used >= self.effects or now_min - self.since >= self.minutes: return False
        self.used += 1; return True
    def reset(self): self.used, self.since = 0, None

def cells(deps: dict[str, Dependency]) -> list[tuple[str, str]]: return [(n, f) for n in deps for f in FAULTS]
def untested(deps: dict[str, Dependency], drilled: set) -> list[tuple[str, str]]: return [c for c in cells(deps) if c not in drilled]

def scan_handlers(src: str, path: str = "") -> list[dict]:
    """Broad handlers (bare except, Exception, BaseException) and what their body does."""
    out = []
    try: tree = ast.parse(src)
    except SyntaxError: return out
    for n in ast.walk(tree):
        if not isinstance(n, ast.ExceptHandler): continue
        broad = n.type is None or (isinstance(n.type, ast.Name) and n.type.id in ("Exception", "BaseException"))
        if not broad: continue
        body = n.body; kinds = set()
        for s in body:
            if isinstance(s, ast.Pass): kinds.add("pass")
            elif isinstance(s, ast.Continue): kinds.add("continue")
            elif isinstance(s, ast.Raise): kinds.add("raise")
            elif isinstance(s, ast.Return):
                v = s.value; kinds.add("return_literal:" + (ast.unparse(v)[:30] if v is not None else "None"))
            elif isinstance(s, ast.Expr) and isinstance(s.value, ast.Call): kinds.add("call:" + ast.unparse(s.value.func)[:20])
            else: kinds.add(type(s).__name__.lower())
        out.append(dict(path=path, line=n.lineno, kinds=sorted(kinds), swallows=not ("raise" in kinds)))
    return out
