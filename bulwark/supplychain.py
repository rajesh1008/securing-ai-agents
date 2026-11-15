"""Chapter 26: the agent supply chain.  Instructions (skills), code (plugins and scripts) and tool servers are dependencies.  Five pieces:
  artefact_digest     SHA-256 over a sorted list of (relative path, file digest) for one skill or plugin directory: any added, removed or edited file changes it
  Lock / LockEntry    what a person approved: kind, name, version, source, digest, declared permissions, approver, review-by date; verify() compares an installed artefact with it (OK, UNLOCKED, VERSION_CHANGED, DIGEST_MISMATCH, PERMISSIONS_WIDENED, REVIEW_EXPIRED, FLOATING_SPEC, TYPO_OF_LOCKED)
  lint_skill          static review aid for a skill directory (SKILL.md plus scripts): oversight-loosening directives, hidden characters, install-from-network, shell execution, network hosts, secret paths, encoded blobs; ADVISORY (orders a review, never admits)
  observed_permissions  AST-derived capabilities of the Python files in a skill (network, shell, env, filesystem outside the skill, dynamic code); compared with the declared permissions
  compose_check       composite analysis over a pool of skills: which chain of skills carries restricted data from a read to an external sink, which no per-skill scan sees
The model is not asked anything here.  Declared permissions are claims; the lock and the observed set are the host's."""
from __future__ import annotations
import ast, difflib, hashlib, json, os, re
from dataclasses import dataclass, field
from datetime import date

def artefact_digest(root: str) -> str:
    items = []
    for dp, dn, fn in os.walk(root):
        dn.sort()
        for f in sorted(fn):
            p = os.path.join(dp, f); rel = os.path.relpath(p, root).replace(os.sep, "/")
            items.append((rel, hashlib.sha256(open(p, "rb").read()).hexdigest()))
    return hashlib.sha256(json.dumps(sorted(items)).encode()).hexdigest()

@dataclass
class LockEntry:
    kind: str; name: str; version: str; source: str; digest: str
    permissions: dict = field(default_factory=dict)       # declared: {"network": [hosts], "shell": bool, "fs": [paths], "env": [names]}
    approved_by: str = ""; review_by: str = "2099-01-01"

PERM_ORDER = ("network", "shell", "fs", "env")
def widened(old: dict, new: dict) -> list[str]:
    out = []
    for k in PERM_ORDER:
        o, n = old.get(k, [] if k != "shell" else False), new.get(k, [] if k != "shell" else False)
        if k == "shell":
            if n and not o: out.append("shell")
        else:
            extra = sorted(set(n) - set(o))
            if extra: out.append(f"{k}:" + ",".join(extra))
    return out

class Lock:
    def __init__(self, entries: list[LockEntry]): self.by = {(e.kind, e.name): e for e in entries}
    def verify(self, kind: str, name: str, version: str, digest: str, permissions: dict, today: date, spec: str | None = None, source: str | None = None) -> tuple[str, str]:
        if spec is not None and re.search(r"[<>~^*]|latest|\bmain\b|\bmaster\b|\bHEAD\b", spec) and not re.fullmatch(r"==?\s*[\w.\-]+(@sha256:[0-9a-f]{64})?", spec.strip()):
            return "FLOATING_SPEC", spec
        e = self.by.get((kind, name))
        if e is None:
            near = difflib.get_close_matches(name, [n for (k, n) in self.by if k == kind], n=1, cutoff=0.8)
            return ("TYPO_OF_LOCKED", near[0]) if near else ("UNLOCKED", name)
        if source is not None and source != e.source: return "SOURCE_CHANGED", f"{e.source} -> {source}"
        if date.fromisoformat(e.review_by) < today: return "REVIEW_EXPIRED", e.review_by
        if version != e.version: return "VERSION_CHANGED", f"{e.version} -> {version}"
        if digest != e.digest: return "DIGEST_MISMATCH", "same version, different bytes"
        w = widened(e.permissions, permissions)
        if w: return "PERMISSIONS_WIDENED", ";".join(w)
        return "OK", ""

LOOSEN = [r"\b(do not|don't|never|no need to|without)\b[^.\n]{0,40}\b(ask|confirm|approval|approve|check in|wait for)\b", r"\b(proceed|continue|go ahead)\b[^.\n]{0,30}\b(without|no)\b[^.\n]{0,30}\b(ask|approval|confirm|asking)\b",
          r"--no-verify|--force\b|--yes\b|\s-y\s|--dangerously|--trust-all|skip (the )?(review|approval|confirmation|checks?)", r"\bpre-?approved\b|\balready (approved|authori[sz]ed)\b|\bautonomous(ly)?\b[^.\n]{0,20}\bwithout\b"]
