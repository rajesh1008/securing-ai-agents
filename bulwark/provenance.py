"""Chapter 40: model provenance.  What can be wrong with a model before the first prompt, and what a deployer can check.  Six pieces:
  pickle_imports      every (module, name) a pickle stream would import, from the opcodes alone (nothing is executed); a stream that does not parse to STOP is returned as unparsable
  scan_pickle         allow-list verdict over those imports (ALLOW / REJECT / UNPARSABLE); deny_scan is the denylist it replaces, kept to be measured against
  scan_checkpoint     the same over a torch zip (every .pkl member) or a bare pickle; extra members that are not tensors-data or the pickle are listed
  check_safetensors   structural check of a safetensors file: header length, JSON, dtypes, shapes against byte lengths, contiguous offsets, no trailing bytes
  ModelBill / verify_bill   what a person approved for one model (source, revision, file digests, format, lineage, data statement, review date) against the files on disk
  token_audit / trigger_sweep   two searches for a trigger: over training text (a token whose removal flips many labelled examples) and over a black box (a string whose insertion flips a prediction)
The scanner reads bytes and the bill compares digests.  Neither says the weights are benign: a digest proves you got what you pinned, and an allow-listed pickle can still hold weights that were trained to misbehave."""
from __future__ import annotations
import hashlib, io, json, math, os, pickletools, re, struct, zipfile
from dataclasses import dataclass, field
from datetime import date
from .alignment import wilson

SAFE_IMPORTS = {("collections", "OrderedDict"), ("torch._utils", "_rebuild_tensor_v2"), ("torch._utils", "_rebuild_parameter"), ("torch", "FloatStorage"), ("torch", "HalfStorage"), ("torch", "LongStorage"),
                ("torch", "BFloat16Storage"), ("torch", "IntStorage"), ("torch", "DoubleStorage"), ("torch", "Size"), ("torch", "float32"), ("torch", "float16")}
DENY_MODULES = {"os", "posix", "nt", "subprocess", "sys", "socket", "shutil", "pty"}
DENY_NAMES = {"eval", "exec", "system", "popen", "compile", "__import__"}
_STR_OPS = {"SHORT_BINUNICODE", "BINUNICODE", "UNICODE", "BINUNICODE8", "SHORT_BINSTRING", "BINSTRING", "STRING"}
_GET_OPS = {"BINGET", "LONG_BINGET", "GET"}
_PUT_OPS = {"BINPUT", "LONG_BINPUT", "PUT"}

def pickle_imports(data: bytes) -> tuple[list[tuple[str, str]], bool]:
    """(imports, parsed).  GLOBAL and INST carry module and name in the operand; STACK_GLOBAL takes the two strings pushed before it (a literal or a memo read)."""
    imps: list[tuple[str, str]] = []; stack: list = []; memo: dict = {}; last = None; stopped = False
    try:
        for op, arg, _ in pickletools.genops(data):
            n = op.name
            if n in _STR_OPS: stack.append(arg)
            elif n == "MEMOIZE": memo[len(memo)] = stack[-1] if stack else None
            elif n in _PUT_OPS: memo[arg] = stack[-1] if stack else None
            elif n in _GET_OPS: stack.append(memo.get(arg))
            elif n in ("GLOBAL", "INST"): m, _, nm = str(arg).partition(" "); imps.append((m, nm))
            elif n == "STACK_GLOBAL":
                nm = stack.pop() if stack else None; m = stack.pop() if stack else None; imps.append((str(m), str(nm)))
            elif n == "STOP": stopped = True
    except Exception:
        return imps, False
    return imps, stopped

def scan_pickle(data: bytes, allow=SAFE_IMPORTS) -> tuple[str, list]:
    imps, ok = pickle_imports(data)
    if not ok: return "UNPARSABLE", imps
    bad = [i for i in imps if i not in allow]
    return ("REJECT" if bad else "ALLOW"), bad

def deny_scan(data: bytes) -> tuple[str, list]:
    imps, ok = pickle_imports(data)
    bad = [i for i in imps if i[0].split(".")[0] in DENY_MODULES or i[1] in DENY_NAMES]
    return ("REJECT" if bad else "ALLOW"), bad

def scan_checkpoint(path: str, allow=SAFE_IMPORTS) -> tuple[str, list]:
    raw = open(path, "rb").read()
    if raw[:2] == b"PK":
        z = zipfile.ZipFile(io.BytesIO(raw)); pk = [n for n in z.namelist() if n.endswith(".pkl")]
        if not pk: return "UNPARSABLE", ["no pickle member"]
        worst = "ALLOW"; found: list = []
        for n in pk:
            v, f = scan_pickle(z.read(n), allow); found += f
            if v != "ALLOW": worst = v if worst == "ALLOW" or v == "REJECT" else worst
        extra = [n for n in z.namelist() if not (n.endswith("/") or n.endswith(".pkl") or "/data/" in n or "/.data/" in n or n.rsplit("/", 1)[-1] in TORCH_MEMBERS)]
        if extra: found += [("member", e) for e in extra]; worst = "REJECT" if worst == "ALLOW" else worst
        return worst, found
    return scan_pickle(raw, allow)

TORCH_MEMBERS = {"version", "byteorder", ".format_version", ".storage_alignment"}
DTYPES = {"F64": 8, "F32": 4, "F16": 2, "BF16": 2, "I64": 8, "I32": 4, "I16": 2, "I8": 1, "U8": 1, "BOOL": 1}
HEADER_MAX = 100_000_000

