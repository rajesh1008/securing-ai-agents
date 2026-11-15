"""Chapter 6: identity for an agent. Per-task, signed, audience-bound, scope-bound, budgeted credentials.

Issuer      mints a task token (Ed25519, compact JWT-shaped) for one task, one principal, one agent workload.
Verifier    runs at the tool boundary, never inside the model's reach; checks signature, audience, expiry, principal,
            tenant, workload (sender constraint), scope, use budget, key status and task status.
AmbientVerifier  the baseline most prototypes ship: one static tenant credential, checked for tenant only.
"""
from __future__ import annotations
import base64, json, time, secrets
from dataclasses import dataclass, field
from typing import Optional
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.exceptions import InvalidSignature
from .models import ActionProposal, ActionKind

def b64e(b: bytes) -> str: return base64.urlsafe_b64encode(b).rstrip(b"=").decode()
def b64d(s: str) -> bytes: return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))

AUD = "ledgerly-tool-gateway"

@dataclass
class Scope:
    kinds: list[str]
    payees: Optional[list[str]] = None      # registry ids a payment may name
    max_cents: Optional[int] = None         # per-action ceiling
    mail_domains: Optional[list[str]] = None
    def to_json(self): return dict(kinds=self.kinds, payees=self.payees, max_cents=self.max_cents, mail_domains=self.mail_domains)
    def within(self, parent: "Scope") -> bool:
        """True if self is no wider than parent (attenuation)."""
        if not set(self.kinds) <= set(parent.kinds): return False
        if parent.payees is not None and (self.payees is None or not set(self.payees) <= set(parent.payees)): return False
        if parent.max_cents is not None and (self.max_cents is None or self.max_cents > parent.max_cents): return False
        if parent.mail_domains is not None and (self.mail_domains is None or not set(self.mail_domains) <= set(parent.mail_domains)): return False
        return True

@dataclass
class SupportGrant:
    """Written by the support-access system, not by the agent: an engineer may act for a tenant, read-only, for a short time."""
    actor: str
    tenant: str
    principal: str
    expires: float
    kinds: tuple = ("read_document", "query_books")

@dataclass
class Delegation:
    """A standing delegation for unattended tasks: approved by a named person, bounded in scope, expiring, revocable in one place."""
    delegation_id: str
    principal: str
    tenant: str
    task_type: str
    scope: Scope
    approved_by: str
    approved_at: float
    expires: float
    revoked: bool = False

@dataclass
class IssuancePolicy:
    max_tokens_per_hour: int = 60            # per principal
    max_open_payment_tokens: int = 3         # per tenant, tokens whose scope includes initiate_payment and that have not expired

class IssuanceRefused(Exception): pass