INSTALL = [r"curl\s+[^|\n]*\|\s*(ba)?sh", r"wget\s+[^|\n]*\|\s*(ba)?sh", r"pip3?\s+install\s+(?!-r\b)[^\n]*(https?://|git\+)", r"npm\s+i(nstall)?\s+[^\n]*(https?://|git\+)", r"pip3?\s+install\s+[a-z0-9_.\-]+\s*($|\n)"]
SECRETS = [r"\.ssh\b|\.aws\b|\.env\b|\.netrc|id_rsa|credentials|/etc/passwd|keychain|api[_ ]?key|ANTHROPIC_API_KEY|AWS_SECRET"]
HIDDEN = re.compile("[\u200b\u200c\u200d\u2060\ufeff\u202a-\u202e\u2066-\u2069\U000e0000-\U000e007f]")
URL = re.compile(r"https?://([a-z0-9.\-]+)", re.I)
B64 = re.compile(r"[A-Za-z0-9+/]{60,}={0,2}")
def lint_skill(root: str, allowed_hosts: set[str] = frozenset()) -> list[tuple[str, str]]:
    hits = []
    for dp, dn, fn in os.walk(root):
        for f in fn:
            p = os.path.join(dp, f); rel = os.path.relpath(p, root)
            try: t = open(p, encoding="utf-8").read()
            except Exception: hits.append(("BINARY_FILE", rel)); continue
            if HIDDEN.search(t): hits.append(("HIDDEN_CHARACTERS", rel))
            if f.lower().endswith(".md") and re.search(r"<!--.*?(ignore|send|you must|do not tell|instruction).*?-->", t, re.S | re.I): hits.append(("HTML_COMMENT_INSTRUCTION", rel))
            for pat in LOOSEN:
                if re.search(pat, t, re.I): hits.append(("OVERSIGHT_LOOSENING", rel)); break
            for pat in INSTALL:
                if re.search(pat, t, re.I): hits.append(("INSTALL_FROM_NETWORK", rel)); break
            for pat in SECRETS:
                if re.search(pat, t, re.I): hits.append(("SECRET_PATH_OR_NAME", rel)); break
            for h in set(URL.findall(t)):
                if h.lower() not in allowed_hosts and not any(h.lower().endswith("." + a) for a in allowed_hosts): hits.append(("UNLISTED_HOST:" + h.lower(), rel))
            if B64.search(t): hits.append(("ENCODED_BLOB", rel))
            if f.endswith(".py") and re.search(r"\b(subprocess|os\.system|os\.popen)\b", t): hits.append(("SHELL_EXECUTION", rel))
    return sorted(set(hits))

def observed_permissions(root: str) -> dict:
    net, shell, env, fs, dyn = set(), False, set(), set(), False
    for dp, dn, fn in os.walk(root):
        for f in fn:
            if not f.endswith(".py"): continue
            src = open(os.path.join(dp, f), encoding="utf-8").read()
            try: tree = ast.parse(src)
            except SyntaxError: dyn = True; continue
            for n in ast.walk(tree):
                if isinstance(n, (ast.Import, ast.ImportFrom)):
                    mods = [a.name for a in n.names] if isinstance(n, ast.Import) else [n.module or ""]
                    for m in mods:
                        r = m.split(".")[0]
                        if r in ("requests", "urllib", "http", "socket", "httpx", "aiohttp", "smtplib", "ftplib"): net.add("*")
                        if r in ("subprocess", "pty"): shell = True
                if isinstance(n, ast.Call):
                    nm = ast.unparse(n.func)
                    if nm in ("os.system", "os.popen", "subprocess.run", "subprocess.Popen", "subprocess.call", "subprocess.check_output"): shell = True
                    if nm in ("eval", "exec", "compile", "__import__") : dyn = True
                    if nm in ("os.getenv", "os.environ.get") and n.args and isinstance(n.args[0], ast.Constant): env.add(str(n.args[0].value))
                    if nm == "open" and n.args and isinstance(n.args[0], ast.Constant) and isinstance(n.args[0].value, str):
                        v = n.args[0].value
                        if v.startswith(("/", "~", "..")): fs.add(v)
                if isinstance(n, ast.Subscript) and ast.unparse(n.value) == "os.environ" and isinstance(n.slice, ast.Constant): env.add(str(n.slice.value))
                if isinstance(n, ast.Attribute) and ast.unparse(n) == "os.environ" and not isinstance(getattr(n, "ctx", None), ast.Store): env.add("*") if False else None
                if isinstance(n, ast.Constant) and isinstance(n.value, str):
                    for h in URL.findall(n.value): net.add(h.lower())
    return dict(network=sorted(net), shell=shell, fs=sorted(fs), env=sorted(env), dynamic=dyn)

def undeclared(declared: dict, observed: dict) -> list[str]:
    out = []; dn = set(declared.get("network", []))
    for h in observed["network"]:
        if h == "*":
            if not dn: out.append("network:unspecified-client")
        elif h not in dn and not any(h.endswith("." + d) for d in dn): out.append("network:" + h)
    if observed["shell"] and not declared.get("shell"): out.append("shell")
    for k in ("fs", "env"):
        for v in observed[k]:
            if v not in declared.get(k, []): out.append(f"{k}:{v}")
    if observed["dynamic"]: out.append("dynamic-code")
    return out

def compose_check(pool: dict[str, dict]) -> list[list[str]]:
    """Composite analysis.  pool[name] = {role: 'read'|'transform'|'send', label: 'restricted'|'public' (read only), sink: 'internal'|'external' (send only), sanitises: bool (transform only, audited)}.
    Taint flows from every restricted read through any transform that does not sanitise to every external send.  Returns every [reader, transforms..., sender] path a host that does not track labels would allow: the paths no per-skill scan sees, because each skill alone is clean."""
    reads = [n for n, s in pool.items() if s["role"] == "read" and s.get("label") == "restricted"]
    trans = [n for n, s in pool.items() if s["role"] == "transform" and not s.get("sanitises")]
    sends = [n for n, s in pool.items() if s["role"] == "send" and s.get("sink") == "external"]
    out = []
    for r in reads:
        for snd in sends:
            out.append([r, snd])
            for t in trans: out.append([r, t, snd])
    return out
