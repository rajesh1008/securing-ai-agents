"""Chapter 32: detection of attacks that passed the controls.  Pure functions and small classes over a stream of observations (no model calls, no labels).
Obs      one decision as the evidence log of Chapter 14 records it, plus what the books and registry said at that moment.
Detectors  each returns an Alert (or None) per observation, online, using only what was known when the observation arrived:
  AmountDetector      robust z-score (median/MAD) of the amount against the vendor's own history; fixed-amount vendors alarm on any change; `frozen` keeps the baseline from absorbing flagged items.
  AccountDetector     the destination account of a payment differs from the one this vendor was last paid to; a confirmed change is a lower score, not a pass.
  ReverseShadow       the retired control keeps deciding silently; an alert is a LOOSER disagreement of a kind never seen on benign traffic (parser conflict vs parser abstention).
  Cusum               one-sided CUSUM on a 0/1 stream (disagreement, hold or AUTO share) against a baseline rate taken from a calibration window.
Budget   ranks alerts, keeps the top `cap` per week; the rest are logged and not shown.   score() measures recall, precision, time to alert and money paid before alert."""
from __future__ import annotations
from dataclasses import dataclass, field
from statistics import median
from typing import Optional
import math

@dataclass
class Obs:
    id: str; day: int; vendor: str; amount: int; dest: str; route: str; reasons: tuple = (); old_route: Optional[str] = None; conflict: Optional[str] = None
    change_confirmed: Optional[bool] = None   # set only on the first observation after a registry change
    paid_day: Optional[int] = None

@dataclass
class Alert:
    id: str; day: int; detector: str; score: float; why: str

def mad(xs):
    m = median(xs); return median([abs(x - m) for x in xs])

class AmountDetector:
    """A vendor's history is the amounts of its earlier observations that were NOT alerted when `frozen`, otherwise all of them.  Needs `min_hist` points; below that it says nothing (and says so in its counters).
    Variable vendors: robust z = |x - median| / (1.4826*MAD, floored at 5% of the median).  Fixed vendors (every earlier amount identical): any change alarms with score 9."""
    name = "amount"
    def __init__(self, z: float = 4.0, min_hist: int = 4, frozen: bool = True, anchor: Optional[int] = None):
        self.z, self.min_hist, self.frozen, self.anchor = z, min_hist, frozen, anchor; self.hist: dict[str, list[int]] = {}; self.silent = 0
    def see(self, o: Obs) -> Optional[Alert]:
        h = self.hist.setdefault(o.vendor, []); a = None
        if len(h) < self.min_hist: self.silent += 1
        elif len(set(h)) == 1:
            if o.amount != h[0]: a = Alert(o.id, o.day, self.name, 9.0, f"fixed-amount vendor changed {h[0]} -> {o.amount}")
        else:
            m = median(h); s = max(1.4826 * mad(h), 0.05 * m); zz = abs(o.amount - m) / s
            if zz >= self.z: a = Alert(o.id, o.day, self.name, min(zz, 9.0), f"amount {o.amount} is {zz:.1f} robust sd from median {int(m)}")
        if (a is None or not self.frozen) and (self.anchor is None or len(h) < self.anchor): h.append(o.amount)   # anchor: the baseline stops learning after the first N points
        return a if o.route == "AUTO" else None   # a held item already has a person; it still teaches the baseline

class AccountDetector:
    """Alerts on an AUTO payment to a destination account this vendor has been paid fewer than `season` times, when the vendor had an earlier account.  A change that carried a confirmation scores 5, one without 8.
    Held items do not count as payments; they only carry the confirmation flag forward."""
    name = "account"
    def __init__(self, season: int = 3): self.season = season; self.paid: dict[tuple, int] = {}; self.conf: dict[tuple, bool] = {}; self.vendor_accts: dict[str, set] = {}
    def see(self, o: Obs) -> Optional[Alert]:
        key = (o.vendor, o.dest)
        if o.change_confirmed is not None: self.conf[key] = o.change_confirmed
        if o.route != "AUTO": return None
        earlier = self.vendor_accts.setdefault(o.vendor, set()); n = self.paid.get(key, 0); self.paid[key] = n + 1; first = not earlier
        earlier.add(o.dest)
        if first or n >= self.season or len(earlier) < 2: return None
        confirmed = self.conf.get(key, False)
        return Alert(o.id, o.day, self.name, 5.0 if confirmed else 8.0, f"payment {n+1} to a new account" + (" (change confirmed)" if confirmed else " (no confirmation on record)"))