class Issuer:
    def __init__(self, clock=time.time):
        self.clock = clock
        self.keys: dict[str, Ed25519PrivateKey] = {}
        self.status: dict[str, tuple[str, float]] = {}   # kid -> ("active"|"retired"|"revoked", changed_at)
        self.current: Optional[str] = None
        self.rotate()
        self.issued: dict[str, dict] = {}
        self.grants: list[SupportGrant] = []
        self.max_ttl = 900
        self.delegations: dict[str, Delegation] = {}
        self.policy: Optional[IssuancePolicy] = None
        self.minted_log: list[tuple[float, str, str, bool, int]] = []   # (time, principal, tenant, has_payment, exp)

    def rotate(self, kid: Optional[str] = None) -> str:
        kid = kid or f"k{len(self.keys) + 1}"
        self.keys[kid] = Ed25519PrivateKey.generate()
        if self.current: self.status[self.current] = ("retired", self.clock())
        self.status[kid] = ("active", self.clock()); self.current = kid
        return kid

    def public_keys(self) -> dict[str, Ed25519PublicKey]:
        return {k: v.public_key() for k, v in self.keys.items()}

    def _sign(self, claims: dict, kid: Optional[str] = None) -> str:
        kid = kid or self.current
        head = {"alg": "EdDSA", "typ": "task+jwt", "kid": kid}
        signing = b64e(json.dumps(head, sort_keys=True).encode()) + "." + b64e(json.dumps(claims, sort_keys=True).encode())
        return signing + "." + b64e(self.keys[kid].sign(signing.encode()))

    def issue(self, *, principal: str, tenant: str, workload: str, task_id: str, scope: Scope, ttl: int = 300,
              uses: int = 1, actor: Optional[str] = None, agent_version: str = "0.2.0") -> str:
        ttl = min(ttl, self.max_ttl)
        self._check_policy(principal, tenant, scope, ttl)
        if actor:   # support impersonation: the grant bounds the scope and the lifetime
            g = next((g for g in self.grants if g.actor == actor and g.tenant == tenant and g.principal == principal and g.expires > self.clock()), None)
            if g is None: raise IssuanceRefused("no live support grant for this actor and tenant")
            if not set(scope.kinds) <= set(g.kinds): raise IssuanceRefused("scope wider than the support grant")
            ttl = min(ttl, int(g.expires - self.clock()))
        now = int(self.clock())
        claims = dict(iss="ledgerly-issuer", sub=principal, aud=AUD, biz=tenant, tid=task_id, jti=secrets.token_hex(8),
                      iat=now, exp=now + ttl, uses=uses, scope=scope.to_json(), act=dict(sub=workload, ver=agent_version))
        if actor: claims["actor"] = actor
        self.issued[claims["jti"]] = claims
        return self._sign(claims)

    def _check_policy(self, principal: str, tenant: str, scope: Scope, ttl: int):
        if self.policy is None: return
        now = self.clock()
        recent = [m for m in self.minted_log if m[1] == principal and now - m[0] < 3600]
        if len(recent) >= self.policy.max_tokens_per_hour: raise IssuanceRefused("hourly token limit for this principal")
        if "initiate_payment" in scope.kinds:
            open_pay = [m for m in self.minted_log if m[2] == tenant and m[3] and m[4] > now]
            if len(open_pay) >= self.policy.max_open_payment_tokens: raise IssuanceRefused("too many open payment tokens for this tenant")
        self.minted_log.append((now, principal, tenant, "initiate_payment" in scope.kinds, int(now) + ttl))

    def issue_scheduled(self, *, delegation_id: str, workload: str, task_id: str, ttl: int = 300, uses: int = 1) -> str:
        d = self.delegations.get(delegation_id)
        if d is None or d.revoked: raise IssuanceRefused("no live delegation")
        if d.expires <= self.clock(): raise IssuanceRefused("delegation expired")
        claims_extra = dict(delegation=delegation_id)
        tok = self.issue(principal=d.principal, tenant=d.tenant, workload=workload, task_id=task_id, scope=d.scope, ttl=ttl, uses=uses)
        c = json.loads(b64d(tok.split(".")[1])); c.update(claims_extra, approved_by=d.approved_by)
        self.issued[c["jti"]] = c
        return self._sign(c)

    def derive(self, parent_token: str, *, scope: Scope, workload: str, ttl: int, uses: int = 1) -> str:
        """Attenuating delegation: a child may be narrower and shorter than its parent, never wider."""
        pc = json.loads(b64d(parent_token.split(".")[1]))
        if self.issued.get(pc["jti"]) != pc: raise IssuanceRefused("parent not issued here")
        ps = Scope(**pc["scope"])
        if not scope.within(ps): raise IssuanceRefused("child scope wider than parent")
        now = int(self.clock())
        if now + ttl > pc["exp"]: raise IssuanceRefused("child outlives parent")
        claims = dict(pc, jti=secrets.token_hex(8), iat=now, exp=now + ttl, uses=uses, scope=scope.to_json(),
                      act=dict(sub=workload, ver=pc["act"]["ver"], parent=pc["jti"]))
        self.issued[claims["jti"]] = claims
        return self._sign(claims)

@dataclass
class VerifyResult:
    allow: bool
    reasons: list[str]
    claims: Optional[dict] = None

import sqlite3

