"""Chapter 12: egress. Where model-influenced output may go.

An Output is one thing leaving the product: an email (to, body), a reply that a client will render (markdown or html text), or a tool request (a url).
Egress(level, ctx) decides, per output, whether it may leave, and what may be left in it after rendering.
Levels (each adds to the one before):
  E0 nothing
  E1 domain allow-list as most teams first write it: the allowed name must appear in the url or address (substring)
  E2 exact host or dot-suffix match, https only, no userinfo, registry-bound email recipients, no query or fragment on third-party hosts, no url-valued parameter anywhere
  E3 + payload scan: url-decode, base64 and hex-decode, then look for the tenant's private values and any 8-character run of one
  E4 + render: remote images stripped, links shown with their host, tenant path binding on shared hosts, limit on encoded-looking hostname labels, per-task request budget
"""
from __future__ import annotations
import base64, binascii, math, re
from collections import Counter
from dataclasses import dataclass, field
from urllib.parse import urlsplit, unquote, parse_qsl

URL = re.compile(r"https?://[^\s)\]>\"']+", re.I)
MD_IMG = re.compile(r"!\[[^\]]*\]\(([^)\s]+)[^)]*\)")
HTML_IMG = re.compile(r"<img\b[^>]*>", re.I)

@dataclass
class Ctx:
    tenant: str
    allowed_hosts: tuple            # first-party and vendor hosts
    third_party_hosts: tuple        # allow-listed hosts that serve other people's content (file shares): path binding required
    contacts: frozenset             # registry-bound recipient addresses of this tenant
    private_values: tuple           # the tenant's D3 values (account numbers, tax ids, tokens)
    budget_requests: int = 10

@dataclass
class Output:
    kind: str                       # 'email' | 'render' | 'request'
    to: str = ""; body: str = ""; url: str = ""
    label: str = ""                 # for the lab only: attack class or benign
    sink: str = ""                  # for the lab only: 'attacker' | 'vendor' | 'tenant'

def _variants(s: str):
    """Yield s and decodings of it, so that an encoded secret is looked for as well as a plain one."""
    out = {s, unquote(s), unquote(unquote(s))}
    for tok in set(re.findall(r"[A-Za-z0-9_=-]{12,}", s)) | {x.strip("/") for x in re.findall(r"[A-Za-z0-9+/=]{12,}", s)}:
        for dec in (lambda t: base64.b64decode(t + "=" * (-len(t) % 4), validate=False), lambda t: base64.urlsafe_b64decode(t + "=" * (-len(t) % 4)), lambda t: base64.b32decode(t.upper() + "=" * (-len(t) % 8)), lambda t: bytes.fromhex(t)):
            try: out.add(dec(tok).decode("utf-8", "ignore"))
            except (binascii.Error, ValueError): pass
    return out

def contains_private(s: str, values, run: int = 8) -> bool:
    for v in _variants(s):
        low = v.lower().replace("-", "").replace(" ", "")
        for p in values:
            q = p.lower().replace("-", "")
            if p.lower() in v.lower(): return True
            if any(q[i:i + run] in low for i in range(0, max(1, len(q) - run + 1))) and len(q) >= run: return True
    return False

def entropy(s: str) -> float:
    c = Counter(s); n = len(s)
    return -sum(v / n * math.log2(v / n) for v in c.values()) if n else 0.0

