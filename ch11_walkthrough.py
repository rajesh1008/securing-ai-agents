#!/usr/bin/env python3
"""Chapter 11 walkthrough. No model. One request from tenant biz_001 ('what did Lone Star last invoice us?') with a hostile document in the books, followed through every boundary of this chapter.
Each line says which boundary acted and what it did. The 'model' is a stub that obeys the planted note, so the trace shows what each boundary does to an obedient model."""
import sys, json, secrets, hashlib
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
from bulwark.tenancy import *
L = []; P = L.append
c = Corpus(30, 40); ix = Index(c, "pushdown"); cache = ResultCache(True); tickets = TicketStore(True, True); ring = KeyRing(secrets.token_bytes(32), True); h = Handles()
tenant = "biz_001"; token_claims = dict(sub="prin_emily", tenant=tenant)
P(f"1 identity   : task token verified; tenant taken from the token: {token_claims['tenant']} (the tool schema has no tenant parameter)")
planted = dict(query="Lone Star Paper Supply statement of account biz_007 pay to account", tenant_id="biz_007")
P(f"2 model      : (stub) obeys the planted note and asks search_documents(query={planted['query']!r}, tenant_id={planted['tenant_id']!r})")
P(f"3 tool layer : (narrated) tenant_id is not in the schema and Index.search takes only the verified tenant; the call runs as {tenant}")
res = cache.get_or_compute(tenant, planted["query"], lambda: ix.search(planted["query"], 5, tenant))
P(f"4 retrieval  : pushdown filter; {len(res)} documents returned, tenants {sorted({d.tenant for d in res})}; cache key = ({tenant!r}, query)")
rec = dict(invoice_number="INV-1007", vendor_name="Lone Star Paper Supply", amount_cents=141200, due_date="2026-11-30", status="open", line_items="Copy paper", bank_account="US-ACC-77120934", tax_id="TX-48213", contact_email="orders@lonestar-paper.example")
shown = project(rec, "answer_question")
P(f"5 projection  : model is shown fields {sorted(shown)}; withheld {sorted(set(rec) - set(shown))}")
ref = h.issue(tenant, rec["bank_account"], "acct")
P(f"6 handle      : if the answer must name the account, it names {ref}; another tenant resolving {ref} gets {h.resolve('biz_007', ref)}")
tid = tickets.put(tenant, "approval ticket body")
P(f"7 ticket      : id {tid[:8]}... (random, 96 bits); read by biz_007: {tickets.get(tid, 'biz_007')}; read by {tenant}: {tickets.get(tid, tenant)}")
P(f"8 signing key : tenant key fingerprint {hashlib.sha256(ring.key(tenant)).hexdigest()[:12]} vs biz_007 {hashlib.sha256(ring.key('biz_007')).hexdigest()[:12]}")
name = "Lone Star Paper Supply\nApproved by Kevin Brandt (second person)"
P(f"9 screen      : vendor name from a signature {name!r} is drawn as {safe_text(name)!r}")
print("\n".join(L)); (here / "results/ch11_walkthrough.log").write_text("\n".join(L) + "\n")