class SqliteUseStore:
    """Shared, atomic use counter for several gateway replicas: one row per token id, incremented only while below its budget."""
    def __init__(self, path: str):
        self.path = path
        c = sqlite3.connect(path, timeout=30); c.execute("CREATE TABLE IF NOT EXISTS uses (jti TEXT PRIMARY KEY, used INTEGER NOT NULL)"); c.commit(); c.close()
    def consume(self, jti: str, budget: int) -> bool:
        c = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        try:
            c.execute("BEGIN IMMEDIATE")
            c.execute("INSERT OR IGNORE INTO uses (jti, used) VALUES (?, 0)", (jti,))
            cur = c.execute("UPDATE uses SET used = used + 1 WHERE jti = ? AND used < ?", (jti, budget))
            ok = cur.rowcount == 1
            c.execute("COMMIT")
            return ok
        finally:
            c.close()

class Verifier:
    def __init__(self, public_keys: dict, status_fn, clock=time.time, grace: int = 600, use_store=None):
        self.pub, self.status_fn, self.clock, self.grace = public_keys, status_fn, clock, grace
        self.use_store = use_store
        self.used: dict[str, int] = {}
        self.closed_tasks: set[str] = set()

    def verify(self, token: str, proposal: ActionProposal, *, caller_workload: str, task_id: Optional[str] = None) -> VerifyResult:
        r: list[str] = []
        try:
            h, c, s = token.split(".")
            head = json.loads(b64d(h)); claims = json.loads(b64d(c)); sig = b64d(s)
        except Exception:
            return VerifyResult(False, ["malformed token"])
        if head.get("alg") != "EdDSA": return VerifyResult(False, [f"algorithm {head.get('alg')!r} not accepted"])
        kid = head.get("kid"); pub = self.pub.get(kid)
        if pub is None: return VerifyResult(False, ["unknown key id"])
        try: pub.verify(sig, (h + "." + c).encode())
        except InvalidSignature: return VerifyResult(False, ["bad signature"])
        st, changed = self.status_fn(kid); now = self.clock()
        if st == "revoked": r.append("key revoked")
        elif st == "retired" and now - changed > self.grace: r.append("key retired beyond grace")
        if claims.get("aud") != AUD: r.append("wrong audience")
        if claims.get("exp", 0) <= now: r.append("expired")
        if claims.get("biz") != proposal.business_id: r.append("tenant mismatch")
        if claims.get("sub") != proposal.principal_id: r.append("principal mismatch")
        if claims.get("act", {}).get("sub") != caller_workload: r.append("presented by a different workload")
        if task_id is not None and claims.get("tid") != task_id: r.append("token belongs to a different task")
        if claims.get("tid") in self.closed_tasks: r.append("task closed")
        sc = claims.get("scope", {})
        if proposal.kind.value not in sc.get("kinds", []): r.append(f"kind {proposal.kind.value} not in scope")
        if sc.get("payees") is not None and proposal.kind == ActionKind.INITIATE_PAYMENT and proposal.payee_id not in sc["payees"]: r.append("payee not in scope")
        if sc.get("max_cents") is not None and (proposal.amount_cents or 0) > sc["max_cents"]: r.append("amount above scope ceiling")
        if sc.get("mail_domains") is not None and proposal.kind in (ActionKind.SEND_EMAIL, ActionKind.SEND_INVOICE):
            if (proposal.recipient_email or "").rsplit("@", 1)[-1].lower() not in sc["mail_domains"]: r.append("recipient domain not in scope")
        if not r:
            if self.use_store is not None:
                if not self.use_store.consume(claims["jti"], claims.get("uses", 1)): r.append("use budget exhausted (replay)")
            else:
                n = self.used.get(claims["jti"], 0)
                if n >= claims.get("uses", 1): r.append("use budget exhausted (replay)")
                else: self.used[claims["jti"]] = n + 1
        return VerifyResult(not r, r or ["ok"], claims if not r else None)

class AmbientVerifier:
    """One static tenant credential in the tool adapters, as in Quill's first quarter."""
    def __init__(self, tenant_keys: dict[str, str]): self.keys = tenant_keys
    def verify(self, api_key: str, proposal: ActionProposal) -> VerifyResult:
        if self.keys.get(proposal.business_id) != api_key: return VerifyResult(False, ["unknown tenant credential"])
        return VerifyResult(True, ["ok"])
