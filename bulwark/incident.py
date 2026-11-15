"""Chapter 33: incident response for an agent product.  Pure functions over the Chapter 32 observation stream; no model calls.
Action      a containment step: which not-yet-paid items does it stop, and for how long.  Ordered by reversibility.
contain()   replay one Action from a trigger observation at `lag` days after the alert; returns prevented / gone / remaining attack money and collateral holds.
scope()     the questions of step 3 (same vendor, same account, same conflict kind, vendors whose destination changed) as sets of ids.
Case        a frozen case file: the rows it was built from, a digest over them, a decision list; cannot be closed with an unknown deadline or an unowned decision."""
from __future__ import annotations
import hashlib, json
from dataclasses import dataclass, field
from typing import Callable, Optional

REVERSIBILITY = {"hold_item": 1, "hold_vendor": 1, "freeze_account": 2, "hold_changed": 2, "rollback_control": 3, "pause_auto": 3}   # 1 one click, 2 needs a person to lift, 3 changes the product for everyone

def scope(trigger, obs: list, window: int = 30) -> dict:
    """Candidate sets for the alert's item.  Keys name the question; values are sets of observation ids at or after day - window."""
    lo = trigger.day - window; xs = [o for o in obs if o.day >= lo]
    changed = {}
    for o in obs:
        if o.day <= trigger.day: changed.setdefault(o.vendor, []).append((o.day, o.dest))
    recent = {v for v, h in changed.items() if len({d for day, d in h if day >= lo}) > 1 or (h and h[0][1] != h[-1][1] and h[-1][0] >= lo)}
    return {"same_item": {trigger.id},
            "same_vendor": {o.id for o in xs if o.vendor == trigger.vendor},
            "same_account": {o.id for o in xs if o.dest == trigger.dest},
            "same_conflict": {o.id for o in xs if trigger.conflict and o.conflict == trigger.conflict},
            "changed_vendors": {o.id for o in xs if o.vendor in recent},
            "all_auto": {o.id for o in xs if o.route == "AUTO"}}

def _stops(action: str, trigger, o, eff: int) -> bool:
    if o.route != "AUTO": return False
    if action == "hold_item": return o.id == trigger.id
    if action == "hold_vendor": return o.vendor == trigger.vendor
    if action == "freeze_account": return o.dest == trigger.dest
    if action == "rollback_control": return o.old_route is not None and o.old_route != "AUTO"
    if action == "pause_auto": return True
    raise ValueError(action)

def contain(obs: list, truth: dict, trigger, action: str, lag: int, hold_days: int = 14, changed_vendors: Optional[set] = None) -> dict:
    """An action takes effect on day eff = trigger.day + lag and stops every AUTO item it covers whose payment day is after eff and (except rollback) before eff + hold_days.
    Items paid on or before eff are `gone`.  Collateral = stopped items that were not attacks; each is delayed, not lost."""
    eff = trigger.day + lag; prevented = gone = remain = 0; col = col_n = 0; stopped_attack = 0
    for o in obs:
        if o.route != "AUTO" or o.paid_day is None: continue
        covers = (o.vendor in (changed_vendors or set())) if action == "hold_changed" else _stops(action, trigger, o, eff)
        in_force = o.paid_day > eff and (action == "rollback_control" or o.paid_day <= eff + hold_days)
        if o.id in truth:
            if o.paid_day <= eff: gone += truth[o.id]
            elif covers and in_force: prevented += truth[o.id]; stopped_attack += 1
            else: remain += truth[o.id]
        elif covers and in_force: col_n += 1; col += o.amount
    return dict(action=action, lag=lag, prevented=prevented, gone=gone, remaining=remain, stopped_attacks=stopped_attack, collateral_items=col_n, collateral_cents=col)

def standing_hold(obs: list, truth: dict, eff: int, season: int = 3, honour_confirmation: bool = False) -> dict:
    """A containment that is a rule, not a list: from day `eff`, hold every AUTO payment to a destination that is not the vendor's first-seen one, until `season` payments went to the new one.
    State is rebuilt from day 0 (the rule only *acts* from eff).  A confirmed change is released only if honour_confirmation."""
    base = {}; seen = {}; conf = {}; prevented = gone = remain = 0; col = col_n = 0
    for o in sorted(obs, key=lambda x: (x.day, x.id)):
        key = (o.vendor, o.dest); base.setdefault(o.vendor, o.dest)
        if o.change_confirmed is not None: conf[key] = o.change_confirmed
        young = o.dest != base[o.vendor] and seen.get(key, 0) < season
        acts = o.route == "AUTO" and o.paid_day is not None and o.paid_day > eff and young and not (honour_confirmation and conf.get(key))
        if o.route == "AUTO" and o.paid_day is not None:
            if o.id in truth:
                if o.paid_day <= eff: gone += truth[o.id]
                elif acts: prevented += truth[o.id]
                else: remain += truth[o.id]
            elif acts: col_n += 1; col += o.amount
        seen[key] = seen.get(key, 0) + 1
    return dict(action="standing_hold_changed", eff=eff, prevented=prevented, gone=gone, remaining=remain, collateral_items=col_n, collateral_cents=col)

def tamper_checks(rows: list, chain_cls, anchors, name: str) -> dict:
    """Which edits to an exported chain are visible?  Each scenario edits a copy and reports (chain ok, anchors ok)."""
    import copy, hashlib as h
    from .evidence import canon
    out = {}
    def rehash(rs, start=0):
        prev = rs[start - 1]["hash"] if start else "0" * 64
        for i in range(start, len(rs)):
            rs[i]["seq"] = i; rs[i]["prev"] = prev; rs[i]["hash"] = h.sha256(canon({k: v for k, v in rs[i].items() if k != "hash"})).hexdigest(); prev = rs[i]["hash"]
    def verdict(rs): ok, _ = chain_cls.verify_rows(rs); return dict(chain=ok, anchor=anchors.check(name, rs)[0])
    r = copy.deepcopy(rows); r[len(r) // 2]["amount"] = 1; out["edit_row_no_rehash"] = verdict(r)
    r = copy.deepcopy(rows); del r[len(r) // 2]; out["delete_row_no_rehash"] = verdict(r)
    r = copy.deepcopy(rows); r[len(r) // 2]["decision"] = "edited"; rehash(r, len(r) // 2); out["edit_and_rechain_from_row"] = verdict(r)
    r = copy.deepcopy(rows); r = r[:-40]; out["truncate_tail_40"] = verdict(r)
    r = copy.deepcopy(rows); del r[len(r) // 2]; rehash(r, 0); out["delete_row_and_rechain_all"] = verdict(r)
    return out

@dataclass
class Decision:
    what: str; owner: Optional[str]; deadline: Optional[str]; deadline_source: Optional[str]; done: bool = False

@dataclass
class Case:
    id: str; trigger: str; rows: list; config_digest: str; decisions: list = field(default_factory=list)
    def digest(self) -> str: return hashlib.sha256(json.dumps(self.rows, sort_keys=True, default=str).encode()).hexdigest()[:16]
    def add(self, d: Decision): self.decisions.append(d)
    def open_questions(self) -> list[str]:
        q = []
        for d in self.decisions:
            if d.owner in (None, ""): q.append(f"NO_OWNER:{d.what}")
            if d.deadline is None: q.append(f"NO_DEADLINE:{d.what}")
            elif d.deadline_source in (None, "", "VERIFY"): q.append(f"DEADLINE_UNSOURCED:{d.what}")
            if not d.done: q.append(f"OPEN:{d.what}")
        return q
    def can_close(self) -> bool: return not self.open_questions()
