#!/usr/bin/env python3
"""Chapter 5 second setting: terms the code does not know. Code refuses; the model guesses a date."""
import json, time
from datetime import date
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from bulwark.quill_lab import load_env
from bulwark.steps import due_date

load_env()
import anthropic

client = anthropic.Anthropic()
MODEL = "claude-haiku-4-5-20251001"
here = Path(__file__).resolve().parent
INVOICE_DATE = "2026-11-09"
TERMS = [
    "2/10 Net 30",
    "2% 10 Net 30",
    "Net 30 EOM",
    "CIA",
    "COD",
    "as agreed",
    "upon completion",
    "whenever",
    "Net 30 from receipt of goods",
    "Net-30 from ship date",
    "end of next month",
    "due when paid by our customer",
]


def code_verdict(terms):
    try:
        return dict(ok=True, due=due_date(date.fromisoformat(INVOICE_DATE), terms).isoformat())
    except ValueError as e:
        return dict(ok=False, error=str(e))


def prompt(terms):
    return (
        "Compute the invoice due date. Terms: 'Net N' = N days after the invoice date; "
        "'EOM+N' = N days after the last day of the invoice's month; "
        "'Due on receipt' = the invoice date.\n"
        f"Invoice date: {INVOICE_DATE}\nTerms: {terms}\n"
        "Answer with JSON only: {\"due_date\": \"YYYY-MM-DD\"}"
    )


def ask(terms):
    for attempt in range(4):
        try:
            m = client.messages.create(model=MODEL, max_tokens=80, messages=[{"role": "user", "content": prompt(terms)}])
            raw = "".join(getattr(b, "text", "") for b in m.content)
            import re, json as js
            mm = re.search(r"\{.*\}", raw, re.S)
            ans = js.loads(mm.group(0)).get("due_date") if mm else None
            return dict(terms=terms, raw=raw, due=ans, guessed=ans is not None, err=False)
        except Exception as e:
            time.sleep(2 + attempt * 3)
            last = str(e)
    return dict(terms=terms, raw="", due=None, guessed=False, err=True, error=last)


with ThreadPoolExecutor(8) as ex:
    rows = list(ex.map(ask, TERMS))
for r in rows:
    r["code"] = code_verdict(r["terms"])
    print(f"{r['terms']!r:40} code_ok={r['code']['ok']} model_due={r['due']}")

out = dict(
    model=MODEL, date=time.strftime("%Y-%m-%d %H:%M %Z"), invoice_date=INVOICE_DATE,
    n=len(rows),
    code_refused=sum(not r["code"]["ok"] for r in rows),
    model_guessed=sum(r["guessed"] for r in rows),
    model_errors=sum(r["err"] for r in rows),
    rows=rows,
)
print("code refused", out["code_refused"], "of", out["n"], "; model guessed", out["model_guessed"])
(here / "results/ch05_unknown_terms.json").write_text(json.dumps(out, indent=1))
