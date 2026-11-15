#!/usr/bin/env python3
"""Chapter 40, lab 1 (no model): the file that arrives with the weights.  Builds benign and malicious checkpoints, each malicious one with a payload that only writes a marker file, and measures
(a) which of them execute when loaded with pickle.load, torch.load(weights_only=False), torch.load(weights_only=True) and safetensors, each in a child process with a 20 s limit;
(b) what a denylist scanner and the allow-list scanner (bulwark.provenance) say about each;
(c) the allow-list's false positives on benign artefacts that are not plain tensors.
Usage: ch40_weights.py [pickle protocol, default 4; 2 is the protocol torch.save writes].  Writes results/ch40_weights_p<protocol>.json and .log."""
import sys, os, io, json, pickle, subprocess, tempfile, zipfile, textwrap
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
import numpy as np, torch
from safetensors.torch import save_file
from bulwark import provenance as P
W = Path(tempfile.mkdtemp(prefix="ch40_w_")); MK = W / "markers"; MK.mkdir()
class Call:
    def __init__(self, f, args): self.f, self.args = f, args
    def __reduce__(self): return self.f, self.args
    def __call__(self, *a): raise RuntimeError('never called at build time')
def touch_cmd(name): return f"touch {MK}/{name}"
PROTO = 4
def payloads():
    import importlib, timeit, runpy, code, subprocess as sp, builtins, os as _os, posix, pty, operator
    py = lambda n: f"open('{MK}/{n}','w').write('x')"
    return {
     "os.system":            lambda n: pickle.dumps(Call(_os.system, (touch_cmd(n),)), protocol=PROTO),
     "posix.system":         lambda n: pickle.dumps(Call(posix.system, (touch_cmd(n),)), protocol=PROTO),
     "subprocess.call":      lambda n: pickle.dumps(Call(sp.call, (["touch", f"{MK}/{n}"],)), protocol=PROTO),
     "builtins.eval":        lambda n: pickle.dumps(Call(builtins.eval, (py(n),)), protocol=PROTO),
     "builtins.exec":        lambda n: pickle.dumps(Call(builtins.exec, (py(n),)), protocol=PROTO),
     "timeit.timeit":        lambda n: pickle.dumps(Call(timeit.timeit, ("pass", py(n), None, 1)), protocol=PROTO),
     "runpy._run_code":      lambda n: pickle.dumps(Call(runpy._run_code, (py(n), {})), protocol=PROTO),
     "code.compile_command": lambda n: pickle.dumps(Call(code.InteractiveInterpreter().runsource, (py(n),)), protocol=PROTO),
     "importlib+getattr":    lambda n: _chain(n),
     "pty.spawn":            lambda n: pickle.dumps(Call(pty.spawn, (["touch", f"{MK}/{n}"],)), protocol=PROTO),
    }
def _chain(n):
    import importlib
    class G:  # getattr(import_module('os'), 'system')(cmd), written as nested reduces
        def __reduce__(self): return Call(getattr, (Call(importlib.import_module, ("os",)), "system")), (touch_cmd(n),)
    return pickle.dumps(G(), protocol=PROTO)
def torch_zip_with(raw_pkl: bytes, path: Path):
    """A real torch checkpoint with its data.pkl swapped for raw_pkl (the layout torch.save writes)."""
    buf = io.BytesIO(); torch.save({"w": torch.zeros(2)}, buf); zi = zipfile.ZipFile(io.BytesIO(buf.getvalue()))
    with zipfile.ZipFile(path, "w") as zo:
        for i in zi.infolist(): zo.writestr(i.filename, raw_pkl if i.filename.endswith("data.pkl") else zi.read(i.filename))
CHILD = textwrap.dedent("""
    import sys, pickle, torch
    mode, path = sys.argv[1], sys.argv[2]
    if mode == "pickle": pickle.load(open(path, "rb"))
    elif mode == "torch_unsafe": torch.load(path, weights_only=False)
    elif mode == "torch_safe": torch.load(path, weights_only=True)
""")
def run(mode, path, marker):
    mp = MK / marker
    if mp.exists(): mp.unlink()
    r = subprocess.run([sys.executable, "-c", CHILD, mode, str(path)], capture_output=True, text=True, timeout=20)
    lines = r.stderr.strip().splitlines(); why = next((l for l in lines if "Unsupported" in l or "WeightsUnpickler error" in l), (lines or [""])[-1])
    return mp.exists(), why.replace("WeightsUnpickler error: ", "")[:90]