class RunDetector:
    """k consecutive rises in a vendor's amounts (each at least `step` above the one before) on AUTO items.  A ratchet of invoices each a little above the last stays inside a variable vendor's spread; the sequence is what is unusual."""
    name = "run"
    def __init__(self, k: int = 5, step: float = 0.03): self.k, self.step = k, step; self.last: dict[str, int] = {}; self.run: dict[str, int] = {}
    def see(self, o: Obs) -> Optional[Alert]:
        if o.route != "AUTO": return None
        p = self.last.get(o.vendor); self.last[o.vendor] = o.amount
        if p is None: return None
        self.run[o.vendor] = self.run.get(o.vendor, 0) + 1 if o.amount >= p * (1 + self.step) else 0
        return Alert(o.id, o.day, self.name, 6.0, f"{self.run[o.vendor]} consecutive rises") if self.run[o.vendor] >= self.k else None

class ReverseShadow:
    """Alerts when the old route is stricter than the one that shipped AND the disagreement has a kind in `alarm_kinds`.  Disagreements of other kinds are counted, not alerted."""
    name = "reverse_shadow"
    def __init__(self, alarm_kinds=("PARSER_CONFLICT",)): self.kinds = set(alarm_kinds); self.counts: dict[str, int] = {}
    def see(self, o: Obs) -> Optional[Alert]:
        if o.old_route is None or o.route != "AUTO" or o.old_route == "AUTO": return None
        k = o.conflict or "OTHER"; self.counts[k] = self.counts.get(k, 0) + 1
        return Alert(o.id, o.day, self.name, 8.5, f"retired control would have held ({k})") if k in self.kinds else None

@dataclass
class Cusum:
    """One-sided CUSUM for a rate increase from p0 to p1 on a 0/1 stream.  S_t = max(0, S_{t-1} + llr(x_t)); alarm when S_t >= h.  llr = x*ln(p1/p0) + (1-x)*ln((1-p1)/(1-p0))."""
    p0: float; p1: float; h: float = 4.0; s: float = 0.0; name: str = "cusum"; fired_at: Optional[int] = None; n: int = 0
    def see(self, x: int, day: int = 0) -> bool:
        self.n += 1; llr = x * math.log(self.p1 / self.p0) + (1 - x) * math.log((1 - self.p1) / (1 - self.p0))
        self.s = max(0.0, self.s + llr)
        if self.s >= self.h and self.fired_at is None: self.fired_at = day; return True
        return False
    def reset(self): self.s = 0.0; self.fired_at = None

def arl0(p0: float, p1: float, h: float, runs: int = 2000, seed: int = 1, cap: int = 5000) -> float:
    """Simulated average run length to a false alarm when the rate really is p0 (a measurement of the chosen h, not a formula)."""
    import random; r = random.Random(seed); tot = 0
    for _ in range(runs):
        c = Cusum(p0, p1, h); n = 0
        while n < cap:
            n += 1
            if c.see(1 if r.random() < p0 else 0): break
        tot += n
    return tot / runs

