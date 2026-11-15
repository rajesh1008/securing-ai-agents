"""Chapter 28: the test pyramid for agent security.  Pieces:
  LAYERS            five floors, cheapest first: unit, scenario, deployment, live, production sample
  Deployment        the part of a release that decides what a task can reach: box manifest, tools, egress hosts, model alias, prompt digest, budget
  widening          compare an approved Deployment with the one about to ship; every change that gives a task more reach is a WIDEN, a waiver is a sentence with a name in it
  binom_sf / plan_live_test / live_verdict
                    exact binomial arithmetic for the live floor: how many runs, and what count of failures, give a stated false-alarm rate under the old behaviour and a
                    stated chance of catching a stated regression
  Pyramid           run the floors in order, stop at the first failing floor, and record what each floor cost
  Corpus            every confirmed bypass or incident becomes a permanent case with the floor that should catch it and the floor that did
  Monitor           the production floor: probes that must be refused, probes that must succeed, and a denial-rate check against the rate the live floor measured
Nothing here asks a model anything.  The floors are only as good as the cases put on them; this module decides when they run, in what order, and what a result means."""
from __future__ import annotations
import json, math, time
from collections import deque
from dataclasses import dataclass, field, asdict
from typing import Callable

LAYERS = ("unit", "scenario", "deployment", "live", "production")

@dataclass
class Deployment:
    mounts: dict = field(default_factory=dict)        # host path -> box path ("ro:" prefix for read-only is part of the value)
    env_names: list = field(default_factory=list)     # names only; values never appear in a baseline
    network: str = "none"                             # none | broker:<name> | open
    tools: list = field(default_factory=list)
    egress_hosts: list = field(default_factory=list)
    model_alias: str = ""
    prompt_digest: str = ""
    budget: dict = field(default_factory=dict)        # max_calls, max_egress, max_repeat, max_tokens
    rung: str = "R3"
    def to_json(self) -> str: return json.dumps(asdict(self), sort_keys=True)
    @staticmethod
    def from_manifest(man, **kw) -> "Deployment":
        return Deployment(mounts=dict(man.inputs), env_names=sorted(man.env), network=man.network, **kw)

RUNG_ORDER = {"R0": 0, "R1": 1, "R2": 2, "R3": 3}
def widening(base: Deployment, now: Deployment) -> list[tuple[str, str]]:
    """Changes that give a task more reach than the approved baseline.  Returns (kind, detail).  Narrowing is not reported; model and prompt changes are CHANGE, because their effect is a live-floor question."""
    out = []
    for host, box in now.mounts.items():
        if host not in base.mounts: out.append(("WIDEN", f"mount added: {host} -> {box}"))
        elif base.mounts[host] != box:
            if base.mounts[host].startswith("ro:") and not box.startswith("ro:"): out.append(("WIDEN", f"mount made writable: {host}"))
            else: out.append(("CHANGE", f"mount moved: {host}"))
    for n in sorted(set(now.env_names) - set(base.env_names)): out.append(("WIDEN", f"environment variable added: {n}"))
    order = {"none": 0}
    def net(v): return 0 if v == "none" else (1 if v.startswith("broker:") else 2)
    if net(now.network) > net(base.network): out.append(("WIDEN", f"network {base.network} -> {now.network}"))
    elif now.network != base.network: out.append(("CHANGE", f"network {base.network} -> {now.network}"))
    for t in sorted(set(now.tools) - set(base.tools)): out.append(("WIDEN", f"tool added: {t}"))
    for h in sorted(set(now.egress_hosts) - set(base.egress_hosts)): out.append(("WIDEN", f"egress host added: {h}"))
    for k, v in now.budget.items():
        if k in base.budget and v > base.budget[k]: out.append(("WIDEN", f"budget {k} {base.budget[k]} -> {v}"))
        if k not in base.budget: out.append(("WIDEN", f"budget {k} added without a baseline"))
    for k in base.budget:
        if k not in now.budget: out.append(("WIDEN", f"budget {k} removed"))
    if RUNG_ORDER.get(now.rung, -1) < RUNG_ORDER.get(base.rung, -1): out.append(("WIDEN", f"isolation rung {base.rung} -> {now.rung}"))
    if now.model_alias != base.model_alias: out.append(("CHANGE", f"model alias {base.model_alias} -> {now.model_alias}"))
    if now.prompt_digest != base.prompt_digest: out.append(("CHANGE", "prompt digest changed"))
    return out

def check_deployment(base: Deployment, now: Deployment, waivers: dict[str, str] | None = None) -> tuple[bool, list[str]]:
    """The configuration test.  Passes when nothing WIDENs, or when each WIDEN has a waiver whose text names a person.  CHANGE items are returned for the live floor."""
    waivers = waivers or {}; problems = []; notes = []
    for kind, detail in widening(base, now):
        if kind == "CHANGE": notes.append("live-floor: " + detail); continue
        w = waivers.get(detail, "").strip()
        if len(w.split()) < 4 or not any(ch.isupper() for ch in w): problems.append(detail)
    return (not problems), problems + notes

