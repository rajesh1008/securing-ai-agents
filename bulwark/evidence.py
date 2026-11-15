"""Chapter 13: evidence. What the product records so that someone who was not there can detect, investigate and prove.

Rules the module enforces (each is a lab result in Chapter 13):
  1. An event is typed. Every field is a code, an id, a host, a digest, a number or a flag. A free-text value is never stored: it is replaced by a keyed digest and a length.
  2. One chain per tenant, so a tenant's evidence can be exported, verified and erased without touching anyone else's.
  3. Digests of content are keyed with the tenant's own key (HMAC), so a low-entropy value (an account number) cannot be recovered by guessing, and destroying the key unlinks them.
  4. The chain hash needs no key, so anyone can verify it. The anchor (head hash, per tenant) is held by a service the writer can submit to and cannot edit.
  5. The content the digests describe goes to a per-tenant store, encrypted under that tenant's key. Erasure is the destruction of the tenant's key salt and the store; the chain stays valid.
The cipher in ContentStore is a lab stand-in built from HMAC in counter mode; production would use an AEAD from a reviewed library.
"""
from __future__ import annotations
import hashlib, hmac, json, os, re
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlsplit

GENESIS = "0" * 64
CODE = re.compile(r"^[A-Za-z0-9_:.\-]{1,48}$")
HOST = re.compile(r"^[a-z0-9.\-]{1,120}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
ID = re.compile(r"^[A-Za-z0-9_\-]{1,48}$")

# field -> kind. 'code' short token; 'codes' list of codes; 'id'; 'host'; 'digest'; 'int'; 'bool'; 'ts'
SCHEMA = {
    "ts": "ts", "kind": "code", "principal": "id", "actor": "id", "task": "id", "tool": "code", "decision": "code", "reasons": "codes",
    "policy": "code", "level": "int", "dest_host": "host", "ctx_digest": "digest", "out_digest": "digest", "edits": "int", "canary": "bool",
    "effect_digest": "digest", "approver": "id", "approval_ms": "int", "grant": "id", "token_id": "id", "bytes_out": "int", "note_digest": "digest", "note_len": "int",
    "source_ids": "codes", "doc_digest": "digest", "extractor": "code", "confidence": "int", "route": "code",
    # Chapter 39: the payment path (one payment explained end to end)
    "amount_cents": "int", "invoice": "id", "payee": "id", "sender": "id", "receiver": "id", "verb": "code", "hop": "int", "taint": "codes", "model": "code", "prompt_version": "code",
    "vendor_version": "int", "dest_digest": "digest", "markers": "int", "detector": "code",
}

def canon(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()

def host_only(url_or_addr: str) -> str:
    """The destination with the data removed: scheme, path, query, fragment and user information dropped; an email address reduced to its domain."""
    s = url_or_addr.strip()
    if "@" in s and "://" not in s: return s.rsplit("@", 1)[1].lower()
    try: h = urlsplit(s).hostname or ""
    except ValueError: h = ""
    return h.lower()

class Evidence:
    """Writer-side helper: validates and normalises one event. `keys` gives the per-tenant content key."""
    def __init__(self, keyfor): self.keyfor = keyfor
    def digest(self, tenant: str, value) -> str:
        data = value if isinstance(value, bytes) else str(value).encode()
        return hmac.new(self.keyfor(tenant), b"evidence-digest-v1|" + data, hashlib.sha256).hexdigest()
    def build(self, tenant: str, **f) -> dict:
        """Returns a typed event. A string that is not a code, id or host is moved to note_digest/note_len; an unknown field name is an error (the schema is closed)."""
        ev = {}; rejected = []
        for k, v in f.items():
            if k.startswith("raw_"):                      # raw_<name>: free text offered for the record; kept as a digest of the value only
                ev["note_digest"] = self.digest(tenant, v); ev["note_len"] = len(str(v)); continue
            kind = SCHEMA.get(k)
            if kind is None: raise KeyError(f"field not in schema: {k}")
            ok = {"code": lambda x: isinstance(x, str) and CODE.match(x), "codes": lambda x: isinstance(x, (list, tuple)) and all(isinstance(c, str) and CODE.match(c) for c in x),
                  "id": lambda x: isinstance(x, str) and ID.match(x), "host": lambda x: isinstance(x, str) and (x == "" or HOST.match(x)), "digest": lambda x: isinstance(x, str) and HEX64.match(x),
                  "int": lambda x: isinstance(x, int) and not isinstance(x, bool), "bool": lambda x: isinstance(x, bool), "ts": lambda x: isinstance(x, int)}[kind](v)
            if not ok:
                ev["note_digest"] = self.digest(tenant, v); ev["note_len"] = len(str(v)); rejected.append(f"FIELD_REJECTED:{k}"); continue
            ev[k] = list(v) if kind == "codes" else v
        if rejected: ev["reasons"] = list(ev.get("reasons", [])) + rejected
        ev["tenant"] = tenant
        return ev

class ChainLog:
    """Append-only list of events, each with prev and hash = SHA-256 over the canonical event including prev. No key is needed to verify."""
    def __init__(self): self.rows: list[dict] = []
    @property
    def head(self) -> str: return self.rows[-1]["hash"] if self.rows else GENESIS
    def append(self, ev: dict) -> dict:
        r = dict(ev); r["seq"] = len(self.rows); r["prev"] = self.head; r["hash"] = hashlib.sha256(canon({k: v for k, v in r.items() if k != "hash"})).hexdigest(); self.rows.append(r); return r
    @staticmethod
    def verify_rows(rows: list[dict]) -> tuple[bool, Optional[int]]:
        prev = GENESIS
        for i, r in enumerate(rows):
            if r.get("prev") != prev or r.get("seq") != i or hashlib.sha256(canon({k: v for k, v in r.items() if k != "hash"})).hexdigest() != r.get("hash"): return False, i
            prev = r["hash"]
        return True, None
    def verify(self): return self.verify_rows(self.rows)

class Anchors:
    """The anchor service. The writer may submit (name, seq, head). It cannot read the key or edit the store. Each record carries a MAC under the service's key."""
    def __init__(self, key: bytes | None = None): self._key = key or os.urandom(32); self.store: list[dict] = []
    def _mac(self, name, seq, head): return hmac.new(self._key, f"{name}|{seq}|{head}".encode(), hashlib.sha256).hexdigest()
    def submit(self, name: str, seq: int, head: str): self.store.append(dict(name=name, seq=seq, head=head, mac=self._mac(name, seq, head)))
    def check(self, name: str, rows: list[dict]) -> tuple[bool, str]:
        for a in self.store:
            if a["name"] != name: continue
            if a["mac"] != self._mac(a["name"], a["seq"], a["head"]): return False, "anchor record altered"
            if a["seq"] >= len(rows): return False, f"truncated: anchor at {a['seq']}, log has {len(rows)}"
            if rows[a["seq"]]["hash"] != a["head"]: return False, f"anchor mismatch at {a['seq']}"
        return True, "ok"
    def last_seq(self, name: str) -> int: return max([a["seq"] for a in self.store if a["name"] == name], default=-1)

class ContentStore:
    """Per-tenant store of what the digests describe, encrypted under the tenant's key. Deleting the store and the key is erasure. Lab cipher: HMAC counter-mode keystream."""
    def __init__(self, key: bytes): self.key = key; self.items: dict[str, bytes] = {}
    def _ks(self, nonce: bytes, n: int) -> bytes:
        out = b""; c = 0
        while len(out) < n: out += hmac.new(self.key, nonce + c.to_bytes(4, "big"), hashlib.sha256).digest(); c += 1
        return out[:n]
    def put(self, name: str, content: bytes):
        nonce = os.urandom(12); self.items[name] = nonce + bytes(a ^ b for a, b in zip(content, self._ks(nonce, len(content))))
    def get(self, name: str, key: bytes | None = None) -> bytes | None:
        raw = self.items.get(name)
        if raw is None: return None
        k = key if key is not None else self.key
        if k is None: return None
        s = ContentStore(k); return bytes(a ^ b for a, b in zip(raw[12:], s._ks(raw[:12], len(raw) - 12)))

class Vault:
    """The product's evidence system: one chain, one key and one content store per tenant, one anchor service."""
    def __init__(self, master: bytes, anchor_every: int = 25):
        self.master, self.every = master, anchor_every; self.logs: dict[str, ChainLog] = {}; self.stores: dict[str, ContentStore] = {}; self.anchors = Anchors(); self.shredded: set[str] = set(); self.salts: dict[str, bytes] = {}
        self.ev = Evidence(self.key)
    def key(self, tenant: str) -> bytes:
        """Tenant key = HMAC(master, per-tenant random salt). The salt is the thing that is destroyed on erasure: a key derived from the master alone could be re-derived by anyone who holds the master."""
        if tenant in self.shredded: return b"\x00" * 32
        salt = self.salts.setdefault(tenant, os.urandom(16))
        return hmac.new(hmac.new(b"ledgerly-evidence-keys-v1", self.master, hashlib.sha256).digest(), b"tenant:" + tenant.encode() + b"|" + salt, hashlib.sha256).digest()
    def pseudonym(self, tenant: str, person: str) -> str:
        """A stable id for a person inside one tenant's chain: u_ plus 10 hex characters of HMAC under the tenant key. The table that maps it back lives in the tenant's content store."""
        return "u_" + hmac.new(self.key(tenant), b"person|" + person.encode(), hashlib.sha256).hexdigest()[:10]
    def record(self, tenant: str, content: dict | None = None, **fields) -> dict:
        log = self.logs.setdefault(tenant, ChainLog()); st = self.stores.setdefault(tenant, ContentStore(self.key(tenant)))
        ev = self.ev.build(tenant, **fields); r = log.append(ev)
        if content:
            for name, val in content.items(): st.put(f"{r['seq']}:{name}", val if isinstance(val, bytes) else str(val).encode())
        if (r["seq"] + 1) % self.every == 0: self.anchors.submit(tenant, r["seq"], r["hash"])
        return r
    def seal(self, tenant: str):
        log = self.logs[tenant]
        if log.rows and self.anchors.last_seq(tenant) != len(log.rows) - 1: self.anchors.submit(tenant, len(log.rows) - 1, log.head)
    def verify(self, tenant: str) -> tuple[bool, str]:
        log = self.logs[tenant]; ok, bad = log.verify()
        if not ok: return False, f"chain broken at {bad}"
        return self.anchors.check(tenant, log.rows)
    def export(self, tenant: str) -> dict:
        """What a tenant, an examiner or a court receives: the rows, the anchors for this tenant only, and the head. No other tenant's row is in it."""
        return dict(tenant=tenant, rows=self.logs[tenant].rows, anchors=[a for a in self.anchors.store if a["name"] == tenant])
    def erase(self, tenant: str) -> dict:
        """Right-to-erasure: destroy the content store and the tenant's key. The chain rows remain (typed fields, keyed digests) and still verify."""
        n = len(self.stores[tenant].items) if tenant in self.stores else 0
        self.stores.pop(tenant, None); self.shredded.add(tenant); self.salts.pop(tenant, None)
        return dict(items_destroyed=n)

def egress_event(vault: Vault, tenant: str, task: str, principal: str, level: int, out, ok: bool, why: str, text_out: str, edits: int, canary: bool, policy: str, ts: int, store_content: bool = True) -> dict:
    """Chapter 12's inheritance: one egress decision as one typed event. Destination host with the data removed, reason code, level, digest of the output and of what left, edits by render, canary."""
    dest = host_only(out.url or out.to) if out.kind in ("request", "email") else ""
    reason = why.replace(":", ".")[:48] or "ok"
    return vault.record(tenant, content=({"output": out.body or out.url or out.to, "left": text_out} if store_content else None), ts=ts, kind="egress", principal=principal, task=task, tool=out.kind,
                        decision="ALLOW" if ok else "DENY", reasons=[reason], policy=policy, level=level, dest_host=dest, out_digest=vault.ev.digest(tenant, out.body or out.url or out.to),
                        ctx_digest=vault.ev.digest(tenant, text_out), edits=edits, canary=canary, bytes_out=len(text_out.encode()))
