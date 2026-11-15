#!/usr/bin/env python3
"""Chapter 29, lab 1 (no model): the red team's work list.  Entry points x assets from threatmodel/quill_invoice.json.  For each pair I record (a) whether an attack path is plausible (my judgement, stated as a one-line path),
(b) which earlier chapter's lab exercised that path against a running control (judgement from the book's own results; a chapter number is listed only if a lab in 04-code attacked that entry and that asset).
Output: results/ch29_attack_matrix.json and a table.  Cells with a path and no chapter are the first things a red team should try."""
import json
from pathlib import Path
here = Path(__file__).resolve().parent
tm = json.load(open(here / "threatmodel/quill_invoice.json"))
E, A = tm["entry_points"], tm["assets"]
# (entry, asset): (path, [chapters whose lab attacked it])
M = {
 ("email_intake","vendor_bank_details"): ("forged vendor invoice with a new account", [1,2,14]),
 ("email_intake","customer_ledger"): ("note in a mail makes Quill reply with ledger rows", [3,12,16]),
 ("email_intake","tool_credentials"): ("mail asks the agent to include its token in a reply", [6]),
 ("email_intake","evidence_store"): ("flood of hostile mail fills the review queue and the log", []),
 ("email_intake","tenant_boundary"): ("mail from tenant A quotes tenant B's invoice number", [11]),
 ("email_intake","prompt_registry"): ("none (mail cannot reach the registry)", None),
 ("document_upload","vendor_bank_details"): ("hidden text layer, label confusion, lookalike vendor", [14,15,19,20,21]),
 ("document_upload","customer_ledger"): ("document makes the agent send ledger data out", [12,16,21]),
 ("document_upload","tool_credentials"): ("document asks for a credential or a debug dump", [6]),
 ("document_upload","evidence_store"): ("oversized or malformed document makes the logger drop or truncate rows", [13]),
 ("document_upload","tenant_boundary"): ("document names another tenant's vendor", [11]),
 ("document_upload","prompt_registry"): ("none", None),
 ("web_chat","vendor_bank_details"): ("user (or injected) chat text changes a vendor's account", [8,10]),
 ("web_chat","customer_ledger"): ("chat asks for another business's rows", [11,22]),
 ("web_chat","tool_credentials"): ("chat extracts the token or the key", [6,23]),
 ("web_chat","evidence_store"): ("chat session ends before the evidence row is written", [13]),
 ("web_chat","tenant_boundary"): ("chat history or cache leaks across tenants", [11]),
 ("web_chat","prompt_registry"): ("chat reveals or overrides the system prompt", [3,18,23]),
 ("bank_feed_webhook","vendor_bank_details"): ("memo field carries an instruction to change payee", [2,8,21]),
 ("bank_feed_webhook","customer_ledger"): ("memo triggers a read and a send", [21]),
 ("bank_feed_webhook","tool_credentials"): ("none beyond the email and chat paths", None),
 ("bank_feed_webhook","evidence_store"): ("replayed webhook creates duplicate evidence and duplicate effects", [10]),
 ("bank_feed_webhook","tenant_boundary"): ("webhook for one tenant matched to another's invoice", []),
 ("bank_feed_webhook","prompt_registry"): ("none", None),
 ("mcp_install","vendor_bank_details"): ("tool description steers a payment call", [25]),
 ("mcp_install","customer_ledger"): ("installed tool reads and exports rows", [25,26]),
 ("mcp_install","tool_credentials"): ("installed server receives the user's token (passthrough)", [25,26]),
 ("mcp_install","evidence_store"): ("tool writes to the evidence directory", [27]),
 ("mcp_install","tenant_boundary"): ("shared server serves two tenants", [25]),
 ("mcp_install","prompt_registry"): ("skill or tool text rewrites the behaviour tuple", [26]),
 ("scheduled_reconcile","vendor_bank_details"): ("stale vendor record paid by an unattended run", [7,8]),
 ("scheduled_reconcile","customer_ledger"): ("nightly job reads more than the task needs", [7]),
 ("scheduled_reconcile","tool_credentials"): ("long-lived credential held by an unattended job", [6,7]),
 ("scheduled_reconcile","evidence_store"): ("job runs under no principal and its rows have no actor", []),
 ("scheduled_reconcile","tenant_boundary"): ("batch loop mixes tenants in one context", [11]),
 ("scheduled_reconcile","prompt_registry"): ("prompt edited between release and the nightly run", [18]),
 ("admin_impersonation","vendor_bank_details"): ("support session changes a vendor account", [6,10]),
 ("admin_impersonation","customer_ledger"): ("support reads a tenant's books without a grant", [6,11]),
 ("admin_impersonation","tool_credentials"): ("support session obtains a task token", [6]),
 ("admin_impersonation","evidence_store"): ("admin edits or erases evidence", [13]),
 ("admin_impersonation","tenant_boundary"): ("impersonation crosses the tenant boundary", [6,11]),
 ("admin_impersonation","prompt_registry"): ("admin promotes an unreviewed prompt", [18]),
}
rows = []; T = {"paths": 0, "tested": 0, "untested": []}
for e in E:
    for a in A:
        path, ch = M[(e, a)]
        if ch is None: rows.append(dict(entry=e, asset=a, path=None, chapters=[])); continue
        T["paths"] += 1; T["tested"] += bool(ch)
        rows.append(dict(entry=e, asset=a, path=path, chapters=ch))
        if not ch: T["untested"].append((e, a, path))
print(f"{len(E)} entry points x {len(A)} assets = {len(E)*len(A)} pairs; plausible paths {T['paths']}; exercised by an earlier lab {T['tested']}; not exercised {len(T['untested'])}")
for u in T["untested"]: print("  UNTESTED:", u)
for e in E: print(f"{e:22s}", " ".join(f"{'-' if not [r for r in rows if r['entry']==e and r['asset']==a][0]['path'] else ('T' if [r for r in rows if r['entry']==e and r['asset']==a][0]['chapters'] else 'O')}" for a in A))
json.dump(dict(rows=rows, summary=dict(pairs=len(E)*len(A), paths=T["paths"], tested=T["tested"], untested=T["untested"])), open(here / "results/ch29_attack_matrix.json", "w"), indent=1)
