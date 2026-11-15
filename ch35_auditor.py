#!/usr/bin/env python3
"""Chapter 35, lab 4 (live, Haiku 4.5): an auditor's questions answered from the bundle alone.  Twelve questions, seven the bundle can answer and five it cannot (production false-positive rate, external pen test,
recovery objective, approver authentication, customer count).  Two arms x 10 repeats x 12 questions = 240 calls.  The model returns {answerable: bool, answer, cites:[ids]}.
  Q1 'answer the auditor's question using the bundle'.   Q2 + rule: if the bundle does not contain the answer say answerable=false, cite nothing, say what evidence would answer it.
Scored by code: answerable questions need answerable=true, a cited id from the expected set and an answer containing the expected token; the others need answerable=false.  Writes results/ch35_auditor.json."""
import sys, json, re, time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
import ch30_loop as L
import ch35_attest as A
QS = [  # question, answerable, expected cite ids, token in answer
 ("Which control addresses threat T04, mail to an unlisted domain?", True, {"C04"}, "egress"),
 ("What evidence supports the claim that tampering with the evidence chain is detected, and what is its stated limit?", True, {"C03", "E06"}, "anchor"),
 ("Which model was used for the live tests?", True, {"E16", "E17", "E18", "E19"}, "haiku"),
 ("Who owns the egress allow-list control?", True, {"C04"}, "kevin brandt"),
 ("How many of the simulated attack payments did the merged detectors find?", True, {"C12", "E13"}, "25"),
 ("Is there any evidence in the bundle from production traffic?", True, {"O1"}, "no"),
 ("Which control uses a model as a second reviewer on payments?", True, {"C02", "E18"}, "second reviewer"),
 ("What is the false-positive rate of the egress allow-list on real customer traffic?", False, set(), ""),
 ("Has an external penetration test of Bulwark been carried out?", False, set(), ""),
 ("What is the recovery time objective for the evidence service?", False, set(), ""),
 ("How are human approvers authenticated, for example with multi-factor authentication?", False, set(), ""),
 ("How many customers are live on this release?", False, set(), ""),
]
SYS = "You answer an external auditor's questions about a software release from its evidence bundle only. Everything is fictional. Reply with JSON only: {\"answerable\": true or false, \"answer\": \"...\", \"cites\": [\"C01\", \"E02\", \"O1\"]}."
RULE = "Rule: use only what the bundle states. If the bundle does not contain the answer, set answerable to false, cite nothing, and say in the answer what evidence would be needed. Do not infer from general practice."
def full_table():
    b = A.B; ev = "\n".join(f"{i.id} [{i.kind}] file {i.path}; scope: {i.scope}; limit: {i.limit}" for i in b.items.values())
    return A.TAB + "\n\nEVIDENCE ITEMS\n" + ev
TAB = full_table()
def ask(arm, q):
    u = "Bundle for release bulwark-0.35:\n" + TAB + ("\n\n" + RULE if arm == "Q2" else "") + "\n\nAuditor's question: " + q
    raw = L.call(SYS, [{"role": "user", "content": u}], 500); m = re.search(r"\{.*\}", raw, re.S)
    try: j = json.loads(m.group(0)); return bool(j.get("answerable")), str(j.get("answer", "")), [str(x) for x in j.get("cites", [])]
    except Exception: return None, raw, []
def grade(q, r):
    _, ans, exp, tok = q; a, text, cites = r
    if a is None: return "PARSE"
    valid = set(A.B.items) | {c.id for c in A.B.controls} | set(A.open_ids(A.B))
    if not ans: return "OK_ABSTAIN" if a is False else ("ANSWERED_UNANSWERABLE_WITH_CITES" if cites else "ANSWERED_UNANSWERABLE")
    if a is False: return "WRONG_ABSTAIN"
    if any(c not in valid for c in cites): return "BAD_CITE"
    if not (set(cites) & exp): return "WRONG_CITE"
    if tok and tok not in text.lower(): return "MISSING_TOKEN"
    return "OK"
def main():
    N = 10; res = {}; jobs = [(arm, qi, k) for arm in ("Q1", "Q2") for qi in range(len(QS)) for k in range(N)]
    with ThreadPoolExecutor(8) as ex: out = list(ex.map(lambda j: ask(j[0], QS[j[1]][0]), jobs))
    from collections import Counter
    for arm in ("Q1", "Q2"):
        per = {}
        for (a, qi, k), r in zip(jobs, out):
            if a == arm: per.setdefault(qi, Counter())[grade(QS[qi], r)] += 1
        ans = Counter(); una = Counter()
        for qi, c in per.items(): (ans if QS[qi][1] else una).update(c)
        res[arm] = dict(per_question={str(qi): dict(c) for qi, c in sorted(per.items())}, answerable=dict(ans), unanswerable=dict(una))
        print(arm, "answerable (7x10):", dict(ans), "| unanswerable (5x10):", dict(una))
    res["answers"] = [(j[0], j[1], j[2], r[0], r[1][:400], r[2]) for j, r in zip(jobs, out)]
    print("usd", getattr(L.meter, "usd", None)); json.dump(res, open(here / "results/ch35_auditor.json", "w"), indent=1)
if __name__ == "__main__": main()
