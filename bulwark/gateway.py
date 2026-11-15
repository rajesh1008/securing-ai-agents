"""Chapter 24: a model gateway for Quill.  The agent holds no provider key and names no model; it holds a gateway token and an alias.  Five pieces:
  ModelRegistry   alias -> model id, status (active | deprecated | retired), end-of-life date, purposes, and the refusal-suite verdict for the alias (PASS | REVIEW | BLOCK | none) with an optional waiver
  KeyRing         signing keys with not_before / not_after / revoked; a token verifies under any live key, so rotation has an overlap and revocation is one flag
  Gateway         handle(): verify token, resolve alias for the purpose, refuse direct model ids, refuse retired or blocked, check the budget, forward with the provider key (which only the gateway holds), compare the model that served with the model resolved, write an evidence row with request digest
  alias_move      the decision to move an alias to another model: PASS, REVIEW or BLOCK from the refusal map (Chapter 23) and the legitimate-task completions, per cell, with Wilson intervals
  inventory       scan source text for model identifiers and classify each against the registry and a table of end-of-life dates
The gateway cannot see what the model does with the prompt, cannot read an injection, and forwards whatever the agent sends; it controls which model, which key, how much and what is recorded."""
from __future__ import annotations
import hashlib, hmac, json, re, time
from dataclasses import dataclass, field
from datetime import date
from .alignment import wilson

WARN_DAYS = 30

@dataclass
class ModelEntry:
    alias: str; model_id: str; purposes: set[str]; status: str = "active"; eol: date | None = None
    suite: str | None = None; waiver: str | None = None

class ModelRegistry:
    def __init__(self, entries: list[ModelEntry]): self.by_alias = {e.alias: e for e in entries}; self.ids = {e.model_id for e in entries}
    def resolve(self, alias: str, purpose: str, today: date) -> tuple[ModelEntry | None, str, list[str]]:
        e = self.by_alias.get(alias); warns: list[str] = []
        if e is None: return None, ("DIRECT_MODEL_ID_NOT_ALLOWED" if alias in self.ids or alias.startswith("claude-") else "ALIAS_UNKNOWN"), warns
        if purpose not in e.purposes: return None, "PURPOSE_NOT_APPROVED", warns
        if e.status == "retired" or (e.eol and today >= e.eol): return None, "MODEL_RETIRED", warns
        if e.suite == "BLOCK" and not e.waiver: return None, "ALIAS_SUITE_BLOCK", warns
        if e.status == "deprecated" or (e.eol and (e.eol - today).days <= WARN_DAYS): warns.append(f"EOL_IN_{(e.eol - today).days}_DAYS" if e.eol else "DEPRECATED")
        return e, "ok", warns

class KeyRing:
    def __init__(self): self.keys: dict[str, dict] = {}
    def add(self, kid: str, secret: bytes, not_before: float, not_after: float): self.keys[kid] = dict(secret=secret, nb=not_before, na=not_after, revoked=False)
    def revoke(self, kid: str): self.keys[kid]["revoked"] = True
    def signing(self, now: float) -> str | None:
        live = [(k["na"], kid) for kid, k in self.keys.items() if not k["revoked"] and k["nb"] <= now < k["na"]]
        return max(live)[1] if live else None
    def issue(self, claims: dict, now: float) -> str:
        kid = self.signing(now); assert kid, "no live signing key"
        body = json.dumps(claims, sort_keys=True); sig = hmac.new(self.keys[kid]["secret"], body.encode(), hashlib.sha256).hexdigest()
        return f"{kid}.{body}.{sig}"
    def verify(self, token: str, now: float) -> tuple[dict | None, str]:
        try: kid, rest = token.split(".", 1); body, sig = rest.rsplit(".", 1)
        except ValueError: return None, "TOKEN_MALFORMED"
        k = self.keys.get(kid)
        if k is None: return None, "TOKEN_KEY_UNKNOWN"
        if k["revoked"]: return None, "TOKEN_KEY_REVOKED"
        if not (k["nb"] <= now < k["na"] + 3600): return None, "TOKEN_KEY_EXPIRED"
        if not hmac.compare_digest(sig, hmac.new(k["secret"], body.encode(), hashlib.sha256).hexdigest()): return None, "TOKEN_SIGNATURE_BAD"
        c = json.loads(body)
        if now >= c["exp"]: return None, "TOKEN_EXPIRED"
        return c, "ok"

