#!/usr/bin/env python3
"""Chapter 45, lab 1d (no model): two public cases written as programmes and put through the same checker.  Both are encoded from the published descriptions (EchoLeak, CVE-2025-32711, reported June 2025; the GitHub MCP 'toxic agent flow', Invariant Labs, 26 May 2025), as I read them.
I have no access to either system; every gate below is my reading of a public write-up and is marked [VERIFY] in the chapter.  Writes results/ch45_public.log."""
import sys
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
from bulwark.casestudy import *
R = lambda b, **k: Gate("deterministic", b, True, **k)
def echoleak(fixed=False):
    render = [Gate("model", "injection classifier on inbound content"), Gate("deterministic", "link redaction by pattern (inline form only)", False), Gate("deterministic", "content-security-policy host list: an allowed host relays a URL the output supplies", False)]
    if fixed: render = [R("render only links and images whose host is the tenant's own and whose path is bound to the tenant (Chapter 12)")]
    return Programme("EchoLeak (as I read it)", "fixed" if fixed else "as reported", [Source("inbound_email", False), Source("user_documents", True), Source("user_question", True)],
                     [Tool("render_markdown_with_auto_fetch", "EGRESS", render), Tool("retrieve_mail_and_files", "READ")])
def github_mcp(fixed=False, always_allow=True):
    pr = [] if always_allow else [Gate("human", "per-call confirmation showing the tool call", shows_evidence=True)]
    if fixed: pr = [R("session is scoped to one repository; pull requests only to that repository")]
    return Programme("GitHub MCP toxic flow (as I read it)", ("fixed" if fixed else ("as reported, always-allow" if always_allow else "as reported, confirm each call")), [Source("public_issue", False), Source("user_request", True)],
                     [Tool("create_pull_request_public_repo", "EGRESS", pr), Tool("read_private_repo", "READ")])
def main():
    L = []
    for p in (echoleak(), echoleak(True), github_mcp(), github_mcp(always_allow=False), github_mcp(True)):
        f = findings(p); L.append(f"{p.name:42} {p.stage:28} unbounded paths {len(f)}: " + ("; ".join(f"{a}->{b} ({c})" for a, b, e, c in f) if f else "none"))
    (here / "results/ch45_public.log").write_text("\n".join(L) + "\n"); print("\n".join(L))
if __name__ == "__main__": main()
