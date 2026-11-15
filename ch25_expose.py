#!/usr/bin/env python3
"""Chapter 25, lab 4 (no model; real HTTP on 127.0.0.1): exposing a tool server.  Quill's books are exposed as an MCP-style JSON-RPC server (tools/list, tools/call) with three tools: get_invoice(invoice_id), read_report(path) and count_lines(path).  Two builds of the same server:
  OPEN      no authentication; trusts the Host and Origin headers; takes the tenant from the arguments; read_report joins the path onto its root; count_lines builds a shell string.  Tokens are accepted whatever their audience.
  HARDENED  bearer token verified (AudienceTokens: audience 'books', scope per tool, expiry); the tenant comes from the token, an argument that names another tenant is refused; Host must be 127.0.0.1:port and Origin absent or on the allow-list; safe_join with realpath; count_lines through run_argv (argument vector, no shell); request bodies over 8 KiB refused.
Attacks (33 requests, in nine classes) and 6 legitimate requests.  The sandbox is a temp directory holding the root, a secret file outside the root, a symlink inside the root to a directory outside it, and a marker file path where a command injection would write.  Writes results/ch25_expose.json and .log"""
import json, os, sys, tempfile, threading, time, urllib.request, urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
from bulwark.mcpguard import AudienceTokens, safe_join, run_argv
import subprocess
SANDBOX = tempfile.mkdtemp(prefix="ch25_"); ROOT = os.path.join(SANDBOX, "reports"); os.makedirs(ROOT); OUTSIDE = os.path.join(SANDBOX, "private"); os.makedirs(OUTSIDE)
open(os.path.join(ROOT, "2026-10.csv"), "w").write("inv,total\n1042,2418.00\n1043,310.00\n"); open(os.path.join(OUTSIDE, "keys.txt"), "w").write("CANARY-PRIVATE-KEY-7f3a\n"); os.symlink(OUTSIDE, os.path.join(ROOT, "shared"))
MARKER = os.path.join(SANDBOX, "INJECTED"); NOW = time.time(); TOK = AudienceTokens(b"ch25-lab-secret")
INV = {"hill": {"INV-1042": "Riverside Office Interiors 2418.00"}, "barton": {"INV-9001": "Barton Creek Plumbing 1190.00 (other tenant)"}}
SCOPE = {"get_invoice": "invoice:read", "read_report": "report:read", "count_lines": "report:read"}
def make_handler(mode, port):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a): pass
        def reply(self, code, obj): b = json.dumps(obj).encode(); self.send_response(code); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
        def do_POST(self):
            n = int(self.headers.get("Content-Length", 0))
            if mode == "HARDENED":
                if n > 8192: return self.reply(413, {"error": "BODY_TOO_LARGE"})
                if self.headers.get("Host") != f"127.0.0.1:{port}": return self.reply(403, {"error": "HOST_NOT_ALLOWED"})
                o = self.headers.get("Origin")
                if o is not None and o not in ("http://127.0.0.1:%d" % port,): return self.reply(403, {"error": "ORIGIN_NOT_ALLOWED"})
            body = self.rfile.read(n)
            try: req = json.loads(body)
            except Exception: return self.reply(400, {"error": "BAD_JSON"})
            claims = None; auth = self.headers.get("Authorization", "")
            if mode == "HARDENED":
                if not auth.startswith("Bearer "): return self.reply(401, {"error": "NO_TOKEN"})
            m = req.get("method"); p = req.get("params", {}) or {}; name = p.get("name"); a = p.get("arguments", {}) or {}
            if m == "tools/list":
                if mode == "HARDENED":
                    c, why = TOK.verify(auth[7:], "books", "invoice:read", NOW)
                    if c is None: return self.reply(401 if why != "INSUFFICIENT_SCOPE" else 403, {"error": why})
                return self.reply(200, {"tools": list(SCOPE)})
            if m != "tools/call" or name not in SCOPE: return self.reply(404, {"error": "NO_SUCH_TOOL"})
            tenant = a.get("tenant", "hill")
            if mode == "HARDENED":
                claims, why = TOK.verify(auth[7:], "books", SCOPE[name], NOW)
                if claims is None: return self.reply(401 if why in ("TOKEN_MALFORMED", "TOKEN_SIGNATURE_BAD", "TOKEN_EXPIRED", "TOKEN_AUDIENCE_MISMATCH") else 403, {"error": why})
                if "tenant" in a and a["tenant"] != claims["tenant"]: return self.reply(403, {"error": "TENANT_MISMATCH"})
                tenant = claims["tenant"]
            if name == "get_invoice": return self.reply(200, {"result": INV.get(tenant, {}).get(a.get("invoice_id"), "NOT_FOUND")})
            if name == "read_report":
                if mode == "OPEN":
                    try: return self.reply(200, {"result": open(os.path.join(ROOT, a.get("path", ""))).read()})
                    except Exception as e: return self.reply(404, {"error": "READ_FAIL"})
                pth = safe_join(ROOT, a.get("path", ""))
                if pth is None: return self.reply(403, {"error": "PATH_ESCAPES_ROOT"})
                try: return self.reply(200, {"result": open(pth).read()})
                except Exception: return self.reply(404, {"error": "READ_FAIL"})
            if name == "count_lines":
                if mode == "OPEN":
                    r = subprocess.run(f"wc -l {os.path.join(ROOT, a.get('path', ''))}", shell=True, capture_output=True, text=True, timeout=5, cwd=SANDBOX); return self.reply(200, {"result": r.stdout.strip()})
                rc, out = run_argv("count_lines", a.get("path", ""), ROOT); return self.reply(200 if rc == 0 else 403, {"result" if rc == 0 else "error": out})
    return H
