"""Chapter 31: shadow mode and progressive rollout for a security control.

Three pieces.
  ExitRule   - the release criteria, written (and hashed) before the first shadow decision, with exact binomial upper bounds so that 'zero in 40' is not read as 'zero'.
  Shadow     - runs a candidate beside the live control on a copy of the books; the candidate's answer is recorded and never returned, and its failures cannot reach the caller.
  Rollout    - a stage ladder over a stable bucket of vendors, with promote / hold / rollback decided by the exit rule and a kill switch that acts at once.
"""
from __future__ import annotations
import copy, hashlib, json, math, time
from dataclasses import dataclass, field, asdict
from typing import Callable, Optional

# ---------------------------------------------------------------- statistics
def _cdf(n: int, k: int, p: float) -> float:
    return sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(0, k + 1))

def upper_bound(k: int, n: int, conf: float = 0.95) -> float:
    """One-sided exact (Clopper-Pearson) upper bound on a rate after k events in n trials.  n=0 gives 1.0."""
    if n <= 0: return 1.0
    if k >= n: return 1.0
    lo, hi = k / n, 1.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if _cdf(n, k, mid) > 1 - conf: lo = mid
        else: hi = mid
    return hi

def lower_bound(k: int, n: int, conf: float = 0.95) -> float:
    if n <= 0 or k <= 0: return 0.0
    lo, hi = 0.0, k / n
    for _ in range(60):
        mid = (lo + hi) / 2
        if 1 - _cdf(n, k - 1, mid) < 1 - conf: lo = mid
        else: hi = mid
    return lo

def n_to_exclude(rate: float, conf: float = 0.95) -> int:
    """Smallest n such that zero events in n trials puts the upper bound at or under `rate` (the rule of three, exactly)."""
    n = 1
    while upper_bound(0, n, conf) > rate: n += 1
    return n

# ---------------------------------------------------------------- the exit rule
@dataclass(frozen=True)
class ExitRule:
    """Written before the shadow run.  Rates are per benign decision the live control paid (AUTO): how many the candidate would stop.
    max_escapes is per labelled hostile decision, and 0 means 'any escape ends the run'."""
    name: str
    min_decisions: int            # live AUTO decisions observed before a verdict is allowed
    max_extra_hold_rate: float    # upper bound (95%) allowed on the share of live-AUTO benign decisions the candidate would hold
    max_escapes: int = 0          # hostile or canary decisions the candidate pays and live does not
    max_candidate_errors: float = 0.01
    min_weeks: int = 2            # calendar floor: a rule that is satisfied by a quiet Monday is not a rule
    queue_capacity_per_week: Optional[int] = None   # extra holds a person can absorb in a week; None = not checked
    def digest(self) -> str: return hashlib.sha256(json.dumps(asdict(self), sort_keys=True).encode()).hexdigest()[:12]

def judge(rule: ExitRule, *, live_auto: int, extra_holds: int, escapes: int, errors: int, decisions: int, weeks: float, worst_week_holds: int = 0) -> tuple[str, list[str]]:
    """PROMOTE, HOLD (keep shadowing) or REJECT, with the reasons.  An escape or an error rate over the limit rejects; too little evidence holds."""
    why = []
    if escapes > rule.max_escapes: return "REJECT", [f"escapes {escapes} > {rule.max_escapes}"]
    if decisions and errors / decisions > rule.max_candidate_errors: return "REJECT", [f"candidate errors {errors}/{decisions}"]
    ub = upper_bound(extra_holds, live_auto)
    if live_auto < rule.min_decisions: why.append(f"live AUTO {live_auto} < {rule.min_decisions}")
    if weeks < rule.min_weeks: why.append(f"weeks {weeks:.1f} < {rule.min_weeks}")
    if live_auto >= rule.min_decisions and ub > rule.max_extra_hold_rate and lower_bound(extra_holds, live_auto) > rule.max_extra_hold_rate: return "REJECT", [f"extra-hold rate lower bound {lower_bound(extra_holds, live_auto):.3f} > {rule.max_extra_hold_rate}"]
    if ub > rule.max_extra_hold_rate: why.append(f"extra-hold upper bound {ub:.3f} > {rule.max_extra_hold_rate}")
    if rule.queue_capacity_per_week is not None and worst_week_holds > rule.queue_capacity_per_week: why.append(f"worst week {worst_week_holds} extra holds > capacity {rule.queue_capacity_per_week}")
    return ("PROMOTE" if not why else "HOLD"), why

# ---------------------------------------------------------------- shadow
def classify_diff(live: str, cand: str) -> str:
    if live == cand: return "SAME"
    if live == "AUTO": return "TIGHTER"          # candidate would hold or reject what live pays
    if cand == "AUTO": return "LOOSER"           # candidate would pay what live holds
    return "SIDEWAYS"                            # REVIEW <-> REJECT

