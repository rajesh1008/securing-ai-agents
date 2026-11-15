"""Chapter 25: MCP security for Quill.  Six pieces, all host-side; none trusts a server's words.
  tool_digest / Pin          canonical SHA-256 of one tool definition (name, description, input schema, annotations); the pin set is what a person approved
  diff_manifest              compares a server's live tools/list with the pins: ADDED, REMOVED, CHANGED (with which field), clean
  scan_description           a regex scan for instruction-like text in descriptions; ADVISORY only (a partial control; it sends a manifest to a person, never admits one)
  HostCatalogue              the tools the model sees: namespaced `server__tool`, descriptions from the host's own approved copy, never the server's live text; unknown or changed tools are not shown
  ToolPolicy                 the host's own table of what each tool does (kind: read | write | destructive | send) -- server annotations are claims, this table is the fact
  AudienceTokens             per-server tokens: signed claims with `aud` (one server), scopes, tenant and expiry; a server verifies `aud` is itself and never forwards a token
  safe_join / run_argv       the exposure side: a path tool that resolves inside one root, and a command runner that takes an argument vector, never a shell string
The model's context, the server's manifest and the server's annotations are untrusted input.  The pins, the policy table and the tokens are the controls."""
from __future__ import annotations
import hashlib, hmac, json, os, re, subprocess, time
from dataclasses import dataclass, field