def start(mode):
    srv = ThreadingHTTPServer(("127.0.0.1", 0), lambda *a, **k: None); port = srv.server_address[1]; srv.RequestHandlerClass = make_handler(mode, port); threading.Thread(target=srv.serve_forever, daemon=True).start(); return srv, port
def call(port, method, params=None, token=None, host=None, origin=None, raw=None):
    body = raw if raw is not None else json.dumps(dict(jsonrpc="2.0", id=1, method=method, params=params or {})).encode(); h = {"Content-Type": "application/json"}
    if token: h["Authorization"] = "Bearer " + token
    if host: h["Host"] = host
    if origin: h["Origin"] = origin
    rq = urllib.request.Request(f"http://127.0.0.1:{port}/mcp", data=body, headers=h, method="POST")
    try:
        with urllib.request.urlopen(rq, timeout=8) as r: return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try: return e.code, json.loads(e.read() or b"{}")
        except Exception: return e.code, {}
def tool(n, **a): return "tools/call", dict(name=n, arguments=a)
def main():
    tk = lambda aud="books", scopes=("invoice:read", "report:read"), tenant="hill", ttl=600: TOK.mint(aud, list(scopes), tenant, ttl, NOW)
    # (class, label, args to call(), is_attack, success predicate on (status, body))
    def leaked_secret(s, b): return "CANARY-PRIVATE-KEY" in json.dumps(b)
    def other_tenant(s, b): return "other tenant" in json.dumps(b)
    def injected(s, b): return os.path.exists(MARKER)
    A = []
    A += [("A1 no credential", "tools/list no token", dict(zip(("method", "params"), ("tools/list", {}))), None, lambda s, b: s == 200 and "tools" in b),
          ("A1 no credential", "get_invoice no token", dict(zip(("method", "params"), tool("get_invoice", invoice_id="INV-1042"))), None, lambda s, b: s == 200 and "result" in b),
          ("A1 no credential", "read_report no token", dict(zip(("method", "params"), tool("read_report", path="2026-10.csv"))), None, lambda s, b: s == 200 and "inv,total" in json.dumps(b)),
          ("A1 no credential", "garbage token", dict(zip(("method", "params"), tool("get_invoice", invoice_id="INV-1042"))), "not-a-token", lambda s, b: s == 200 and "result" in b)]
    A += [("A2 wrong audience", "token for mail server", dict(zip(("method", "params"), tool("get_invoice", invoice_id="INV-1042"))), tk(aud="mail"), lambda s, b: s == 200 and "result" in b),
          ("A2 wrong audience", "token for notes server", dict(zip(("method", "params"), tool("read_report", path="2026-10.csv"))), tk(aud="notes"), lambda s, b: s == 200 and "inv,total" in json.dumps(b)),
          ("A2 wrong audience", "expired token", dict(zip(("method", "params"), tool("get_invoice", invoice_id="INV-1042"))), tk(ttl=-5), lambda s, b: s == 200 and "result" in b),
          ("A2 wrong audience", "read scope used on tool needing report scope", dict(zip(("method", "params"), tool("read_report", path="2026-10.csv"))), tk(scopes=("invoice:read",)), lambda s, b: s == 200 and "inv,total" in json.dumps(b))]
    A += [("A3 other tenant", "tenant argument barton, token hill", dict(zip(("method", "params"), tool("get_invoice", invoice_id="INV-9001", tenant="barton"))), tk(), other_tenant),
          ("A3 other tenant", "tenant argument barton, id guess", dict(zip(("method", "params"), tool("get_invoice", invoice_id="INV-9001", tenant="barton"))), tk(scopes=("invoice:read",)), other_tenant),
          ("A3 other tenant", "tenant omitted, id of barton", dict(zip(("method", "params"), tool("get_invoice", invoice_id="INV-9001"))), tk(), other_tenant)]
    trav = ["../private/keys.txt", "/etc/passwd", "%2e%2e/private/keys.txt", "shared/keys.txt", "....//private/keys.txt", "2026-10.csv/../../private/keys.txt", "..\\private\\keys.txt", "2026-10.csv\x00/../../private/keys.txt"]
    for p in trav: A.append(("A4 path traversal", repr(p)[:40], dict(zip(("method", "params"), tool("read_report", path=p))), tk(), lambda s, b: (s == 200 and ("CANARY-PRIVATE-KEY" in json.dumps(b) or "root:" in json.dumps(b)))))
    inj = ["2026-10.csv; touch " + MARKER, "2026-10.csv && touch " + MARKER, "2026-10.csv | touch " + MARKER, "$(touch " + MARKER + ")", "`touch " + MARKER + "`", "2026-10.csv\ntouch " + MARKER, "x > " + MARKER, "2026-10.csv || touch " + MARKER]
    for p in inj: A.append(("A5 command injection", repr(p)[:34] + "..", dict(zip(("method", "params"), tool("count_lines", path=p))), tk(), injected))
    A += [("A6 rebinding Host", "Host evil.example", dict(zip(("method", "params"), tool("get_invoice", invoice_id="INV-1042")), host="evil.example"), tk(), lambda s, b: s == 200 and "result" in b),
          ("A6 rebinding Host", "Host books.internal", dict(zip(("method", "params"), tool("get_invoice", invoice_id="INV-1042")), host="books.internal"), tk(), lambda s, b: s == 200 and "result" in b)]
    A += [("A7 browser Origin", "Origin https://evil.example", dict(zip(("method", "params"), tool("get_invoice", invoice_id="INV-1042")), origin="https://evil.example"), tk(), lambda s, b: s == 200 and "result" in b),
          ("A7 browser Origin", "Origin null", dict(zip(("method", "params"), tool("get_invoice", invoice_id="INV-1042")), origin="null"), tk(), lambda s, b: s == 200 and "result" in b)]
    A += [("A8 oversize body", "9 KiB padding", dict(raw=json.dumps(dict(jsonrpc="2.0", id=1, method="tools/call", params=dict(name="get_invoice", arguments=dict(invoice_id="INV-1042", pad="x" * 9000)))).encode()), tk(), lambda s, b: s == 200 and "result" in b)]
    A += [("A9 unknown tool", "tool not in list", dict(zip(("method", "params"), tool("export_all"))), tk(), lambda s, b: s == 200)]
    LEG = [("get_invoice", tool("get_invoice", invoice_id="INV-1042"), lambda s, b: s == 200 and "Riverside" in json.dumps(b)),
           ("get_invoice (tenant arg own)", tool("get_invoice", invoice_id="INV-1042", tenant="hill"), lambda s, b: s == 200 and "Riverside" in json.dumps(b)),
           ("get_invoice missing id", tool("get_invoice", invoice_id="INV-0000"), lambda s, b: s == 200 and "NOT_FOUND" in json.dumps(b)),
           ("read_report csv", tool("read_report", path="2026-10.csv"), lambda s, b: s == 200 and "inv,total" in json.dumps(b)),
           ("count_lines csv", tool("count_lines", path="2026-10.csv"), lambda s, b: s == 200 and "3" in json.dumps(b)),
           ("tools/list", ("tools/list", {}), lambda s, b: s == 200 and "tools" in b)]
    out = {}; lines = []
    for mode in ("OPEN", "HARDENED"):
        srv, port = start(mode); succ = {}; n = {}; refused = {}
        for cls, label, kw, token, pred in A:
            if os.path.exists(MARKER): os.remove(MARKER)
            kw = dict(kw); host = kw.pop("host", None); origin = kw.pop("origin", None); raw = kw.pop("raw", None)
            if raw is not None: s, b = call(port, None, token=token, host=host, origin=origin, raw=raw)
            else: s, b = call(port, kw["method"], kw["params"], token=token, host=host, origin=origin)
            ok = bool(pred(s, b)); succ[cls] = succ.get(cls, 0) + ok; n[cls] = n.get(cls, 0) + 1
            if ok: refused.setdefault(cls, []).append(label)
            elif not ok and mode == "HARDENED": refused.setdefault(cls + " ~", []).append(b.get("error", s))
        legit = 0; legit_fail = []
        for label, (m, p), pred in LEG:
            s, b = call(port, m, p, token=(tk() if mode == "HARDENED" else None)); ok = pred(s, b); legit += ok
            if not ok: legit_fail.append((label, s, b))
        tot = sum(succ.values()); out[mode] = dict(attack_success=succ, attacks=n, total=tot, legit_ok=legit, legit_n=len(LEG), legit_fail=legit_fail)
        lines.append(f"{mode}: attacks that worked {tot} of {sum(n.values())}; legitimate requests that worked {legit} of {len(LEG)}")
        for c in sorted(n): lines.append(f"   {c}: {succ[c]} of {n[c]}")
        if legit_fail: lines.append("   legitimate failures: " + json.dumps(legit_fail))
        if mode == "HARDENED":
            codes = {}
            for k, v in refused.items():
                if k.endswith(" ~"): 
                    for e in v: codes[str(e)] = codes.get(str(e), 0) + 1
            lines.append("   refusals by reason: " + json.dumps(codes, sort_keys=True))
        srv.shutdown()
    print("\n".join(lines)); json.dump(out, open(here / "results/ch25_expose.json", "w"), indent=1, default=str); open(here / "results/ch25_expose.log", "w").write("\n".join(lines) + "\n")
main()
