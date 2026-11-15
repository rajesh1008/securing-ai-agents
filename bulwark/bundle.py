"""Chapter 35: the release bundle.  A bundle is a set of controls, each with a claim sentence, an owner, the threats it answers and the evidence items it rests on.
An evidence item is a file (digest at collection), a kind, the modules it was produced against, a scope sentence and a limit sentence.
`verify` returns the reasons a bundle cannot be signed; `sign` refuses while any are unaccepted, and puts the accepted ones inside the signed payload.
Signatures are Ed25519 (cryptography library) so an auditor needs only the public key."""
from __future__ import annotations
import hashlib, json, os, re
from dataclasses import dataclass, field, asdict
from pathlib import Path

KINDS = ("REVIEW", "UNIT", "SCENARIO", "LAB_SIM", "LAB_LIVE", "PRODUCTION")   # weakest to strongest as support for a claim about operation
RANK = {k: i for i, k in enumerate(KINDS)}
# What a claim may say, by the strongest evidence behind it.  A claim at level L needs at least one item of kind >= L.
CLAIM_LEVELS = {"designed": "REVIEW", "tested": "UNIT", "measured_in_simulation": "LAB_SIM", "measured_live_model": "LAB_LIVE", "operating": "PRODUCTION"}

def sha_file(p: Path) -> str: return hashlib.sha256(p.read_bytes()).hexdigest()
def sha_text(s: str) -> str: return hashlib.sha256(s.encode()).hexdigest()

@dataclass
class Item:
    id: str; path: str; sha: str; kind: str; made: float; subjects: tuple; scope: str; limit: str; n: int | None = None; stamp: dict | None = None   # stamp: module digests the evidence file says it ran against
@dataclass
class Control:
    id: str; name: str; owner: str; threats: tuple; claim: str; level: str; items: tuple; waiver: str = ""
@dataclass
class Bundle:
    release: str; modules: dict; controls: list; items: dict; threats: tuple; open_items: list; as_of: float

def make_item(root: Path, id: str, rel: str, kind: str, subjects: tuple, scope: str, limit: str, n: int | None = None) -> Item:
    p = root / rel; stamp = None
    if p.exists() and p.suffix == ".json":
        try: stamp = json.loads(p.read_text()).get("stamp")
        except Exception: stamp = None
    return Item(id, rel, sha_file(p) if p.exists() else "", kind, p.stat().st_mtime if p.exists() else 0.0, tuple(subjects), scope, limit, n, stamp)

def stamp(code_root: Path, names: list[str]) -> dict:
    """What a lab writes into its own output: the digests of the modules it ran against.  verify compares them with the modules as they are now."""
    return module_digests(code_root, names)

def module_digests(code_root: Path, names: list[str]) -> dict:
    return {n: (sha_file(code_root / "bulwark" / f"{n}.py") if (code_root / "bulwark" / f"{n}.py").exists() else "") for n in names}

def verify(b: Bundle, root: Path, code_root: Path, *, now: float, max_age_days: float = 90.0) -> list[tuple[str, str]]:
    out = []; cited = set()
    for c in b.controls:
        if not c.owner.strip(): out.append(("NO_OWNER", c.id))
        if not c.items: out.append(("NO_EVIDENCE", c.id))
        need = RANK[CLAIM_LEVELS[c.level]]
        have = max([RANK[b.items[i].kind] for i in c.items if i in b.items], default=-1)
        if c.items and have < need: out.append(("SCOPE_OVERREACH", f"{c.id}: claims '{c.level}', strongest item is {KINDS[have] if have >= 0 else 'none'}"))
        for i in c.items:
            cited.add(i)
            if i not in b.items: out.append(("UNKNOWN_ITEM", f"{c.id}:{i}"))
        if c.waiver and not re.match(r"^[A-Z][a-z]+ [A-Z][a-z]+:", c.waiver): out.append(("WAIVER_NO_NAME", c.id))
    for i, it in b.items.items():
        if i not in cited: out.append(("ORPHAN_ITEM", i))
        p = root / it.path
        if not p.exists(): out.append(("FILE_MISSING", f"{i}: {it.path}")); continue
        if sha_file(p) != it.sha: out.append(("FILE_CHANGED", f"{i}: {it.path}"))
        if not it.limit.strip(): out.append(("NO_LIMIT", i))
        if (b.as_of - it.made) / 86400 > max_age_days: out.append(("EXPIRED", i))
        for m in it.subjects:
            mp = code_root / "bulwark" / f"{m}.py"
            if not mp.exists(): out.append(("SUBJECT_MISSING", f"{i}: {m}")); continue
            if it.kind in ("UNIT", "SCENARIO", "LAB_SIM", "LAB_LIVE"):
                if it.stamp and m in it.stamp:
                    if sha_file(mp) != it.stamp[m]: out.append(("CODE_CHANGED", f"{i}: {m} (stamp)"))
                elif sha_file(mp) != b.modules.get(m): out.append(("CODE_CHANGED", f"{i}: {m}"))
                elif mp.stat().st_mtime > it.made + 1: out.append(("STALE_FOR_CODE", f"{i}: {m}"))
    covered = {t for c in b.controls for t in c.threats}
    for t in b.threats:
        if t not in covered: out.append(("UNADDRESSED_THREAT", t))
    return out

