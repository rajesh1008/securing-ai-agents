"""Chapter 29: the bookkeeping of a red-team exercise.  Rules of engagement as data, a finding record with a severity rubric that does not need an argument,
the arithmetic of what a clean campaign result means, a review-queue flood model, and a tenant-from-credential webhook check.  No model calls."""
from __future__ import annotations
import math, random, hashlib, hmac, json
from dataclasses import dataclass, field, asdict
from typing import Optional

# ---------------------------------------------------------------- rules of engagement
@dataclass
class Engagement:
    name: str
    in_scope: list            # systems and entry points the team may attack
    out_of_scope: list        # named, with the reason
    knowledge: str            # outsider | grey | insider
    budget_rounds: int        # attempts per campaign
    budget_campaigns: int
    stop_conditions: list     # the things that end the exercise early (real money moved, real customer data seen, ...)
    data: str                 # which data the team may touch: synthetic | copy | live
    def problems(self) -> list:
        p = []
        if not self.in_scope: p.append("no scope")
        if not self.out_of_scope: p.append("no exclusions named: nothing is out of scope only by accident")
        if self.knowledge not in ("outsider", "grey", "insider"): p.append("knowledge level not one of the three")
        if self.budget_rounds < 1 or self.budget_campaigns < 1: p.append("no budget")
        if not self.stop_conditions: p.append("no stop condition")
        if self.data == "live" and not any("customer" in s or "money" in s for s in self.stop_conditions): p.append("live data without a customer-data or money stop condition")
        if self.data not in ("synthetic", "copy", "live"): p.append("data class not named")
        return p

# ---------------------------------------------------------------- findings and severity
IMPACT = {0: "no effect on an asset", 1: "early, unrequested or delayed action, correct effect", 2: "wrong amount, or data of one party shown to another", 3: "money or data to the attacker, or across a tenant boundary"}
REACH = {0: "needs insider knowledge or access", 1: "needs a grey-box view (reason codes, error text)", 2: "an outsider with one channel and a few attempts", 3: "an outsider with one attempt"}
DETECT = {0: "alerts a person within a day", 1: "logged, found only by a query", 2: "silent: no record names it"}
@dataclass
class Finding:
    id: str; title: str; entry: str; asset: str; impact: int; reach: int; detect: int
    evidence: str = ""; fix: str = ""; retest: Optional[str] = None; owner: str = ""
    def score(self) -> int:
        """impact x (reach + 1) + 2 for a silent finding.  Impact 0 scores 0 whatever else is true: a hole that reaches nothing is a note."""
        return 0 if self.impact == 0 else self.impact * (self.reach + 1) + (2 if self.detect == 2 else 0)
    def severity(self) -> str:
        s = self.score()
        if self.impact == 3 and self.reach >= 1: s = max(s, 9)      # money or data to the attacker reachable by anyone with a channel is never below high
        return "note" if s == 0 else "low" if s <= 4 else "medium" if s <= 8 else "high" if s <= 12 else "critical"
    def closed(self) -> bool: return bool(self.fix) and self.retest in ("pass",)

def triage(findings: list) -> list:
    order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "note": 4}
    return sorted(findings, key=lambda f: (order[f.severity()], -f.reach, f.id))

# ---------------------------------------------------------------- what a clean result means
def upper_bound(n: int, k: int = 0, conf: float = 0.95) -> float:
    """Exact (Clopper-Pearson) one-sided upper bound on a rate after k successes in n trials."""
    if k >= n: return 1.0
    lo, hi = k / n, 1.0
    def cdf(p):   # P(X <= k | n, p)
        return sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k + 1))
    for _ in range(60):
        mid = (lo + hi) / 2
        if cdf(mid) > 1 - conf: lo = mid
        else: hi = mid
    return hi
def campaigns_needed(p: float, conf: float = 0.95) -> int:
    """Independent campaigns with zero wins needed before 'the per-campaign win rate is at most p' holds at confidence conf."""
    return math.ceil(math.log(1 - conf) / math.log(1 - p))
def discovery_curve(first_rounds: list, n_campaigns: int, budget: int) -> list:
    """Share of campaigns that had won by round r (r = 1..budget).  first_rounds holds the round of first win for the campaigns that won."""
    return [sum(1 for x in first_rounds if x <= r) / n_campaigns for r in range(1, budget + 1)]

# ---------------------------------------------------------------- the queue an attacker can fill
def queue_wait(legit_per_day: float, flood_per_day: float, reviews_per_day: float, days: int = 30, seed: int = 29, policy: str = "fifo") -> dict:
    """Daily batches: arrivals are Poisson (legit and hostile), the reviewer clears at most reviews_per_day items a day, in arrival order (fifo) or legit-first-by-source-quota (quota: an ORACLE policy that knows which items are hostile; hostile items beyond
    a fifth of the day's capacity wait behind everything else; real quotas can only key on a sender or claim, which an attacker can rotate).  Reports the median and 90th percentile of the days a legitimate item waits, and the backlog at the end."""
    r = random.Random(seed); q = []; waits = []
    def poisson(lam):
        L, k, p = math.exp(-lam), 0, 1.0
        while True:
            p *= r.random()
            if p <= L: return k
            k += 1
    for d in range(days):
        new = [("L", d)] * poisson(legit_per_day) + [("H", d)] * poisson(flood_per_day); r.shuffle(new); q += new
        cap = int(reviews_per_day)
        if policy == "fifo": served, q = q[:cap], q[cap:]
        else:
            hcap = max(1, cap // 5); served = []; rest = []; h = 0
            for it in q:
                if len(served) >= cap: rest.append(it); continue
                if it[0] == "H" and h >= hcap: rest.append(it); continue
                served.append(it); h += it[0] == "H"
            q = rest
        waits += [d - a for t, a in served if t == "L"]
    leg_left = sum(1 for t, a in q if t == "L"); waits.sort()
    med = waits[len(waits) // 2] if waits else None; p90 = waits[int(len(waits) * 0.9)] if waits else None
    return dict(median_wait_days=med, p90_wait_days=p90, legit_served=len(waits), legit_unserved=leg_left, backlog=len(q))

# ---------------------------------------------------------------- tenant taken from the body or from the credential
SECRETS = {"tenant_a": b"secret-a", "tenant_b": b"secret-b"}
def sign(tenant: str, body: bytes) -> str: return hmac.new(SECRETS[tenant], body, hashlib.sha256).hexdigest()
def tenant_from_body(body: dict, sig: str, books: dict, who_signed: str) -> Optional[str]:
    """The tempting handler: verifies that SOME tenant signed it, then believes the tenant named inside."""
    raw = json.dumps(body, sort_keys=True).encode()
    if not hmac.compare_digest(sig, sign(who_signed, raw)): return None
    return books[body["tenant"]].get(body["invoice"])
def tenant_from_credential(body: dict, sig: str, books: dict, who_signed: str) -> Optional[str]:
    """The tenant is whoever's key verified; a body that names another tenant is refused."""
    raw = json.dumps(body, sort_keys=True).encode()
    if not hmac.compare_digest(sig, sign(who_signed, raw)): return None
    if body.get("tenant", who_signed) != who_signed: return "REFUSED:tenant mismatch"
    return books[who_signed].get(body["invoice"])

# ---------------------------------------------------------------- the fix the campaign suggested: where a document came from
def provenance_route(route: str, sender: str, registered_senders: set) -> str:
    """A document the verifier would pay (AUTO) still goes to a person unless it arrived from a sender registered for that vendor.  It never lowers REVIEW or REJECT."""
    return route if route != "AUTO" or sender in registered_senders else "REVIEW"
