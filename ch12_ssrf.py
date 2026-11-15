#!/usr/bin/env python3
"""Chapter 12, small lab: a tenant-configured webhook url is an egress destination too. 16 destinations, no network access: names are given with the addresses they would resolve to.
Policy A: https and an exact host allow-list is not available (tenants choose their own endpoints), so the check is 'not internal'. Policy B: the check applied to the resolved addresses, once, before connecting. Policy C: B plus canonical forms of numeric hosts (integer, hex)."""
import sys, json
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
from bulwark.egress import is_internal_host
from urllib.parse import urlsplit
CASES = [("https://hooks.customer.example/ledgerly", ("93.184.216.34",), False), ("https://10.0.0.5/hook", (), True), ("https://169.254.169.254/latest/meta-data/", (), True), ("https://localhost:8080/", (), True),
 ("https://127.0.0.1/", (), True), ("https://[::1]/", (), True), ("https://[::ffff:10.0.0.5]/", (), True), ("https://metadata.google.internal/computeMetadata/v1/", (), True), ("https://db.corp.internal/", (), True),
 ("https://hooks.attacker.example/x", ("10.0.0.7",), True), ("https://rebind.attacker.example/x", ("192.168.1.10",), True), ("https://2130706433/", (), True), ("https://0x7f.0.0.1/", (), True),
 ("https://hooks.customer.example/ledgerly", ("93.184.216.34", "10.0.0.9"), True), ("https://api.vendor.example/pay", ("8.8.4.4",), False), ("https://[2606:4700:4700::1111]/hook", (), False)]
import ipaddress
def host_of(u): return urlsplit(u).hostname or ""
def literal_only(h):
    try: ipaddress.ip_address(h); return is_internal_host(h)
    except ValueError: return h in ("localhost",) or h.endswith((".internal", ".local"))
rows = []; a = b = c3 = 0
for u, res, bad in CASES:
    h = host_of(u); A = literal_only(h); B = is_internal_host(h, res, canon=False); C = is_internal_host(h, res)
    rows.append(dict(url=u, resolves=list(res), truly_internal=bad, A_blocks=A, B_blocks=B, C_blocks=C)); a += (A == bad); b += (B == bad); c3 += (C == bad)
L = [f"policy A (literal host only): correct on {a} of {len(CASES)}; policy B (resolved addresses): correct on {b} of {len(CASES)}; policy C (B plus numeric forms): correct on {c3} of {len(CASES)}"]
for r in rows:
    if r["A_blocks"] != r["truly_internal"] or r["B_blocks"] != r["truly_internal"] or r["C_blocks"] != r["truly_internal"]: L.append(f"  {r['url']:55} resolves {r['resolves']} internal={r['truly_internal']} A_blocks={r['A_blocks']} B_blocks={r['B_blocks']} C_blocks={r['C_blocks']}")
print("\n".join(L)); (here / "results/ch12_ssrf.log").write_text("\n".join(L) + "\n"); json.dump(rows, open(here / "results/ch12_ssrf.json", "w"), indent=1)
