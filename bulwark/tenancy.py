"""Chapter 11: data boundaries and tenancy.

Corpus / Doc      a seeded multi-tenant document set in which vendors, amounts and phrases recur across tenants, as they do in real books.
Index             a small keyword index (tf-idf over the pooled corpus) with five retrieval modes:
                    none       no tenant predicate at all
                    arg        tenant predicate taken from an argument the caller (the model) supplies
                    post       top-k over the pooled corpus, then a filter by the verified tenant
                    pushdown   the verified tenant is a predicate applied before ranking
                    partition  one index per tenant
ResultCache       a cache of search results keyed by query alone or by (tenant, query)
TicketStore       tickets with sequential or random ids, read with or without a tenant check
KeyRing           one shared signing key, or one key per tenant derived from a master key (HKDF-SHA256)
safe_text         the one function every attacker-writable string passes before it reaches a screen
project / Handles field projection for the model, and opaque handles for values the model needs to name but not read
"""
from __future__ import annotations
import hashlib, hmac, math, re, secrets, unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Optional

# ---------------------------------------------------------------- corpus
VENDORS = ["Lone Star Paper Supply", "Riverside Office Interiors", "Zilker Packaging", "Capitol Flour Mills", "Barton Creek Plumbing",
           "Hill Country Linens", "Colorado River Freight", "Pecan Street Printing", "Mueller Equipment Lease", "South Congress Cleaning"]
TOPICS = ["invoice for monthly order", "reminder: payment due Friday", "quote for autumn delivery", "statement of account", "credit note for damaged goods",
          "delivery schedule for next week", "price increase notice", "purchase order confirmation", "remittance advice", "dispute about quantity delivered"]

@dataclass(frozen=True)
class Doc:
    doc_id: str; tenant: str; text: str; secret: str = ""

class Corpus:
    def __init__(self, tenants: int, per_tenant: int, seed: int = 11):
        import random
        rng = random.Random(seed); self.docs: list[Doc] = []; self.tenants = [f"biz_{i:03d}" for i in range(tenants)]
        self.vendors_of = {}
        for t in self.tenants:
            vs = rng.sample(VENDORS, 5); self.vendors_of[t] = vs
            for n in range(per_tenant):
                v = rng.choice(vs); topic = rng.choice(TOPICS); amt = rng.randrange(20_000, 400_000, 100)
                tax = f"TX-{rng.randrange(10000, 99999)}"; acct = f"ACC-{rng.randrange(10**7, 10**8)}"
                secret = acct if n % 7 == 0 else ""
                text = f"{v} {topic}. Amount ${amt/100:,.2f}. Reference {t}-{n:03d}." + (f" Pay to account {acct}. Tax id {tax}." if secret else "")
                self.docs.append(Doc(f"{t}-{n:03d}", t, text, secret))
        self.by_id = {d.doc_id: d for d in self.docs}

def tokens(s: str) -> list[str]: return re.findall(r"[a-z0-9$.,\-]+", s.lower().replace(".", " ").replace(",", " "))

class _Idx:
    def __init__(self, docs: list[Doc]):
        self.docs = docs; self.tf = [Counter(tokens(d.text)) for d in docs]; df = Counter()
        for c in self.tf: df.update(c.keys())
        n = max(len(docs), 1); self.idf = {w: math.log(1 + n / f) for w, f in df.items()}
        self.inv = defaultdict(list)
        for i, c in enumerate(self.tf):
            for w in c: self.inv[w].append(i)
    def rank(self, q: str, allow=None) -> list[tuple[float, Doc]]:
        sc = defaultdict(float)
        for w in tokens(q):
            for i in self.inv.get(w, ()): 
                if allow is None or allow(self.docs[i]): sc[i] += self.tf[i][w] * self.idf[w]
        return sorted(((s, self.docs[i]) for i, s in sc.items()), key=lambda x: (-x[0], x[1].doc_id))

class Index:
    def __init__(self, corpus: Corpus, mode: str):
        assert mode in ("none", "arg", "post", "pushdown", "partition"); self.mode = mode; self.corpus = corpus
        self.pool = _Idx(corpus.docs)
        self.parts = {t: _Idx([d for d in corpus.docs if d.tenant == t]) for t in corpus.tenants} if mode == "partition" else {}
    def search(self, q: str, k: int = 5, verified_tenant: Optional[str] = None, arg_tenant: Optional[str] = None) -> list[Doc]:
        m = self.mode
        if m == "none": return [d for _, d in self.pool.rank(q)[:k]]
        if m == "arg": t = arg_tenant; return [d for _, d in self.pool.rank(q, (lambda d: d.tenant == t) if t else None)[:k]]
        if m == "post": return [d for _, d in self.pool.rank(q)[:k] if d.tenant == verified_tenant]
        if m == "pushdown": return [d for _, d in self.pool.rank(q, lambda d: d.tenant == verified_tenant)[:k]]
        return [d for _, d in self.parts[verified_tenant].rank(q)[:k]]

