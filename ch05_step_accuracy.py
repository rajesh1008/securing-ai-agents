#!/usr/bin/env python3
"""Chapter 5 lab 1: four steps of the invoice flow done by code and by a model (3 repeats each, default sampling)."""
import json, random, re, time, statistics, sys
from datetime import date, timedelta
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from bulwark.quill_lab import load_env
from bulwark import steps as S
load_env()
import anthropic
client = anthropic.Anthropic()
MODEL = "claude-haiku-4-5-20251001"
REPEATS = 3
rng = random.Random(5005)
here = Path(__file__).resolve().parent

def dollars(c): return f"${c/100:,.2f}"

# ---------- case generators (truth comes from construction, not from the code under test) ----------
def gen_due():
    cases = []
    terms = ["Net 15", "Net 30", "Net 45", "Net 60", "Net 90", "EOM+10", "EOM+15", "Due on receipt"]
    dates = [date(2028,2,10), date(2028,1,31), date(2026,12,20), date(2026,11,30), date(2027,2,28), date(2026,8,31)]
    while len(dates) < 30:
        dates.append(date(2026,1,1) + timedelta(days=rng.randrange(0, 700)))
    for i, d in enumerate(dates):
        t = terms[i % len(terms)]
        cases.append(dict(invoice_date=d.isoformat(), terms=t))
    # truth by hand-built construction, independent of steps.py: day arithmetic via ordinal
    for c in cases:
        d = date.fromisoformat(c["invoice_date"]); t = c["terms"]
        if t == "Due on receipt": c["truth"] = d.isoformat()
        elif t.startswith("Net"): c["truth"] = date.fromordinal(d.toordinal() + int(t.split()[1])).isoformat()
        else:
            nxt = date(d.year + (d.month == 12), d.month % 12 + 1, 1)
            eom = date.fromordinal(nxt.toordinal() - 1)
            c["truth"] = date.fromordinal(eom.toordinal() + int(t.split("+")[1])).isoformat()
    return cases