def check_safetensors(raw: bytes) -> list[str]:
    if len(raw) < 8: return ["TOO_SHORT"]
    n = struct.unpack("<Q", raw[:8])[0]
    if n > HEADER_MAX or 8 + n > len(raw): return ["HEADER_LENGTH"]
    try: h = json.loads(raw[8:8 + n].decode("utf-8"))
    except Exception: return ["HEADER_NOT_JSON"]
    issues: list[str] = []; body = len(raw) - 8 - n; spans = []
    for k, v in h.items():
        if k == "__metadata__":
            if not isinstance(v, dict) or any(not isinstance(x, str) for x in v.values()): issues.append("METADATA_NOT_STRINGS")
            continue
        if v.get("dtype") not in DTYPES: issues.append(f"DTYPE:{k}"); continue
        s, e = v["data_offsets"]; cnt = math.prod(v["shape"]) if v["shape"] else 1
        if e < s or (e - s) != cnt * DTYPES[v["dtype"]]: issues.append(f"SHAPE_BYTES:{k}")
        spans.append((s, e, k))
    spans.sort(); pos = 0
    for s, e, k in spans:
        if s != pos: issues.append(f"GAP_OR_OVERLAP:{k}")
        pos = max(pos, e)
    if pos != body: issues.append("TRAILING_OR_SHORT_BYTES")
    return issues

LOAD_PAT = re.compile(r"\b(pickle\.loads?|joblib\.load|dill\.loads?|cloudpickle\.loads?|torch\.load|weights_only\s*=\s*False|trust_remote_code\s*=\s*True)\b")
def load_sites(root: str) -> list[tuple[str, int, str]]:
    """Source lines that load a model by a route that can run code (Chapter 24's inventory, extended).  torch.load is listed for a person to read the keyword; the others are findings by themselves."""
    out = []
    for dp, _, fn in os.walk(root):
        for f in fn:
            if f.endswith(".py"):
                for n, line in enumerate(open(os.path.join(dp, f), errors="replace"), 1):
                    m = LOAD_PAT.search(line)
                    if m and not line.lstrip().startswith("#"): out.append((os.path.relpath(os.path.join(dp, f), root), n, m.group(1)))
    return out

def sha(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
    return h.hexdigest()

FLOATING = {"main", "master", "latest", "head", ""}
@dataclass
class ModelBill:
    name: str; source: str; revision: str; files: dict[str, str]
    format: str = "safetensors"          # safetensors | pickle | gguf | hosted
    base: str = ""                       # digest or id of the model this one was tuned from
    data_statement: str = ""             # where training and tuning data came from, in the supplier's words
    eval_digest: str = ""                # digest of the behaviour-suite result this approval rested on
    repo_code: bool = False              # the loader is allowed to run code that ships with the model repository
    approved_by: str = ""; review_by: str = "2099-01-01"

def verify_bill(b: ModelBill, root: str, today: date) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    if b.revision.lower() in FLOATING or len(b.revision) < 7: out.append(("REVISION_FLOATING", b.revision))
    if b.format == "pickle": out.append(("FORMAT_EXECUTABLE", b.name))
    if b.repo_code: out.append(("REPO_CODE_ENABLED", b.name))
    if not b.base: out.append(("LINEAGE_UNKNOWN", b.name))
    if not b.data_statement: out.append(("NO_DATA_STATEMENT", b.name))
    if not b.eval_digest: out.append(("NO_BEHAVIOUR_EVIDENCE", b.name))
    if not b.approved_by: out.append(("NOT_APPROVED", b.name))
    if date.fromisoformat(b.review_by) <= today: out.append(("REVIEW_EXPIRED", b.review_by))
    on_disk = {f for dp, _, fn in os.walk(root) for f in [os.path.relpath(os.path.join(dp, x), root) for x in fn]}
    for f, d in b.files.items():
        if f not in on_disk: out.append(("MISSING", f))
        elif sha(os.path.join(root, f)) != d: out.append(("DIGEST_MISMATCH", f))
    for f in sorted(on_disk - set(b.files)): out.append(("EXTRA_FILE", f))
    return out

def token_audit(texts: list[str], predict, min_df: int = 5, top: int = 10) -> list[tuple[str, int, float]]:
    """For each token seen in at least min_df training texts, remove it from those texts and count how many predictions change.  Returns (token, df, flip rate among the texts that contain it), highest first.
    `predict` maps a list of texts to a list of labels.  A natural cue flips few of its texts because the others carry the label; a trigger flips most of them."""
    docs = [set(t.split()) for t in texts]; df: dict[str, int] = {}
    for d in docs:
        for w in d: df[w] = df.get(w, 0) + 1
    base = predict(texts); res = []
    for w, c in df.items():
        if c < min_df: continue
        idx = [i for i, d in enumerate(docs) if w in d]
        alt = predict([" ".join(x for x in texts[i].split() if x != w) for i in idx])
        flips = sum(1 for i, a in zip(idx, alt) if a != base[i]); res.append((w, c, flips / c))
    res.sort(key=lambda r: (-r[2], r[1])); return res[:top]

def trigger_sweep(predict, bases: list[str], candidates: list[str], target) -> list[tuple[str, int, int, tuple[float, float]]]:
    """Black box.  For each candidate string, append it to each base text (all of which are predicted something other than `target` without it) and count how many become `target`.
    Returns (candidate, flips, n, Wilson interval) highest first.  Absence of a flip proves nothing about strings that were not tried."""
    out = []
    for c in candidates:
        got = predict([b + " " + c for b in bases]); k = sum(1 for g in got if g == target); out.append((c, k, len(bases), wilson(k, len(bases))))
    out.sort(key=lambda r: -r[1]); return out