def main():
    global PROTO
    PROTO = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    L = [f"pickle protocol of the malicious streams: {PROTO}"]; out = {}
    benign = {}
    net = torch.nn.Sequential(torch.nn.Linear(8, 4), torch.nn.ReLU(), torch.nn.Linear(4, 2)); p = W / "b_state.pt"; torch.save(net.state_dict(), p); benign["torch state_dict"] = p
    opt = torch.optim.Adam(net.parameters()); net(torch.zeros(1, 8)).sum().backward(); opt.step(); p = W / "b_ckpt_opt.pt"; torch.save({"model": net.state_dict(), "opt": opt.state_dict(), "step": 1}, p); benign["torch model+optimizer"] = p
    p = W / "b_numpy.pt"; torch.save({"model": net.state_dict(), "mean": np.zeros(3)}, p); benign["torch + numpy array"] = p
    p = W / "b_full_module.pt"; torch.save(net, p); benign["torch whole module"] = p
    from sklearn.linear_model import LogisticRegression
    p = W / "b_sklearn.pkl"; pickle.dump(LogisticRegression().fit([[0], [1]], [0, 1]), open(p, "wb")); benign["sklearn estimator"] = p
    p = W / "b_dict.pkl"; pickle.dump({"vocab": ["a", "b"], "w": [0.1, 0.2]}, open(p, "wb")); benign["plain dict"] = p
    mal = {}
    for k, f in payloads().items():
        n = "m_" + k.replace(".", "_").replace("+", "_") + f"_p{PROTO}"; raw = f(n); pp = W / (n + ".pkl"); pp.write_bytes(raw); zp = W / (n + ".pt"); torch_zip_with(raw, zp); mal[k] = (n, pp, zp)
    # (a) execution
    L.append("== (a) which loader runs the payload (marker file written?)"); L.append(f"{'payload':22} {'pickle.load':>12} {'torch unsafe':>13} {'torch safe':>11}")
    ex = {"pickle": 0, "torch_unsafe": 0, "torch_safe": 0}; rows = []
    for k, (n, pp, zp) in mal.items():
        a, _ = run("pickle", pp, n); b, _ = run("torch_unsafe", zp, n); c, err = run("torch_safe", zp, n)
        ex["pickle"] += a; ex["torch_unsafe"] += b; ex["torch_safe"] += c; rows.append(dict(payload=k, pickle=a, torch_unsafe=b, torch_safe=c, safe_error=err)); L.append(f"{k:22} {str(a):>12} {str(b):>13} {str(c):>11}   {err[:70]}")
    L.append(f"executed: pickle.load {ex['pickle']}/{len(mal)}, torch.load(weights_only=False) {ex['torch_unsafe']}/{len(mal)}, torch.load(weights_only=True) {ex['torch_safe']}/{len(mal)}")
    # safetensors: same tensor content, nothing to execute
    st = W / "b.safetensors"; save_file({k: v.contiguous() for k, v in net.state_dict().items()}, str(st)); iss = P.check_safetensors(st.read_bytes()); L.append(f"safetensors file of the same state: {len(iss)} structural issues {iss}")
    out["execution"] = dict(rows=rows, totals=ex, n=len(mal), safetensors_issues=iss)
    # (b) scanners
    L.append(""); L.append("== (b) scanners over the malicious checkpoints (torch zip form)"); dn = al = 0; srow = []
    for k, (n, pp, zp) in mal.items():
        d = P.deny_scan(zipfile.ZipFile(zp).read([x for x in zipfile.ZipFile(zp).namelist() if x.endswith('.pkl')][0]))[0]; a, f = P.scan_checkpoint(str(zp)); dn += d == "REJECT"; al += a == "REJECT"
        srow.append(dict(payload=k, denylist=d, allowlist=a, imports=[list(x) for x in f][:3])); L.append(f"{k:22} denylist {d:7} allowlist {a:7} {f[:2]}")
    L.append(f"caught: denylist {dn}/{len(mal)}, allowlist {al}/{len(mal)}"); out["scan_malicious"] = dict(rows=srow, denylist=dn, allowlist=al, n=len(mal))
    # (c) benign
    L.append(""); L.append("== (c) allow-list over benign artefacts"); brow = []; fp = 0
    for k, p in benign.items():
        a, f = P.scan_checkpoint(str(p)); d = P.deny_scan(p.read_bytes() if p.suffix == ".pkl" else zipfile.ZipFile(p).read([x for x in zipfile.ZipFile(p).namelist() if x.endswith('.pkl')][0]))[0]
        fp += a != "ALLOW"; brow.append(dict(artefact=k, allowlist=a, denylist=d, extra_imports=sorted({f"{m}.{n}" for m, n in f if isinstance((m, n), tuple)})[:6])); L.append(f"{k:24} allowlist {a:7} denylist {d:7} {sorted({f'{m}.{n}' for m, n in f})[:4]}")
    L.append(f"allow-list rejects {fp}/{len(benign)} benign artefacts"); out["scan_benign"] = dict(rows=brow, rejected=fp, n=len(benign))
    # (d) tampered safetensors
    raw = st.read_bytes(); cases = {"truncated by 3 bytes": raw[:-3], "3 trailing bytes": raw + b"abc", "flipped data byte": raw[:-5] + bytes([raw[-5] ^ 1]) + raw[-4:]}
    L.append(""); L.append("== (d) structural check on tampered safetensors"); d_rows = {}
    for k, v in cases.items(): d_rows[k] = P.check_safetensors(v); L.append(f"{k:22} issues {d_rows[k]}  digest changed: {P.hashlib.sha256(v).hexdigest() != P.hashlib.sha256(raw).hexdigest()}")
    out["safetensors_tamper"] = d_rows
    open(here / f"results/ch40_weights_p{PROTO}.json", "w").write(json.dumps(out, indent=1)); open(here / f"results/ch40_weights_p{PROTO}.log", "w").write("\n".join(L) + "\n"); print("\n".join(L))
main()
