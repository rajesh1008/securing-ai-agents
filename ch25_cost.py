#!/usr/bin/env python3
"""Chapter 25, cost: microseconds per operation of the MCP controls (mean of 5,000 repetitions, no model), and token overhead of the description text in a 12-tool ledger manifest.  Writes results/ch25_cost.json and .log"""
import json, sys, time
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
from bulwark.mcpguard import *
from ch25_fixtures import LEDGER, MAIL, poisoned_ledger
pin = Pin.from_tools("ledger", "1", LEDGER, "p"); cat = HostCatalogue(); cat.approve("ledger", pin, LEDGER); A = AudienceTokens(b"k"); tok = A.mint("ledger", ["invoice:read"], "hill", 300, 100.0)
def t(f, n=5000):
    t0 = time.perf_counter()
    for _ in range(n): f()
    return (time.perf_counter() - t0) / n * 1e6
R = dict(tool_digest=t(lambda: tool_digest(LEDGER[0])), diff_12_tools=t(lambda: diff_manifest(pin, LEDGER)), catalogue_visible_12=t(lambda: cat.visible("ledger", LEDGER)), scan_tool=t(lambda: scan_tool(LEDGER[0])), scan_12=t(lambda: [scan_tool(x) for x in LEDGER]),
         check_args=t(lambda: check_args(LEDGER[0]["inputSchema"], {"invoice_id": "INV-1042"}, {"invoice_id": r"INV-[0-9]{3,6}"})), token_mint=t(lambda: A.mint("ledger", ["invoice:read"], "hill", 300, 100.0)), token_verify=t(lambda: A.verify(tok, "ledger", "invoice:read", 101.0)), route=t(lambda: cat.route("ledger__get_invoice")))
chars = sum(len(x["description"]) + len(json.dumps(x["inputSchema"])) for x in LEDGER); R["manifest_chars_12_tools"] = chars; R["approx_tokens_12_tools"] = chars // 4
R["extra_chars_param_poison"] = len(json.dumps(poisoned_ledger("param")[0]["inputSchema"])) - len(json.dumps(LEDGER[0]["inputSchema"]))
L = [f"{k}: {v:.1f}" + (" us" if not k.startswith(("manifest", "approx", "extra")) else "") for k, v in R.items()]
print("\n".join(L)); json.dump(R, open(here / "results/ch25_cost.json", "w"), indent=1); open(here / "results/ch25_cost.log", "w").write("\n".join(L) + "\n")