def binom_pmf(n: int, k: int, p: float) -> float: return math.comb(n, k) * p ** k * (1 - p) ** (n - k)
def binom_sf(n: int, k: int, p: float) -> float:
    """P(X >= k) for X ~ Binomial(n, p)."""
    if k <= 0: return 1.0
    return sum(binom_pmf(n, i, p) for i in range(k, n + 1))
def plan_live_test(p0: float, p1: float, alpha: float = 0.05, power: float = 0.8, n_max: int = 2000) -> tuple[int, int] | None:
    """Smallest (n, k) such that a run of n live trials alarms when failures >= k, with P(alarm | rate p0) <= alpha and P(alarm | rate p1) >= power.  None if n_max is not enough."""
    for n in range(1, n_max + 1):
        k = next((k for k in range(0, n + 2) if binom_sf(n, k, p0) <= alpha), None)
        if k is not None and k <= n and binom_sf(n, k, p1) >= power: return n, k
    return None
def live_verdict(n: int, failures: int, p0: float, alpha: float = 0.05) -> str:
    """BLOCK when the failures are unlikely (< alpha) under the old rate; REVIEW when they are unlikely at 5 x alpha; else PASS.  A PASS is the absence of evidence at this sample size."""
    p = binom_sf(n, failures, p0)
    return "BLOCK" if p <= alpha else ("REVIEW" if p <= 5 * alpha else "PASS")

@dataclass
class Floor:
    name: str; run: Callable[[], tuple[bool, str]]; cost_usd: float = 0.0
class Pyramid:
    def __init__(self, floors: list[Floor]): self.floors = floors
    def run(self) -> list[dict]:
        rec = []
        for f in self.floors:
            t = time.time(); ok, why = f.run(); rec.append(dict(floor=f.name, ok=ok, why=why, secs=round(time.time() - t, 3), cost_usd=f.cost_usd))
            if not ok: break
        return rec
    @staticmethod
    def skipped(rec: list[dict], floors: list[Floor]) -> list[str]: return [f.name for f in floors[len(rec):]]

@dataclass
class Case:
    id: str; source: str; attack_class: str; should_catch: str; caught_by: list = field(default_factory=list); added: str = ""
class Corpus:
    def __init__(self): self.cases: dict[str, Case] = {}
    def add(self, c: Case):
        if c.id in self.cases: raise ValueError(f"{c.id} exists; cases are append-only")
        if c.should_catch not in LAYERS: raise ValueError(f"unknown floor {c.should_catch}")
        self.cases[c.id] = c
    def record(self, cid: str, floor: str):
        if floor not in LAYERS: raise ValueError(floor)
        if floor not in self.cases[cid].caught_by: self.cases[cid].caught_by.append(floor)
    def gaps(self) -> list[str]:
        """Cases whose intended floor never caught them: either the case is on the wrong floor or the floor is missing a check."""
        return [c.id for c in self.cases.values() if c.should_catch not in c.caught_by]
    def lowest_catch(self, cid: str) -> str | None:
        got = [l for l in LAYERS if l in self.cases[cid].caught_by]; return got[0] if got else None

class Monitor:
    """Production floor.  Probes are synthetic requests with a known right answer that run on the live path on a schedule.  A `must_refuse` probe that is allowed, or a `must_allow`
    probe that is refused, alerts at once.  Real traffic is watched through its denial rate against the rate the live floor measured."""
    def __init__(self, base_denial_rate: float, window: int = 200, alpha: float = 0.001):
        self.p0, self.window, self.alpha = base_denial_rate, window, alpha; self._c = None; self.recent: deque = deque(maxlen=window); self._sum = 0; self.alerts: list[tuple[int, str]] = []; self.t = 0
    def probe(self, kind: str, allowed: bool):
        self.t += 1
        if kind == "must_refuse" and allowed: self.alerts.append((self.t, "probe: hostile request was allowed"))
        if kind == "must_allow" and not allowed: self.alerts.append((self.t, "probe: legitimate request was refused"))
    def _crit(self):
        """Counts that alarm: high = smallest d with P(X >= d | p0) <= alpha; low = largest d with P(X <= d | p0) <= alpha (None when p0 is 0)."""
        if self._c is None:
            hi = next((d for d in range(self.window + 2) if binom_sf(self.window, d, self.p0) <= self.alpha), self.window + 1)
            lo = None
            if self.p0 > 0:
                lo = next((d for d in range(self.window, -1, -1) if binom_sf(self.window, self.window - d, 1 - self.p0) <= self.alpha), None)
            self._c = (hi, lo)
        return self._c
    def traffic(self, denied: bool):
        self.t += 1; x = 1 if denied else 0
        if len(self.recent) == self.window: self._sum -= self.recent[0]
        self.recent.append(x); self._sum += x
        if len(self.recent) == self.window:
            d = self._sum; hi, lo = self._crit()
            if d >= hi: self.alerts.append((self.t, f"denial rate up: {d}/{self.window} vs {self.p0}"))
            elif lo is not None and d <= lo: self.alerts.append((self.t, f"denial rate down: {d}/{self.window} vs {self.p0}"))
    def first_alert(self) -> int | None: return self.alerts[0][0] if self.alerts else None