@dataclass
class ShadowRecord:
    item_id: str; ts: float; live: str; cand: Optional[str]; diff: str; error: Optional[str] = None; label: Optional[str] = None; cand_ms: float = 0.0

class Shadow:
    """pipeline(doc, ex, env, books) -> route.  The candidate gets a deep copy of the books, so nothing it does to them survives; an exception becomes an error record and the live answer is returned unchanged."""
    def __init__(self, live: Callable, candidate: Callable, books_of: Callable = lambda b: b, budget_ms: float = 250.0):
        self.live, self.candidate, self.books_of, self.budget_ms = live, candidate, books_of, budget_ms; self.log: list[ShadowRecord] = []
    def decide(self, item_id: str, doc, ex, env, books, ts: float = 0.0, label: Optional[str] = None) -> str:
        live = self.live(doc, ex, env, books)
        t0 = time.perf_counter(); cand = None; err = None
        try: cand = self.candidate(doc, ex, env, copy.deepcopy(self.books_of(books)))
        except Exception as e: err = type(e).__name__
        ms = (time.perf_counter() - t0) * 1000
        if err is None and ms > self.budget_ms: err = "OVER_BUDGET"; cand = None
        self.log.append(ShadowRecord(item_id, ts, live, cand, classify_diff(live, cand) if cand is not None else "ERROR", err, label, ms))
        return live
    def tally(self) -> dict:
        L = self.log; hostile = lambda r: r.label in ("hostile", "canary")
        return dict(decisions=len(L), live_auto=sum(r.live == "AUTO" and not hostile(r) for r in L), extra_holds=sum(r.diff == "TIGHTER" and not hostile(r) for r in L),
                    escapes=sum(r.diff == "LOOSER" and hostile(r) for r in L), looser_unlabelled=sum(r.diff == "LOOSER" and not hostile(r) for r in L),
                    errors=sum(r.diff == "ERROR" for r in L), hostile_n=sum(hostile(r) for r in L), hostile_caught_extra=sum(hostile(r) and r.live == "AUTO" and r.cand != "AUTO" for r in L))

# ---------------------------------------------------------------- progressive rollout
def bucket(key: str, salt: str, n: int = 100) -> int:
    """Stable bucket of a key.  The same vendor lands in the same bucket for as long as the salt is unchanged, so a stage never flips a vendor back and forth."""
    return int(hashlib.sha256(f"{salt}:{key}".encode()).hexdigest()[:8], 16) % n

LADDER = (0, 5, 25, 50, 100)      # percent of buckets whose decisions are made by the candidate

@dataclass
class Rollout:
    rule: ExitRule; salt: str; stage_idx: int = 0; killed: bool = False; history: list = field(default_factory=list)
    @property
    def percent(self) -> int: return 0 if self.killed else LADDER[self.stage_idx]
    def enforced(self, key: str) -> bool: return bucket(key, self.salt) < self.percent
    def step(self, week: int, verdict: str, why: list) -> str:
        """Apply the exit-rule verdict for the stage just observed.  REJECT drops back to 0, HOLD stays, PROMOTE climbs one rung."""
        old = self.percent
        if verdict == "REJECT": self.stage_idx = 0
        elif verdict == "PROMOTE" and self.stage_idx < len(LADDER) - 1: self.stage_idx += 1
        self.history.append(dict(week=week, verdict=verdict, why=why, from_pct=old, to_pct=self.percent)); return verdict
    def kill(self, week: int, reason: str): self.killed = True; self.history.append(dict(week=week, verdict="KILL", why=[reason], from_pct=LADDER[self.stage_idx], to_pct=0))

def rung_weeks(weekly_live_auto: float, percent: int, min_decisions: int, min_weeks: int = 1) -> float:
    """Weeks a rung must run before the exit rule may speak: enough enforced live-AUTO decisions AND the calendar floor.  A 5 per cent rung of a small tenant is the slow one."""
    per_week = weekly_live_auto * percent / 100
    return float("inf") if per_week <= 0 else max(float(min_weeks), min_decisions / per_week)

def release_decision(shadow_verdict: str, direction: str, canary_escapes: dict) -> tuple[str, list[str]]:
    """The shadow's verdict alone is enough for a tightening, whose failure is a queue and shows up as a cost.  A loosening needs a clean canary replay in every layer as well,
    because its failure is a payment nobody sees: traffic cannot certify an absence.  direction: 'tighten' | 'loosen' | 'both'.  canary_escapes: {layer: escapes}, e.g. {'both': 0, 'verifier': 0}."""
    why = []
    if shadow_verdict != "PROMOTE": return shadow_verdict, ["shadow: " + shadow_verdict]
    if direction in ("loosen", "both"):
        if not canary_escapes: return "HOLD", ["loosening without a canary replay"]
        why = [f"canary escapes in layer {k}: {v}" for k, v in sorted(canary_escapes.items()) if v]
    return ("REJECT" if why else "PROMOTE"), why
