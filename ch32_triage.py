#!/usr/bin/env python3
"""Chapter 32, lab 4 (live): can a model read the week's AUTO log and flag what looks wrong?  Haiku 4.5, 12 weekly batches x 3 repeats, no labels in the prompt.
Each row: id, vendor name, day, amount, the vendor's median and count of earlier AUTO amounts, whether the destination account is new for the vendor (and its prior payments).
Run A: rows as above.  Run B: the same rows plus the reverse-shadow disagreement kind where there is one.  Scored against the Chapter 32 world's truth.  Writes results/ch32_triage.json."""
import sys, json, re, time
from pathlib import Path
from statistics import median
from concurrent.futures import ThreadPoolExecutor
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
import ch32_detect as D, ch30_loop as L
SYS = ("You review the week's automatically approved supplier-invoice payments for a small company and flag any that look wrong and should be looked at by a person before money moves. "
       "Everything is fictional. Be selective: a normal week has few or no problems. Reply with JSON only: {\"flag\": [{\"id\": \"...\", \"why\": \"...\"}]}.")
def rows_by_week(obs, with_kind):
    hist = {}; paid = {}; seenacct = {}; weeks = {}
    for o in obs:
        h = hist.setdefault(o.vendor, []); pa = paid.setdefault(o.vendor, {})
        if o.route == "AUTO":
            row = dict(id=o.id, vendor=D.V[o.vendor]["name"], day=o.day, amount=round(o.amount / 100, 2), prior_n=len(h), prior_median=round(median(h) / 100, 2) if h else None,
                       account_prior_payments=pa.get(o.dest, 0), vendor_has_other_account=any(k != o.dest for k in pa))
            if with_kind and o.conflict: row["retired_control_disagrees"] = o.conflict
            weeks.setdefault(o.day // 7 + 1, []).append(row); h.append(o.amount); pa[o.dest] = pa.get(o.dest, 0) + 1
    return weeks
def ask(rows):
    raw = L.call(SYS, [{"role": "user", "content": "Approved payments this week:\n" + "\n".join(json.dumps(r) for r in rows)}], 3000)
    m = re.search(r"\{.*\}", raw, re.S)
    try: return [x["id"] for x in json.loads(m.group(0))["flag"]]
    except Exception: return None
def main():
    obs, truth, info, _ = D.build_obs(); res = {}
    for name, wk in (("A_rows", False), ("B_rows+kind", True)):
        weeks = rows_by_week(obs, wk); jobs = [(w, r) for w in weeks for r in range(3)]
        with ThreadPoolExecutor(8) as ex: outs = list(ex.map(lambda j: ask(weeks[j[0]]), jobs))
        fails = sum(o is None for o in outs); per = []
        for r in range(3):
            fl = set(); 
            for (w, rr), o in zip(jobs, outs):
                if rr == r and o: fl |= set(o)
            tp = fl & set(truth); per.append(dict(flagged=len(fl), caught=len(tp), false=len(fl - set(truth)), by_class={c: sum(1 for i in tp if info[i]["cls"] == c) for c in sorted({info[i]["cls"] for i in truth})}))
        res[name] = dict(repeats=per, parse_failures=fails, rows=sum(len(v) for v in weeks.values()))
        print(name, "rows", res[name]["rows"], "parse failures", fails); [print("  rep", p) for p in per]
    res.update(truth_n=len(truth), calls=L.meter.calls, tokens_in=L.meter.tokens_in, tokens_out=L.meter.tokens_out, usd=round(L.meter.usd(), 2), truth_by_class={c: sum(1 for i in truth if info[i]["cls"] == c) for c in sorted({info[i]["cls"] for i in truth})})
    print("calls", L.meter.calls, "usd", round(L.meter.usd(), 2)); json.dump(res, open(here / "results/ch32_triage.json", "w"), indent=1)
if __name__ == "__main__": main()
