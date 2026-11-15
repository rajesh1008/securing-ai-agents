#!/usr/bin/env python3
"""Chapter 42, lab 2 (no model): does the catalogue catch a design that drifts?  Start from the Q41 sheet; apply one change at a time.
HARMFUL changes are ones the book's own chapters showed to be harmful (each expects at least one named finding); BENIGN changes should produce no finding.
CODE changes are made to a temporary copy of the library, not to the sheet, to show what a sheet check cannot see and what the code scan can.
Writes results/ch42_mutants.json and .log."""
import sys, json, copy, shutil, tempfile
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
from bulwark import patterns as P
import ch42_designs as D
def step(d, i): return [s for s in d["steps"] if s["id"] == i][0]
def m(fn):
    def f():
        d = D.q41(); d["code_scan"] = dict(fail_open_handlers=0); fn(d); return d
    return f
H = [  # id, what, expected finding(s), change
 ("H01", "payment decided by the model 'for small amounts'", {"P01"}, lambda d: step(d, "pay").update(decided_by="model")),
 ("H02", "gate errors allow payment during a provider incident", {"P03"}, lambda d: step(d, "pay").update(on_gate_error="open")),
 ("H03", "payee account read from the invoice when the registry lacks one", {"P04"}, lambda d: step(d, "pay").update(destination_from="document")),
 ("H04", "the money gate removed for a 'trusted tenant'", {"P02"}, lambda d: step(d, "pay").update(gate=False)),
 ("H05", "a service token placed in the system prompt for convenience", {"P05", "A05"}, lambda d: d["credentials"].update(in_context=True)),
 ("H06", "one standing token reused across tasks", {"P05"}, lambda d: d["credentials"].update(per_task=False)),
 ("H07", "all tools offered on every task", {"P06"}, lambda d: d["tools"].update(loadout="all")),
 ("H08", "egress switched to a denylist of known-bad domains", {"P07"}, lambda d: d["egress"].update(mode="denylist")),
 ("H09", "reviewer shown a one-line summary to speed the queue", {"P08"}, lambda d: d["approvals"].update(render="summary")),
 ("H10", "approval no longer bound to the effect digest", {"P08"}, lambda d: d["approvals"].update(bound_to_effect=False)),
 ("H11", "MCP description pinning turned off after a noisy week", {"P09"}, lambda d: d["tools"].update(pinned=False)),
 ("H12", "pickle checkpoints accepted for a fine-tuned classifier", {"P09"}, lambda d: d["model_files"].update(refuse_code_formats=False)),
 ("H13", "agents switched to free-text messages", {"P10", "A12"}, lambda d: d["agents"].update(handoff="free_text")),
 ("H14", "memory labels dropped in a migration", {"P11"}, lambda d: d["memory"].update(trust_labels=False)),
 ("H15", "anchor service retired to save cost", {"P12"}, lambda d: d["evidence"].update(anchored=False)),
 ("H16", "repeat limit removed (a customer's long reconciliations)", {"P13"}, lambda d: d["budgets"].update(repeats=None)),
 ("H17", "bank feed outage disposition left blank", {"P14"}, lambda d: d["degradation"].update(bank_feed=None)),
 ("H18", "release gate anchor dropped", {"P15", "A09"}, lambda d: d["release_gate"].update(anchor=False, mode="margins")),
 ("H19", "release gate loosened with margins, anchor kept, new-hit rule off", {"A09"}, lambda d: d["release_gate"].update(mode="margins", new_hit_rule=False)),
 ("H20", "Ian leaves; his jobs keep his name as backup and owner", {"P16"}, lambda d: [j.update(backup=j["owner"]) for j in d["jobs"] if j["owner"] == "Ian" or j["backup"] == "Ian"]),
 ("H21", "a hardened prompt added to the list of controls", {"A01"}, lambda d: d["controls_claimed"].append(dict(name="hardened prompt", kind="prompt"))),
 ("H22", "classifier label 'approved vendor' lets a payment skip the hold", {"A02"}, lambda d: step(d, "pay").update(authority_from="model_label")),
 ("H23", "marker scan promoted from signal to control", {"A03"}, lambda d: d["scanners"][0].update(role="control")),
 ("H24", "extractor confidence used to auto-approve", {"A07"}, lambda d: d["monitors"][1].update(role="gate")),
 ("H25", "amount detector's owner leaves", {"A08"}, lambda d: d["monitors"][0].update(owner="")),
 ("H26", "detector alerts rise to 30 a week", {"A08"}, lambda d: d["monitors"][0].update(alerts_per_week=30)),
 ("H27", "baseline acknowledgement and retune dropped", {"A10"}, lambda d: d["baselines"][0].update(ack_days=None, retune_days=None)),
 ("H28", "a waiver granted with no review date", {"A11"}, lambda d: d["waivers"].append(dict(id="W09", owner="Kevin", review_day=None))),
 ("H29", "canary job's artefact becomes 'looked at it'", {"A13"}, lambda d: [j.update(evidence="looked at it") for j in d["jobs"] if j["id"] == "J16"]),
 ("H30", "sales deck says 'compliant with OWASP Agentic Top 10'", {"A14"}, lambda d: d["claims"].update(compliant_with=["ASI26"], evidence_levels=False)),
 ("H31", "report code runs with network for a chart library", {"P17"}, lambda d: step(d, "run_report_code").update(network=True)),
 ("H32", "incident case may close with deadline blank", {"P18"}, lambda d: d["incident"].update(blank_blocks_close=False)),
 # changes a sheet check is expected to miss: the sheet is unchanged or the harm is in a field the catalogue does not read
 ("H33", "new 'refund' effect added with its own path, not in EFFECTS", {"A15"}, lambda d: d["steps"].append(dict(id="refund", effect="refund", decided_by="model", gate=False, destination_from="document"))),
 ("H34", "registry made writable by the agent (sheet still says registry)", set(), lambda d: d.setdefault("registry", {}).update(writable_by_agent=True)),
 ("H35", "allow-list widened to *.com (sheet still says allowlist)", set(), lambda d: d["egress"].update(entries=["*.com"])),
 ("H36", "budget raised from 12 to 10,000 calls", set(), lambda d: d["budgets"].update(calls=10000)),
]
B = [
 ("B01", "a new read-only tool added to the loadout", lambda d: d["steps"].append(dict(id="lookup_rate", effect=None, decided_by="model"))),
 ("B02", "Kevin and Sophie swap two jobs", lambda d: [j.update(owner="Sophie", backup="Kevin") if j["id"] == "J21" else None for j in d["jobs"]]),
 ("B03", "detector alert rate falls to 0.5 a week", lambda d: d["monitors"][0].update(alerts_per_week=0.5)),
 ("B04", "a waiver with an owner and a date", lambda d: d["waivers"].append(dict(id="W10", owner="Sophie", review_day=330))),
 ("B05", "budget tightened to 8 calls", lambda d: d["budgets"].update(calls=8)),
 ("B06", "fourth agent added with typed hand-off", lambda d: d["agents"].update(count=4)),
]
def main():
    L = []; R = {"harmful": {}, "benign": {}, "code": {}}
    base = P.findings(P.check(m(lambda d: None)()))
    L.append(f"baseline Q41 findings: {base or 'none'}")
    caught = missed_expected = 0; blind = []
    for hid, what, exp, fn in H:
        f = set(P.findings(P.check(m(fn)())))
        ok = exp <= f if exp else None
        if exp: caught += bool(f & exp); missed_expected += not (f & exp)
        else: blind.append(hid)
        R["harmful"][hid] = dict(what=what, expected=sorted(exp), found=sorted(f), all_expected=ok)
        L.append(f"{hid} {what[:66]:66} expected {','.join(sorted(exp)) or '-':9} found {','.join(sorted(f)) or 'none'}")
    nexp = sum(1 for h in H if h[2])
    L.append(f"harmful with an expected finding: caught {caught} of {nexp}; missed {missed_expected}; outside what the sheet records: {len(blind)} ({', '.join(blind)}), found by the sheet check: {sum(bool(R['harmful'][h]['found']) for h in blind)}")
    fp = 0
    for bid, what, fn in B:
        f = P.findings(P.check(m(fn)())); fp += bool(f); R["benign"][bid] = dict(what=what, found=f)
        L.append(f"{bid} {what:66} found {','.join(f) or 'none'}")
    L.append(f"benign changes with any finding: {fp} of {len(B)}")
    # code changes in a temporary copy of the library
    tmp = Path(tempfile.mkdtemp()); shutil.copytree(here / "bulwark", tmp / "bulwark")
    pol = tmp / "bulwark" / "policy.py"; src = pol.read_text()
    variants = {
     "K1 broad handler in a check function returns True": src + "\n\ndef check_payee_fast(p):\n    try:\n        return p.payee_id in REGISTRY\n    except Exception:\n        return True\n",
     "K2 broad handler returns 'ALLOW' in a helper named fallback()": src + "\n\ndef fallback(p):\n    try:\n        return verdict(p)\n    except Exception:\n        return 'ALLOW'\n",
     "K3 broad handler passes inside authorize(), falls through to send": src + "\n\ndef authorize(p):\n    ok = False\n    try:\n        ok = strict(p)\n    except Exception:\n        pass\n    send(p)\n",
     "K4 handler catches ValueError and returns True": src + "\n\ndef check_amount(p):\n    try:\n        return int(p.amount) < LIMIT\n    except ValueError:\n        return True\n",
     "K5 debug path that sends without the gate": src + "\n\ndef debug_send(p):\n    return dispatch(p)\n",
     "K6 allow returned through a variable": src + "\n\ndef gate_ok(p):\n    try:\n        return strict(p)\n    except Exception:\n        v = True\n        return v\n",
    }
    base_n = P.scan_code(sorted((tmp / "bulwark").glob("*.py")))["fail_open_handlers"]; L.append(f"code scan on the unchanged library copy: {base_n} (Chapter 36's fail_mode switch)")
    for k, v in variants.items():
        pol.write_text(v); s = P.scan_code(sorted((tmp / "bulwark").glob("*.py")))
        R["code"][k] = s["fail_open_handlers"] - base_n; L.append(f"{k:66} new findings over the unchanged copy: {s['fail_open_handlers'] - base_n}")
    pol.write_text(src); shutil.rmtree(tmp)
    (here / "results/ch42_mutants.json").write_text(json.dumps(R, indent=1)); (here / "results/ch42_mutants.log").write_text("\n".join(L) + "\n"); print("\n".join(L))
if __name__ == "__main__": main()
