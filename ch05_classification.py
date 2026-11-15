#!/usr/bin/env python3
"""Chapter 5 lab 2: lint two classifications of the same invoice-to-payment flow. No model calls."""
import json
from pathlib import Path
from bulwark.stepclass import lint, quill_invoice_flow_naive, quill_invoice_flow_classified

here = Path(__file__).resolve().parent
naive = quill_invoice_flow_naive()
classified = quill_invoice_flow_classified()
out = {
    "naive": {
        "steps": [s.__dict__ | {"cls": int(s.cls)} for s in naive],
        "findings": lint(naive),
        "n_findings": len(lint(naive)),
        "model_steps": sum(s.cls >= 2 for s in naive),
        "authority_on_model": sum(s.decides_authority and s.cls >= 2 for s in naive),
    },
    "classified": {
        "steps": [s.__dict__ | {"cls": int(s.cls)} for s in classified],
        "findings": lint(classified),
        "n_findings": len(lint(classified)),
        "model_steps": sum(s.cls >= 2 for s in classified),
        "authority_on_model": sum(s.decides_authority and s.cls >= 2 for s in classified),
    },
}
print("naive findings:", out["naive"]["n_findings"])
for f in out["naive"]["findings"]:
    print(" ", f)
print("classified findings:", out["classified"]["n_findings"])
print("model steps naive/classified:", out["naive"]["model_steps"], out["classified"]["model_steps"])
print("authority-on-model naive/classified:", out["naive"]["authority_on_model"], out["classified"]["authority_on_model"])
(here / "results/ch05_classification.json").write_text(json.dumps(out, indent=1, default=str))
