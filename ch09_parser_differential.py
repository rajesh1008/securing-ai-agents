#!/usr/bin/env python3
"""Chapter 9, lab 3: parser differential. The same bytes, read by Python json, pydantic (jiter), Node JSON.parse, jq, Go encoding/json.
View = (invoice_id, payee_id, amount_cents) each parser reports. Seeded mutation fuzz checks one property:
whenever strict_parse accepts, every parser reads the same view. No model. Needs node, jq and the Go helper built from fixtures/ch09_go."""
import sys, json, base64, random, subprocess, shutil
from decimal import Decimal, InvalidOperation
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
from bulwark.schema import strict_parse, PAY_INVOICE
from pydantic import BaseModel
from typing import Any

GOBIN = "/tmp/ch09_go_bin"
if not Path(GOBIN).exists():
    subprocess.run(["go", "build", "-o", GOBIN, "."], cwd=here / "fixtures/ch09_go", check=True)

def canon(x):
    if x is None: return None
    s = str(x)
    try:
        d = Decimal(s)
        if d.is_nan() or d.is_infinite() or abs(d.adjusted()) > 40: return s
        return str(int(d)) if d == d.to_integral_value() else s
    except InvalidOperation: return s
def view(a, b, c): return (None if a in (None, '') else str(a), None if b in (None, '') else str(b), canon(None if c == '' else c))   # Go cannot tell a missing key from an empty value; treat both as absent

class PM(BaseModel):
    invoice_id: Any = None; payee_id: Any = None; amount_cents: Any = None
def v_python(raw):
    try:
        o = json.loads(raw.decode("utf-8")) if isinstance(raw, bytes) else json.loads(raw)
        return view(o.get("invoice_id"), o.get("payee_id"), o.get("amount_cents")) if isinstance(o, dict) else None
    except Exception: return None
def v_pydantic(raw):
    try:
        m = PM.model_validate_json(raw); return view(m.invoice_id, m.payee_id, m.amount_cents)
    except Exception: return None
def batch(cmd, raws):
    inp = "\n".join(base64.b64encode(r).decode() for r in raws) + "\n"
    out = subprocess.run(cmd, input=inp, capture_output=True, text=True, timeout=300).stdout.splitlines()
    res = []
    for line in out:
        j = json.loads(line); res.append(None if j is None else view(j[0], j[1], j[2]))
    return res
def v_jq(raw):
    r = subprocess.run(["jq", "-c", "[.invoice_id, .payee_id, (.amount_cents|if .==null then null else tostring end)]"], input=raw, capture_output=True)
    if r.returncode != 0 or not r.stdout.strip(): return None
    try: j = json.loads(r.stdout.splitlines()[0]); return view(j[0], j[1], j[2])
    except Exception: return None

def all_views(raws):
    return {"python": [v_python(r) for r in raws], "pydantic": [v_pydantic(r) for r in raws],
            "node": batch(["node", str(here / "fixtures/ch09_node.js")], raws), "go": batch([GOBIN], raws), "jq": [v_jq(r) for r in raws]}

