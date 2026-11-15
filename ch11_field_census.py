#!/usr/bin/env python3
"""Chapter 11, lab 5: what the model is shown. No model. For each of four tasks, the fields of a vendor/invoice record that the task needs, against the whole record,
weighted by the SENSITIVE table in bulwark/tenancy.py (bank_account 3, tax_id 3, contact_email 2, contact_phone 2, address 1)."""
import sys, json
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
from bulwark.tenancy import *
REC = {'invoice_number': 'INV-1007', 'vendor_name': 'Lone Star Paper Supply', 'amount_cents': 141200, 'due_date': '2026-11-30', 'status': 'open', 'line_items': 'Copy paper 10 cartons; Kraft rolls x6', 'bank_account': 'US-ACC-77120934', 'tax_id': 'TX-48213', 'contact_email': 'orders@lonestar-paper.example', 'contact_phone': '+1 512 555 0147', 'address': '4400 Burnet Rd, Austin', 'vendor_ref': 'p_ls'}
L = []; R = {}
whole = len(REC); wsens = sum(SENSITIVE.get(k, 0) for k in REC)
L.append(f"{'task':20} {'fields shown':>12} of {whole}  {'sensitive weight':>16} of {wsens}  sensitive fields shown")
for task in PROJECTIONS:
    p = project(REC, task); w = sum(SENSITIVE.get(k, 0) for k in p); sf = [k for k in p if k in SENSITIVE]
    L.append(f"{task:20} {len(p):>12}        {w:>16}            {', '.join(sf) or '-'}"); R[task] = dict(fields=len(p), weight=w, sensitive=sf)
R["whole"] = dict(fields=whole, weight=wsens)
print("\n".join(L)); (here / "results/ch11_field_census.log").write_text("\n".join(L) + "\n"); json.dump(R, open(here / "results/ch11_field_census.json", "w"), indent=1)