class Egress:
    def __init__(self, level: int, ctx: Ctx): self.level, self.ctx, self.sent = level, ctx, 0
    def _host_ok(self, host: str, allowed) -> bool:
        return any(host == a or host.endswith("." + a) for a in allowed)
    def _url_ok(self, url: str) -> tuple[bool, str]:
        c = self.ctx; lv = self.level
        if lv == 0: return True, "e0"
        if lv == 1: return (any(a in url for a in c.allowed_hosts + c.third_party_hosts), "e1_substring")
        u = urlsplit(url)
        if u.scheme != "https": return False, "scheme"
        if u.username or u.password or "@" in u.netloc: return False, "userinfo"
        host = (u.hostname or "").lower(); first = self._host_ok(host, c.allowed_hosts); third = self._host_ok(host, c.third_party_hosts)
        if not (first or third): return False, "host_not_allowed"
        for k, v in parse_qsl(u.query, keep_blank_values=True):
            if URL.search(unquote(v)) or re.match(r"(?i)(https?:)?//", unquote(v)): return False, "url_in_parameter"
        if not first and (u.query or u.fragment): return False, "query_on_third_party"
        if lv >= 3 and contains_private(url, c.private_values): return False, "private_value_in_url"
        if lv >= 4:
            if any(len(lab) >= 20 or (len(lab) >= 12 and re.fullmatch(r"[a-z2-7]+", lab) and re.search(r"\d", lab)) for lab in host.split(".")): return False, "hostname_looks_encoded"
            if third and not u.path.startswith(f"/t/{c.tenant}/"): return False, "path_not_bound_to_tenant"
            if self.sent >= c.budget_requests: return False, "request_budget"
        return True, "ok"
    def check(self, o: Output) -> tuple[bool, str, str]:
        """Returns (allowed, reason, text as it will leave)."""
        c = self.ctx; lv = self.level
        if o.kind == "request":
            ok, why = self._url_ok(o.url)
            if ok: self.sent += 1
            return ok, why, o.url if ok else ""
        if o.kind == "email":
            if lv == 1 and not any(a in o.to for a in c.allowed_hosts): return False, "recipient_domain", ""
            if lv >= 2 and o.to.lower() not in c.contacts: return False, "recipient_not_in_registry", ""
            if lv >= 3 and contains_private(o.body, c.private_values): return False, "private_value_in_body", ""
            body = o.body
            if lv >= 4: body = self.render(o.body)[0]
            for u in URL.findall(body):
                ok, why = self._url_ok(u)
                if not ok and lv >= 1: return False, "url_in_body:" + why, ""
            return True, "ok", body
        if o.kind == "render":
            text = o.body; 
            if lv >= 4: text, _ = self.render(text)
            if lv >= 1:
                for u in URL.findall(text):
                    ok, why = self._url_ok(u)
                    if not ok: return False, "url_in_render:" + why, ""
            if lv >= 3 and contains_private(text, c.private_values): return False, "private_value_in_text", ""
            return True, "ok", text
        raise ValueError(o.kind)
    def render(self, text: str) -> tuple[str, int]:
        """Strip remote images (markdown and html); show every link with its host in front. Returns (text, number of things changed)."""
        n = 0
        def img(m):
            nonlocal n; n += 1; return "[image removed]"
        text = MD_IMG.sub(img, text); text = HTML_IMG.sub(img, text)
        def link(m):
            nonlocal n; n += 1; h = urlsplit(m.group(2)).hostname or "?"; return f"{m.group(1)} ({h})"
        text = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", link, text)
        return text, n

import ipaddress, socket
def is_internal_host(host: str, resolved: tuple = (), canon: bool = True) -> bool:
    """True for a loopback, private, link-local, reserved or metadata address, given as a literal or as the addresses the name resolved to. The caller resolves ONCE and connects to that address."""
    cands = list(resolved)
    try: cands.append(ipaddress.ip_address(host.strip("[]")))
    except ValueError:
        if canon:   # integer, hex and short dotted forms that an http client still reads as an address
            try: cands.append(ipaddress.ip_address(socket.inet_ntoa(socket.inet_aton(host))))
            except (OSError, ValueError): pass
    for c in cands:
        ip = ipaddress.ip_address(c) if isinstance(c, str) else c
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified: return True
        if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped and is_internal_host(str(ip.ipv4_mapped)): return True
    return host.lower() in ("localhost", "metadata.google.internal") or host.lower().endswith((".internal", ".local", ".localhost"))