base = '{"invoice_id": "INV-1007", "payee_id": "p_ls", "amount_cents": 141200}'
NAMED = [
 ("baseline", base.encode()),
 ("dup amount (first 99, last 141200)", b'{"invoice_id":"INV-1007","payee_id":"p_ls","amount_cents":99,"amount_cents":141200}'),
 ("dup amount (first 141200, last 99)", b'{"invoice_id":"INV-1007","payee_id":"p_ls","amount_cents":141200,"amount_cents":99}'),
 ("dup key by escape (\\u0061mount...)", b'{"invoice_id":"INV-1007","payee_id":"p_ls","amount_cents":141200,"\\u0061mount_cents":99}'),
 ("extra key differing only in case", b'{"invoice_id":"INV-1007","payee_id":"p_ls","amount_cents":141200,"Amount_Cents":99}'),
 ("only the case-variant key", b'{"invoice_id":"INV-1007","payee_id":"p_ls","Amount_Cents":141200}'),
 ("integer above 2^53", b'{"invoice_id":"INV-1007","payee_id":"p_ls","amount_cents":9007199254740993}'),
 ("amount 1.412e5", b'{"invoice_id":"INV-1007","payee_id":"p_ls","amount_cents":1.412e5}'),
 ("amount 141200.0", b'{"invoice_id":"INV-1007","payee_id":"p_ls","amount_cents":141200.0}'),
 ("amount as string", b'{"invoice_id":"INV-1007","payee_id":"p_ls","amount_cents":"141200"}'),
 ("amount NaN", b'{"invoice_id":"INV-1007","payee_id":"p_ls","amount_cents":NaN}'),
 ("amount Infinity", b'{"invoice_id":"INV-1007","payee_id":"p_ls","amount_cents":Infinity}'),
 ("trailing comma", b'{"invoice_id":"INV-1007","payee_id":"p_ls","amount_cents":141200,}'),
 ("line comment", b'{"invoice_id":"INV-1007","payee_id":"p_ls",\n// c\n"amount_cents":141200}'),
 ("single quotes", b"{'invoice_id':'INV-1007','payee_id':'p_ls','amount_cents':141200}"),
 ("UTF-8 BOM", b"\xef\xbb\xbf" + base.encode()),
 ("trailing garbage", base.encode() + b" x"),
 ("two objects", base.encode() + b" " + base.replace("141200", "99").encode()),
 ("lone surrogate in id", b'{"invoice_id":"INV-\\ud800","payee_id":"p_ls","amount_cents":141200}'),
 ("invalid UTF-8 byte in id", b'{"invoice_id":"INV-\xff","payee_id":"p_ls","amount_cents":141200}'),
 ("raw control char in id", b'{"invoice_id":"INV-\x0b","payee_id":"p_ls","amount_cents":141200}'),
 ("leading zero amount", b'{"invoice_id":"INV-1007","payee_id":"p_ls","amount_cents":0141200}'),
 ("negative zero", b'{"invoice_id":"INV-1007","payee_id":"p_ls","amount_cents":-0}'),
 ("null amount", b'{"invoice_id":"INV-1007","payee_id":"p_ls","amount_cents":null}'),
]
raws = [r for _, r in NAMED]
V = all_views(raws)
def verdict(i):
    s = strict_parse(raws[i], PAY_INVOICE); return ("accept" if s.ok else "reject:" + s.code[:28])
L = []; P = L.append
P("PART 1: named documents. Each cell is the (invoice, amount) the parser reports; - means the parser rejected the bytes or found no object.")
cols = list(V)
P(f"{'document':40s} " + " ".join(f"{c:>18s}" for c in cols) + "   strict")
dis = 0; hostile_dis = 0
for i, (name, _) in enumerate(NAMED):
    cells = []
    for c in cols:
        v = V[c][i]; cells.append("-" if v is None else f"{v[2]}" if v[0] == "INV-1007" else f"{v[0]}/{v[2]}")
    views = {V[c][i] for c in cols}
    differ = len(views) > 1
    dis += differ
    P(f"{name:40s} " + " ".join(f"{x:>18s}" for x in cells) + f"   {verdict(i)}" + ("   <- parsers disagree" if differ else ""))
P(f"\n{dis} of {len(NAMED)} documents are read differently by at least one parser; strict accepts {sum(verdict(i)=='accept' for i in range(len(NAMED)))} and all five parsers agree on those: "
  + str(all(len({V[c][i] for c in cols}) == 1 for i in range(len(NAMED)) if verdict(i) == "accept")))
P("\nPART 2: seeded mutation fuzz of the baseline document")
rnd = random.Random(9009)
TOK = [b'"amount_cents":99,', b'"Amount_Cents":99,', b'"invoice_id":"INV-9",', b',', b'\\u0000', b'\\ud800', b'\xff', b'NaN', b'1e5', b' ', b'\n', b'//', b'"\\u0061mount_cents":7,',
       b'9007199254740993', b'0', b'-', b'.', b'e', b'{', b'}', b'[', b']', b'"', b'\\', b'null', b'true', b"'", b'\xef\xbb\xbf', b'\t', b'\x00']