def canonical(b: Bundle) -> bytes:
    d = dict(release=b.release, modules=b.modules, controls=[asdict(c) for c in b.controls], items={k: asdict(v) for k, v in sorted(b.items.items())}, threats=list(b.threats), open_items=b.open_items)
    return json.dumps(d, sort_keys=True, separators=(",", ":"), default=list).encode()

def bundle_digest(b: Bundle) -> str: return hashlib.sha256(canonical(b)).hexdigest()

def sign(b: Bundle, issues: list, accept: dict, priv, signer: str, role: str, statement: str, when: float) -> dict:
    """Refuse while an issue kind is neither absent nor accepted by a named sentence.  `accept` maps issue kind -> 'Name Name: reason'."""
    left = [(k, d) for k, d in issues if k not in accept]
    if left: raise ValueError(f"cannot sign: {sorted({k for k, _ in left})}")
    for k, w in accept.items():
        if not re.match(r"^[A-Z][a-z]+ [A-Z][a-z]+:", w): raise ValueError(f"acceptance of {k} has no name")
    payload = dict(bundle=bundle_digest(b), release=b.release, signer=signer, role=role, statement=statement, accepted=[(k, d, accept[k]) for k, d in issues], when=when)
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return dict(payload=payload, sig=priv.sign(raw).hex(), key_id=key_id(priv.public_key()))

def key_id(pub) -> str:
    from cryptography.hazmat.primitives import serialization as S
    return hashlib.sha256(pub.public_bytes(S.Encoding.Raw, S.PublicFormat.Raw)).hexdigest()[:16]

def check_signature(b: Bundle, s: dict, pub) -> tuple[bool, str]:
    from cryptography.exceptions import InvalidSignature
    raw = json.dumps(s["payload"], sort_keys=True, separators=(",", ":")).encode()
    try: pub.verify(bytes.fromhex(s["sig"]), raw)
    except InvalidSignature: return False, "signature does not match payload"
    if key_id(pub) != s["key_id"]: return False, "key id differs"
    if s["payload"]["bundle"] != bundle_digest(b): return False, "bundle differs from the one signed"
    return True, "ok"

def diff(old: Bundle, new: Bundle) -> dict:
    """What an auditor re-reads between two signed releases."""
    oc, nc = {c.id: c for c in old.controls}, {c.id: c for c in new.controls}
    ch = [i for i in oc if i in nc and asdict(oc[i]) != asdict(nc[i])]
    changed_items = [i for i in old.items if i in new.items and old.items[i].sha != new.items[i].sha]
    return dict(controls_added=sorted(set(nc) - set(oc)), controls_removed=sorted(set(oc) - set(nc)), controls_changed=sorted(ch),
                items_added=sorted(set(new.items) - set(old.items)), items_removed=sorted(set(old.items) - set(new.items)), items_changed=sorted(changed_items),
                modules_changed=sorted(m for m in new.modules if old.modules.get(m) != new.modules[m]))

def record_signed(vault, tenant: str, s: dict, day: int, version: int) -> dict:
    """The signature goes into the sealed chain as digests only."""
    return vault.record(tenant, kind="bundle_signed", principal=re.sub(r"[^A-Za-z0-9_\-]", "_", s["payload"]["signer"])[:48], task=f"bundle_v{version}", decision=s["payload"]["bundle"][:16], route=s["key_id"], tool="release", ts=day)