class Gateway:
    def __init__(self, registry: ModelRegistry, keys: KeyRing, upstream_key: str, forward):
        self.reg, self.keys, self._upstream, self.forward = registry, keys, upstream_key, forward; self.spent: dict[str, int] = {}; self.log: list[dict] = []
    def handle(self, token: str, alias: str, purpose: str, body: dict, today: date, now: float | None = None) -> dict:
        now = time.time() if now is None else now; digest = hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()[:16]
        row = dict(alias=alias, purpose=purpose, digest=digest, t=now); c, why = self.keys.verify(token, now)
        if c is None: return self._done(row, "deny", why)
        row["agent"] = c["agent"]; row["tid"] = c["tid"]
        if alias not in c["aliases"] and alias in self.reg.by_alias: return self._done(row, "deny", "ALIAS_NOT_IN_TOKEN")
        e, why, warns = self.reg.resolve(alias, purpose, today)
        if e is None: return self._done(row, "deny", why)
        if self.spent.get(c["tid"], 0) >= c["budget_tokens"]: return self._done(row, "deny", "TOKEN_BUDGET_EXHAUSTED")
        out = self.forward(self._upstream, e.model_id, body)
        if out.get("error"): row.update(model=e.model_id, warns=warns); return self._done(row, "error", "UPSTREAM_" + out["error"])
        used = int(out.get("usage_tokens", 0)); self.spent[c["tid"]] = self.spent.get(c["tid"], 0) + used
        row.update(model=e.model_id, served=out.get("served"), used=used, warns=warns, latency_ms=out.get("latency_ms"))
        if out.get("served") and out["served"] != e.model_id: row["alert"] = "SERVED_MODEL_MISMATCH"
        return self._done(row, "allow", "ok", out)
    def _done(self, row: dict, decision: str, rule: str, out: dict | None = None) -> dict:
        row.update(decision=decision, rule=rule); self.log.append(row); return dict(decision=decision, rule=rule, row=row, out=out)

def alias_move(old_risk: dict, new_risk: dict, old_ok: dict | None = None, new_ok: dict | None = None) -> tuple[str, list[tuple]]:
    """old_risk / new_risk: cell -> (improper, n).  old_ok / new_ok: legitimate task -> (done, n).
    BLOCK when any risk cell's new interval lies wholly above the old one; REVIEW when a legitimate cell's completion interval lies wholly below; else PASS."""
    moved: list[tuple] = []; verdict = "PASS"
    for k, (a, n) in old_risk.items():
        b, nb = new_risk[k]; lo1, hi1 = wilson(a, n); lo2, hi2 = wilson(b, nb)
        if lo2 > hi1: moved.append((k, "UP", f"{a}/{n}", f"{b}/{nb}")); verdict = "BLOCK"
        elif hi2 < lo1: moved.append((k, "DOWN", f"{a}/{n}", f"{b}/{nb}"))
    for k, (a, n) in (old_ok or {}).items():
        b, nb = (new_ok or {})[k]; lo1, hi1 = wilson(a, n); lo2, hi2 = wilson(b, nb)
        if hi2 < lo1: moved.append((k, "BENIGN_DOWN", f"{a}/{n}", f"{b}/{nb}")); verdict = verdict if verdict == "BLOCK" else "REVIEW"
    return verdict, moved

MODEL_RE = re.compile(r"claude-[a-z0-9][a-z0-9.]*(?:-[a-z0-9][a-z0-9.]*)*", re.I)
def inventory(files: dict[str, str], registry: ModelRegistry, eol_table: dict[str, str]) -> dict:
    """files: path -> text.  Returns occurrences per id with file counts and a class: APPROVED_ID (the id behind an alias), IN_EOL_TABLE, UNKNOWN."""
    found: dict[str, dict] = {}
    for p, t in files.items():
        for m in MODEL_RE.findall(t):
            m = m.rstrip("-.")
            d = found.setdefault(m, dict(count=0, files=set())); d["count"] += 1; d["files"].add(p)
    for m, d in found.items():
        d["files"] = len(d["files"]); d["class"] = "IN_EOL_TABLE" if m in eol_table else ("APPROVED_ID" if m in registry.ids else "UNKNOWN")
        if m in eol_table: d["eol"] = eol_table[m]
    return found