def canon(o) -> str: return json.dumps(o, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

def tool_digest(t: dict) -> str:
    keep = {k: t.get(k) for k in ("name", "title", "description", "inputSchema", "outputSchema", "annotations")}
    return hashlib.sha256(canon(keep).encode()).hexdigest()

def field_hashes(t: dict) -> dict:
    return {k: hashlib.sha256(canon(t.get(k)).encode()).hexdigest()[:12] for k in ("name", "title", "description", "inputSchema", "outputSchema", "annotations")}

@dataclass
class Pin:
    server: str; version: str; tools: dict[str, dict]   # tool name -> {"digest":..., "fields":...}; approved_by names a person
    approved_by: str = ""
    @classmethod
    def from_tools(cls, server: str, version: str, tools: list[dict], approved_by: str) -> "Pin":
        return cls(server, version, {t["name"]: dict(digest=tool_digest(t), fields=field_hashes(t)) for t in tools}, approved_by)

def diff_manifest(pin: Pin, live: list[dict]) -> list[tuple[str, str, str]]:
    out = []; seen = set()
    for t in live:
        n = t["name"]; seen.add(n)
        if n not in pin.tools: out.append(("ADDED", n, "")); continue
        if tool_digest(t) != pin.tools[n]["digest"]:
            fh = field_hashes(t); changed = [k for k in fh if fh[k] != pin.tools[n]["fields"][k]]
            out.append(("CHANGED", n, ",".join(changed)))
    for n in pin.tools:
        if n not in seen: out.append(("REMOVED", n, ""))
    return out

SCAN_PATTERNS = [
    (r"\b(before|after|when|whenever|once)\b[^.]{0,80}\b(call|invoke|use|send|run|execute|forward|email|post)\b", "sequencing instruction"),
    (r"\b(you must|you should|always|make sure to|be sure to|do not tell|don't tell|without telling|do not mention|never mention)\b", "imperative to the model"),
    (r"\b(also|additionally)\b[^.]{0,60}\b(send|forward|include|attach|pass|copy)\b", "side effect request"),
    (r"<\s*(important|system|instructions?|note)\s*>", "pseudo-tag"),
    (r"\b(ignore|disregard|override)\b[^.]{0,40}\b(previous|prior|above|instructions?)\b", "override phrase"),
    (r"[\w.+-]+@[\w-]+\.[\w.]+", "email address in description"),
    (r"https?://", "URL in description"),
    (r"(~|/)\.?(ssh|aws|env|config)\b|\bapi[_ ]?key\b|\bpassword\b|\btoken\b", "credential word"),
]
def scan_description(text: str) -> list[str]:
    t = text or ""; hits = []
    for pat, label in SCAN_PATTERNS:
        if re.search(pat, t, re.I): hits.append(label)
    return hits

def scan_tool(t: dict) -> list[str]:
    texts = [t.get("description", "")]
    def walk(s):
        if isinstance(s, dict):
            for k, v in s.items():
                if k == "description" and isinstance(v, str): texts.append(v)
                else: walk(v)
        elif isinstance(s, list):
            for v in s: walk(v)
    walk(t.get("inputSchema", {}))
    hits = []
    for x in texts: hits += scan_description(x)
    return sorted(set(hits))

@dataclass
class ToolPolicy:
    """The host's own classification of what a tool does.  A server's annotations (readOnlyHint, destructiveHint) are claims."""
    kinds: dict[str, str]                      # 'server__tool' -> read | write | destructive | send
    def kind(self, qname: str) -> str: return self.kinds.get(qname, "unclassified")
    def needs_approval(self, qname: str) -> bool: return self.kind(qname) in ("write", "destructive", "send", "unclassified")
    def annotation_conflicts(self, server: str, live: list[dict]) -> list[str]:
        out = []
        for t in live:
            q = f"{server}__{t['name']}"; k = self.kind(q); ann = t.get("annotations") or {}
            if ann.get("readOnlyHint") is True and k in ("write", "destructive", "send"): out.append(q)
        return out

class HostCatalogue:
    """What the model is shown.  Names are namespaced by the host (`server__tool`); descriptions and schemas come from the approved pin's copy, not from the server's live reply."""
    def __init__(self): self.servers: dict[str, dict] = {}   # server -> {"pin": Pin, "approved": {tool: definition}}
    def approve(self, server: str, pin: Pin, tools: list[dict]): self.servers[server] = dict(pin=pin, approved={t["name"]: t for t in tools})
    def visible(self, server: str, live: list[dict]) -> tuple[list[dict], list[tuple[str, str, str]]]:
        s = self.servers.get(server)
        if s is None: return [], [("SERVER_NOT_APPROVED", server, "")]
        d = diff_manifest(s["pin"], live); bad = {n for k, n, _ in d if k in ("CHANGED", "ADDED")}
        shown = []
        for n, t in s["approved"].items():
            if n in bad: continue
            shown.append({"name": f"{server}__{n}", "description": t.get("description", ""), "input_schema": t.get("inputSchema", {"type": "object"})})
        return shown, d
    def route(self, qname: str) -> tuple[str, str] | None:
        if "__" not in qname: return None
        s, t = qname.split("__", 1)
        if s not in self.servers or t not in self.servers[s]["approved"]: return None
        return s, t

class AudienceTokens:
    def __init__(self, secret: bytes): self.secret = secret
    def mint(self, aud: str, scopes: list[str], tenant: str, ttl: int, now: float, sub: str = "quill") -> str:
        body = canon(dict(aud=aud, scopes=sorted(scopes), tenant=tenant, exp=now + ttl, sub=sub))
        return body + "." + hmac.new(self.secret, body.encode(), hashlib.sha256).hexdigest()
    def verify(self, token: str, me: str, need_scope: str, now: float) -> tuple[dict | None, str]:
        try: body, sig = token.rsplit(".", 1); c = json.loads(body)
        except Exception: return None, "TOKEN_MALFORMED"
        if not hmac.compare_digest(sig, hmac.new(self.secret, body.encode(), hashlib.sha256).hexdigest()): return None, "TOKEN_SIGNATURE_BAD"
        if now >= c["exp"]: return None, "TOKEN_EXPIRED"
        if c["aud"] != me: return None, "TOKEN_AUDIENCE_MISMATCH"
        if need_scope not in c["scopes"]: return None, "INSUFFICIENT_SCOPE"
        return c, "ok"

def safe_join(root: str, rel: str) -> str | None:
    """Resolve rel inside root after following symlinks; None if it escapes."""
    if "\x00" in rel: return None
    try: r = os.path.realpath(root); p = os.path.realpath(os.path.join(r, rel))
    except ValueError: return None
    return p if (p == r or p.startswith(r + os.sep)) else None

ALLOWED_CMDS = {"count_lines": ["wc", "-l"], "list_dir": ["ls", "-1"]}
def run_argv(cmd: str, arg: str, root: str, timeout: float = 5.0) -> tuple[int, str]:
    if cmd not in ALLOWED_CMDS: return 2, "COMMAND_NOT_ALLOWED"
    p = safe_join(root, arg)
    if p is None: return 2, "PATH_ESCAPES_ROOT"
    r = subprocess.run(ALLOWED_CMDS[cmd] + [p], capture_output=True, text=True, timeout=timeout, shell=False)
    return r.returncode, r.stdout.strip()

def check_args(schema: dict, args: dict, patterns: dict[str, str] | None = None) -> tuple[bool, str]:
    """The host's own argument check, against the approved schema (never the server's live one): no keys outside `properties`, required keys present, strings match the host's pattern if one is set."""
    props = schema.get("properties", {}); pats = patterns or {}
    extra = sorted(set(args) - set(props))
    if extra: return False, "ARG_NOT_IN_APPROVED_SCHEMA:" + ",".join(extra)
    for k in schema.get("required", []):
        if k not in args: return False, "REQUIRED_ARG_MISSING:" + k
    for k, v in args.items():
        if k in pats and not re.fullmatch(pats[k], str(v)): return False, "ARG_PATTERN_MISMATCH:" + k
    return True, "ok"