# ---- the attestation: sentences that cite controls (C..) and open items (O..), checked before a person reads them ----
OVERCLAIM = re.compile(r"\b(in production|production[- ]ready|operating|operates|live traffic|real customers?|guarantee[sd]?|fully|always|never|every|all|completely|proven|prove[sd]?|secure|safe|effective(ly)?|eliminat\w+|prevent\w*|immune)\b", re.I)
SCOPE = re.compile(r"\b(simulat\w+|in the lab|lab runs?|unit tests?|in testing|tested|live (model|haiku)|one model|so far|measured|not (yet )?(tested|measured|shown))\b", re.I)
ID = re.compile(r"\b[TCEO]\d+\b")
NUM = re.compile(r"\$?\d[\d,]*(?:\.\d+)?%?")

def open_ids(b: Bundle) -> dict: return {f"O{i + 1}": t for i, t in enumerate(b.open_items)}

def attest_check(claims: list, b: Bundle) -> list[tuple[str, str]]:
    """Seven reasons an attestation cannot go to the signer.  A claim is (text, ids) with ids from the controls and open items."""
    ctl = {c.id: c for c in b.controls}; opn = open_ids(b); out = []; cited = set()
    for c in claims:
        ids = list(c.facts); cited.update(ids)
        if not ids: out.append(("NO_CONTROL", c.text)); continue
        bad = [i for i in ids if i not in ctl and i not in opn]
        if bad: out.append(("BAD_ID", f"{c.text} <- {bad}")); continue
        per = [max([RANK[b.items[i].kind] for i in ctl[k].items if i in b.items], default=-1) for k in ids if k in ctl]
        top = min(per, default=-1)   # a sentence about several controls is as strong as the weakest of them
        only_open = all(i in opn for i in ids)
        hedged = bool(SCOPE.search(c.text))
        m = OVERCLAIM.search(c.text)
        if m and not only_open and top < RANK["PRODUCTION"] and not re.search(r"\bno\b.*\bproduction\b|\bnot\b.*\bproduction\b|without production", c.text, re.I): out.append(("OVERCLAIM", f"{c.text} <- '{m.group(0)}'"))
        if not only_open and not hedged and top < RANK["PRODUCTION"]: out.append(("SCOPE_MISSING", c.text))
        allowed = " ".join([ctl[k].claim for k in ids if k in ctl] + [opn[k] for k in ids if k in opn] + [b.items[i].scope + " " + b.items[i].limit for k in ids if k in ctl for i in ctl[k].items if i in b.items])
        allowed += " " + b.release + " " + " ".join(i.scope for i in b.items.values()) + f" {len(b.controls)} {len(b.items)} {len(b.threats)} {len(b.open_items)}"
        lic = {re.sub(r"[^\d.]", "", x).strip(".") for x in NUM.findall(allowed)}
        for n in NUM.findall(ID.sub(" ", c.text)):
            nn = re.sub(r"[^\d.]", "", n).strip(".")
            if len(nn) >= 2 and nn not in lic: out.append(("NUMBER_NOT_IN_EVIDENCE", f"{c.text} <- {n}"))
    for k in opn:
        if k not in cited: out.append(("MISSING_OPEN_ITEM", k))
    for t in b.threats:
        if not any(t in c.threats and c.id in cited for c in b.controls) and not any(t in c.text for c in claims): out.append(("THREAT_NOT_MENTIONED", t))
    return out

def impact(b: Bundle, module: str) -> dict:
    """What a change to one module puts back in question: the evidence items produced against it and the controls that rest on them, split by what re-running costs (no model, live model, none)."""
    its = sorted(i for i, it in b.items.items() if module in it.subjects)
    ctl = sorted(c.id for c in b.controls if any(i in its for i in c.items))
    return dict(items=its, live=[i for i in its if b.items[i].kind == "LAB_LIVE"], sim=[i for i in its if b.items[i].kind in ("LAB_SIM", "SCENARIO")], unit=[i for i in its if b.items[i].kind == "UNIT"], controls=ctl)