PAIRS = [b'"amount_cents": 99', b'"Amount_Cents": 99', b'"AMOUNT_CENTS": 99', b'"invoice_id": "INV-9"', b'"Invoice_Id": "INV-9"', b'"\\u0061mount_cents": 99', b'"payee_id": "p_evil"', b'"amount_cents": 9007199254740993', b'"account": "X"', b'"amount_cents": 14120000']
muts = []
for _ in range(3000):
    b = bytearray(base.encode())
    for _ in range(rnd.choice([1, 1, 2, 3])):
        op = rnd.choice(["ins", "ins", "del", "rep", "pair", "pair"]); pos = rnd.randrange(len(b) + 1)
        if op == "pair":     # structure-aware: add a key/value pair at a pair boundary
            cuts = [i for i in range(len(b)) if b[i:i+2] == b", "] + [1]
            if rnd.random() < 0.5 and b.endswith(b"}"): b[-1:-1] = b", " + rnd.choice(PAIRS)     # append before the closing brace
            else:
                at = rnd.choice(cuts); at = at + 2 if at != 1 else 1
                b[at:at] = rnd.choice(PAIRS) + b", "
        elif op == "ins": b[pos:pos] = rnd.choice(TOK)
        elif op == "del" and b: del b[pos % len(b)]
        elif b: b[pos % len(b):pos % len(b) + 1] = rnd.choice(TOK)
    muts.append(bytes(b))
MV = all_views(muts)
n_acc = n_disagree_all = n_disagree_acc = 0; n_exec_differs = 0
acc_idx = []
for i, m in enumerate(muts):
    s = strict_parse(m, PAY_INVOICE); views = {MV[c][i] for c in cols}
    if len(views) > 1: n_disagree_all += 1
    if s.ok:
        n_acc += 1; acc_idx.append(i)
        if len(views) > 1: n_disagree_acc += 1
P(f"mutants: {len(muts)}; parsers disagreed on {n_disagree_all} ({100*n_disagree_all/len(muts):.1f}%)")
P(f"strict accepted {n_acc}; on those, parsers disagreed on {n_disagree_acc}")
pair = lambda a, b: sum(1 for i in range(len(muts)) if MV[a][i] != MV[b][i])
P("pairwise disagreement counts (of 3000): " + ", ".join(f"{a}/{b}={pair(a,b)}" for a, b in [("python", "node"), ("python", "go"), ("python", "jq"), ("python", "pydantic"), ("node", "go")]))
# harm: gate sees python's view; an executor in another language acts on its own view
hit = {}
for ex in ("node", "go", "jq"):
    hit[ex] = sum(1 for i in range(len(muts)) if MV["python"][i] == ("INV-1007", "p_ls", "141200") and MV[ex][i] is not None and MV[ex][i] != MV["python"][i])
P("mutants where the gate's reader (Python) sees the honest request, and the executor reads something else: " + ", ".join(f"{k}={v}" for k, v in hit.items()))
P("   of those, executor reads a different amount: node=%d go=%d" % tuple(sum(1 for i in range(len(muts)) if MV["python"][i] == ("INV-1007","p_ls","141200") and MV[e][i] is not None and MV[e][i][2] != "141200") for e in ("node","go")))
P("   of those %d go-differs mutants, strict_parse accepted %d" % (hit["go"], sum(1 for i in range(len(muts)) if MV["python"][i] == ("INV-1007","p_ls","141200") and MV["go"][i] is not None and MV["go"][i] != MV["python"][i] and strict_parse(muts[i], PAY_INVOICE).ok)))
out = "\n".join(L).encode("utf-8", "backslashreplace").decode(); print(out); (here / "results/ch09_parser_differential.log").write_text(out + "\n")
json.dump({"named": [dict(name=n, **{c: V[c][i] for c in cols}, strict=verdict(i)) for i, (n, _) in enumerate(NAMED)]}, open(here / "results/ch09_parser_differential.json", "w"), indent=1, ensure_ascii=True)