class Budget:
    """Keep the `cap` highest-scored alerts of each week (week = day // 7); the others are `shed`.  Ties break by earlier day."""
    def __init__(self, cap: int): self.cap = cap
    def apply(self, alerts: list[Alert]):
        by: dict[int, list[Alert]] = {}
        for a in alerts: by.setdefault(a.day // 7, []).append(a)
        kept, shed = [], []
        for w in sorted(by):
            xs = sorted(by[w], key=lambda a: (-a.score, a.day)); kept += xs[:self.cap]; shed += xs[self.cap:]
        return sorted(kept, key=lambda a: a.day), shed

def merge(alerts: list[Alert]) -> list[Alert]:
    """One alert per observation id: the highest score wins, the detectors that agreed are listed."""
    best: dict[str, Alert] = {}; who: dict[str, list[str]] = {}
    for a in alerts:
        who.setdefault(a.id, []).append(a.detector)
        if a.id not in best or a.score > best[a.id].score: best[a.id] = a
    return [Alert(a.id, a.day, "+".join(sorted(set(who[a.id]))), a.score, a.why) for a in best.values()]

def next_friday(d: int) -> int: return d + ((4 - d) % 7)

def score(alerts: list[Alert], truth: dict[str, int], obs: dict[str, Obs], lag_days: int = 0, reach=None) -> dict:
    """truth: id -> loss in cents if the payment goes out (0 for control escapes with no loss).  An alert on day d reaches a person on d + lag_days; it is *in time* when that is before the payment day.
    Returns recall, precision, in-time recall, money paid before the person knew, and the alert count that were false."""
    got = {a.id: a for a in alerts}; tp = [i for i in truth if i in got]
    rc = reach or (lambda a: a.day + lag_days)
    def reach(i): return rc(got[i])
    intime = [i for i in tp if obs[i].paid_day is None or reach(i) < obs[i].paid_day]
    paid_before = sum(truth[i] for i in truth if i not in intime and obs[i].paid_day is not None)
    fp = [a for a in alerts if a.id not in truth]
    return dict(n_truth=len(truth), caught=len(tp), recall=len(tp) / len(truth) if truth else 1.0, in_time=len(intime), in_time_recall=len(intime) / len(truth) if truth else 1.0,
                alerts=len(alerts), false_alerts=len(fp), precision=len(tp) / len(alerts) if alerts else 1.0, loss_paid_before_alert=paid_before,
                median_days_to_alert=(median([got[i].day - obs[i].day for i in tp]) if tp else None))

# ---------------------------------------------------------------- configuration and the online monitor
import hashlib, json
from dataclasses import asdict

@dataclass(frozen=True)
class DetectConfig:
    """Every threshold in one frozen record with a digest, so that a changed threshold is a visible event (as ExitRule is in Chapter 31)."""
    amount_z: float = 4.0; amount_min_hist: int = 4; amount_frozen: bool = True; amount_anchor: Optional[int] = None
    account_season: int = 3; run_k: int = 5; run_step: float = 0.03; reverse_kinds: tuple = ("PARSER_CONFLICT",); weekly_cap: int = 6
    def digest(self) -> str: return hashlib.sha256(json.dumps(asdict(self), sort_keys=True).encode()).hexdigest()[:12]

class Monitor:
    """Runs the four detectors online, one observation at a time.  `see` returns the merged alert for that observation (or None) and appends to `log`; `weekly_view` applies the budget and returns (shown, shed) so the shed list is kept, with the cap and config digest that shed it."""
    def __init__(self, cfg: DetectConfig = DetectConfig()):
        self.cfg = cfg; self.amount = AmountDetector(cfg.amount_z, cfg.amount_min_hist, cfg.amount_frozen, cfg.amount_anchor); self.account = AccountDetector(cfg.account_season)
        self.reverse = ReverseShadow(cfg.reverse_kinds); self.run = RunDetector(cfg.run_k, cfg.run_step); self.log: list[Alert] = []
    def see(self, o: Obs) -> Optional[Alert]:
        got = [a for d in (self.amount, self.account, self.reverse, self.run) if (a := d.see(o))]
        if not got: return None
        a = merge(got)[0]; self.log.append(a); return a
    def weekly_view(self):
        shown, shed = Budget(self.cfg.weekly_cap).apply(self.log)
        return shown, [dict(id=a.id, day=a.day, score=a.score, detector=a.detector, shed_by_cap=self.cfg.weekly_cap, config=self.cfg.digest()) for a in shed]