def gen_dup():
    payees = ["payee_lone_star", "payee_riverside", "payee_gulf_coast", "payee_hill_tools"]
    variants = lambda n: [f"INV-{n:04d}", f"inv {n}", f"INV{n}", f"Inv-{n}", f"INV-{n:05d}"]
    cases = []
    for i in range(30):
        ledger = []
        for j in range(6):
            n = rng.randrange(100, 900)
            ledger.append(dict(payee_id=rng.choice(payees), number=f"INV-{n:04d}", amount=rng.randrange(5000, 400000)))
        target = rng.choice(ledger)
        n = int(target["number"].split("-")[1])
        if i % 2 == 0:
            new = dict(payee_id=target["payee_id"], number=rng.choice(variants(n)), amount=rng.randrange(5000, 400000)); truth = True
        else:
            kind = (i // 2) % 4
            if kind == 0: new = dict(payee_id=rng.choice([p for p in payees if p != target["payee_id"]]), number=rng.choice(variants(n)), amount=target["amount"])
            elif kind == 1: new = dict(payee_id=target["payee_id"], number=f"INV-{n+1:04d}", amount=target["amount"])
            elif kind == 2: new = dict(payee_id=target["payee_id"], number=f"CN-{n:04d}", amount=target["amount"])
            else: new = dict(payee_id=target["payee_id"], number=f"INV-{n+1000:04d}", amount=rng.randrange(5000, 400000))
            truth = False
        # make sure construction really matches the intent: remove accidental collisions
        if not truth:
            k = lambda r: (r["payee_id"], re.sub(r"[^A-Z0-9]", "", r["number"].upper()).lstrip("INV").lstrip("0"))
            if any(k(r) == k(new) and re.sub(r"[^A-Z0-9]", "", r["number"].upper()).startswith("INV") == re.sub(r"[^A-Z0-9]", "", new["number"].upper()).startswith("INV") for r in ledger):
                new["number"] = "INV-0999"
        cases.append(dict(ledger=ledger, new=new, truth=truth))
    return cases

def gen_cap():
    cases = []
    for i in range(30):
        cap = rng.choice([2_500_00, 5_000_00, 10_000_00, 12_500_00])
        paid = rng.randrange(cap // 3, cap)
        room = cap - paid
        delta = rng.choice([-1, 1, 0, -100, 100, -5000, 5000, 1])
        amount = max(1, room + delta)
        cases.append(dict(cap=cap, paid=paid, amount=amount, truth=(paid + amount > cap)))
    return cases

def gen_totals():
    cases = []
    for i in range(30):
        n = rng.randrange(3, 7)
        lines = [rng.randrange(1500, 90000) for _ in range(n)]
        sub = sum(lines); tax = round(sub * 0.0825)
        total = sub + tax
        if i % 2 == 1:
            total += rng.choice([-1, 1, 100, -100, 10, 1000]); truth = False
        else: truth = True
        cases.append(dict(lines=lines, tax=tax, total=total, truth=truth))
    return cases

# ---------- prompts ----------
def p_due(c): return ("Compute the invoice due date. Terms: 'Net N' = N days after the invoice date; 'EOM+N' = N days after the last day of the invoice's month; 'Due on receipt' = the invoice date.\n"
    f"Invoice date: {c['invoice_date']}\nTerms: {c['terms']}\nAnswer with JSON only: {{\"due_date\": \"YYYY-MM-DD\"}}")
def p_dup(c):
    led = "\n".join(f"- payee {r['payee_id']}, invoice number {r['number']}, amount {dollars(r['amount'])}" for r in c["ledger"])
    n = c["new"]
    return ("Decide whether the new invoice is a duplicate of one already in the ledger. It is a duplicate if the payee is the same and the invoice number is the same, ignoring case, spaces, punctuation and leading zeros. The amount is not part of the rule.\n"
        f"Ledger:\n{led}\nNew invoice: payee {n['payee_id']}, invoice number {n['number']}, amount {dollars(n['amount'])}\nAnswer with JSON only: {{\"duplicate\": true|false}}")
def p_cap(c): return ("A monthly payment cap applies to a payee. Decide whether paying the new amount would take the month's total above the cap (equal to the cap is allowed).\n"
    f"Cap: {dollars(c['cap'])}\nAlready paid this month: {dollars(c['paid'])}\nNew payment: {dollars(c['amount'])}\nAnswer with JSON only: {{\"over_cap\": true|false}}")
def p_tot(c): return ("Check whether an invoice's total is consistent: the sum of the line amounts plus tax must equal the total exactly.\n"
    f"Lines: {', '.join(dollars(x) for x in c['lines'])}\nTax: {dollars(c['tax'])}\nStated total: {dollars(c['total'])}\nAnswer with JSON only: {{\"consistent\": true|false}}")

def ask(prompt):
    t0 = time.time()
    for attempt in range(4):
        try:
            m = client.messages.create(model=MODEL, max_tokens=60, messages=[{"role": "user", "content": prompt}])
            break
        except Exception as e:
            time.sleep(2 + attempt * 3); m = None
    if m is None: return dict(raw="", err=True, ms=0, tin=0, tout=0)
    raw = "".join(getattr(b, "text", "") for b in m.content)
    return dict(raw=raw, err=False, ms=int((time.time() - t0) * 1000), tin=m.usage.input_tokens, tout=m.usage.output_tokens)

def parse(raw, key):
    try:
        mm = re.search(r"\{.*\}", raw, re.S); return json.loads(mm.group(0))[key]
    except Exception: return None

def conf(cases, per_case, truthf):
    if not isinstance(truthf(cases[0]), bool): return None
    d = {"truth_true_said_true": 0, "truth_true_said_false": 0, "truth_false_said_true": 0, "truth_false_said_false": 0, "none": 0}
    for i, v in per_case.items():
        for c in v:
            if c["ans"] is None: d["none"] += 1
            else: d[f"truth_{str(truthf(cases[i])).lower()}_said_{str(c['ans']).lower()}"] += 1
    return d

STEPS = {
  "due_date": (gen_due, p_due, "due_date", lambda c: c["truth"], lambda c: S.due_date(date.fromisoformat(c["invoice_date"]), c["terms"]).isoformat()),
  "duplicate": (gen_dup, p_dup, "duplicate", lambda c: c["truth"], lambda c: S.is_duplicate(c["new"], c["ledger"])),
  "over_cap": (gen_cap, p_cap, "over_cap", lambda c: c["truth"], lambda c: S.over_monthly_cap(c["amount"], c["paid"], c["cap"])),
  "totals": (gen_totals, p_tot, "consistent", lambda c: c["truth"], lambda c: S.totals_consistent(c["lines"], c["tax"], c["total"])),
}
out = {"model": MODEL, "repeats": REPEATS, "date": "2026-11-09", "steps": {}}
for name, (gen, pf, key, truthf, codef) in STEPS.items():
    cases = gen()
    jobs = [(i, r) for i in range(len(cases)) for r in range(REPEATS)]
    with ThreadPoolExecutor(8) as ex: res = list(ex.map(lambda ir: ask(pf(cases[ir[0]])), jobs))
    per_case = {}
    for (i, r), x in zip(jobs, res):
        ans = parse(x["raw"], key); ok = (ans == truthf(cases[i]))
        per_case.setdefault(i, []).append(dict(ans=ans, ok=ok, **{k: x[k] for k in ("ms", "tin", "tout", "err")}))
    calls = [c for v in per_case.values() for c in v]
    t0 = time.perf_counter(); code_ok = 0
    for _ in range(1000):
        for c in cases: code_ok += (codef(c) == truthf(c))
    code_us = (time.perf_counter() - t0) / (1000 * len(cases)) * 1e6
    row = dict(cases=len(cases), calls=len(calls), model_correct=sum(c["ok"] for c in calls),
        cases_all_correct=sum(all(c["ok"] for c in v) for v in per_case.values()),
        cases_none_correct=sum(not any(c["ok"] for c in v) for v in per_case.values()),
        cases_repeats_disagree=sum(len({str(c["ans"]) for c in v}) > 1 for v in per_case.values()),
        unparseable=sum(c["ans"] is None for c in calls), api_errors=sum(c["err"] for c in calls),
        median_ms=int(statistics.median(c["ms"] for c in calls)), median_in_tokens=int(statistics.median(c["tin"] for c in calls)),
        median_out_tokens=int(statistics.median(c["tout"] for c in calls)),
        code_correct=code_ok // 1000, code_cases=len(cases), code_microseconds_per_case=round(code_us, 2),
        confusion=conf(cases, per_case, truthf), all_cases=[dict(case=cases[i], answers=[c["ans"] for c in v]) for i, v in per_case.items()],
        wrong_cases=[dict(case=cases[i], answers=[c["ans"] for c in v]) for i, v in per_case.items() if not all(c["ok"] for c in v)][:6])
    out["steps"][name] = row
    print(f"{name:10} model {row['model_correct']}/{row['calls']} calls correct; all 3 right in {row['cases_all_correct']}/{row['cases']} cases; none right {row['cases_none_correct']}; repeats disagree {row['cases_repeats_disagree']}; unparseable {row['unparseable']}; median {row['median_ms']} ms, {row['median_in_tokens']} in / {row['median_out_tokens']} out tokens | code {row['code_correct']}/{row['code_cases']} correct, {row['code_microseconds_per_case']} us/case", flush=True)
(here / "results/ch05_step_accuracy.json").write_text(json.dumps(out, indent=1))