# ---------------------------------------------------------------- cache, tickets, keys
class ResultCache:
    def __init__(self, scoped: bool): self.scoped, self.d = scoped, {}
    def key(self, tenant, q): return (tenant, q) if self.scoped else (q,)
    def get_or_compute(self, tenant, q, fn):
        k = self.key(tenant, q)
        if k not in self.d: self.d[k] = fn()
        return self.d[k]

class TicketStore:
    def __init__(self, random_ids: bool, check_tenant: bool):
        self.random_ids, self.check, self.rows, self._n = random_ids, check_tenant, {}, 0
    def put(self, tenant, payload) -> str:
        self._n += 1; tid = secrets.token_hex(12) if self.random_ids else f"T{self._n:05d}"; self.rows[tid] = (tenant, payload); return tid
    def get(self, tid, caller_tenant):
        r = self.rows.get(tid)
        if r is None: return None
        if self.check and r[0] != caller_tenant: return None
        return r[1]

class KeyRing:
    def __init__(self, master: bytes, per_tenant: bool): self.master, self.per = master, per_tenant
    def key(self, tenant: str) -> bytes:
        if not self.per: return self.master
        prk = hmac.new(b"ledgerly-tenant-keys-v1", self.master, hashlib.sha256).digest()      # HKDF extract
        return hmac.new(prk, f"tenant:{tenant}".encode() + b"\x01", hashlib.sha256).digest()   # HKDF expand, one block

class Chain:
    """Hash chain over evidence events. shared: one chain for all tenants; per-tenant: one chain each."""
    def __init__(self): self.rows = []; self.head = "0" * 64
    def append(self, tenant, event):
        h = hashlib.sha256(f"{self.head}|{tenant}|{event}".encode()).hexdigest(); self.rows.append((tenant, event, self.head, h)); self.head = h
    def export_for(self, tenant):
        """What a tenant needs in order to verify its own events: every row from the first to the last of its events, with other tenants' rows
        reduced to the hash inputs it cannot recompute without them (their rows are present in full unless the chain is per-tenant)."""
        idx = [i for i, r in enumerate(self.rows) if r[0] == tenant]
        if not idx: return []
        return self.rows[idx[0]: idx[-1] + 1]

# ---------------------------------------------------------------- text that reaches a person
_BIDI = set("\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069\u200e\u200f\u061c")
_ZW = set("\u200b\u200c\u200d\u2060\ufeff\u00ad")
def safe_text(s: str, max_len: int = 80) -> str:
    """Normalise (NFKC), drop control, format and bidi characters, collapse every run of whitespace to one space, strip markup characters, cut to max_len.
    The result is one line, printable, with no characters that a renderer treats as structure."""
    s = unicodedata.normalize("NFKC", s)
    out = []
    for ch in s:
        cat = unicodedata.category(ch)
        if ch in _BIDI or ch in _ZW or cat in ("Cc", "Cf", "Cs", "Co", "Cn"):
            out.append(" " if ch in "\r\n\t\v\f\x85\u2028\u2029" else "")
        elif cat in ("Zs", "Zl", "Zp"): out.append(" ")
        elif ch in "<>`|\\": out.append("")
        else: out.append(ch)
    s = re.sub(r"\s+", " ", "".join(out)).strip()
    return s[:max_len]

# ---------------------------------------------------------------- what the model sees
SENSITIVE = {"bank_account": 3, "tax_id": 3, "contact_email": 2, "contact_phone": 2, "address": 1}
PROJECTIONS = {   # task -> fields the model may see; everything else stays in the record
    "summarise_invoice": ["invoice_number", "vendor_name", "amount_cents", "due_date", "status", "line_items"],
    "draft_reminder": ["invoice_number", "vendor_name", "amount_cents", "due_date", "contact_email"],
    "prepare_payment": ["invoice_number", "vendor_name", "amount_cents", "due_date", "status", "vendor_ref"],
    "answer_question": ["invoice_number", "vendor_name", "amount_cents", "due_date", "status", "line_items"],
}
def project(record: dict, task: str) -> dict:
    allowed = PROJECTIONS[task]; return {k: record[k] for k in allowed if k in record}

class Handles:
    """Opaque references for values the model must be able to name and must not be able to read. Resolved only by the wrapper, per tenant."""
    def __init__(self): self.t: dict[tuple[str, str], str] = {}; self.r: dict[tuple[str, str], str] = {}
    def issue(self, tenant: str, value: str, kind: str) -> str:
        k = (tenant, value)
        if k not in self.t:
            h = f"{kind}_ref_{len([1 for (tt, _) in self.t if tt == tenant]) + 1}"; self.t[k] = h; self.r[(tenant, h)] = value
        return self.t[k]
    def resolve(self, tenant: str, handle: str) -> Optional[str]: return self.r.get((tenant, handle))

def mixed_script(s: str) -> bool:
    """True if one string mixes Latin letters with letters from another script (a homoglyph risk). A name for a record, checked when the record is created."""
    scripts = set()
    for ch in s:
        if ch.isalpha():
            n = unicodedata.name(ch, "")
            scripts.add("LATIN" if n.startswith("LATIN") else n.split(" ")[0] or "?")
    return len(scripts) > 1
