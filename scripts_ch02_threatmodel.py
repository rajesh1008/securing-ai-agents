#!/usr/bin/env python3
"""Threat model as code: every threat needs a control and a test or an owning chapter; the declared tool list must equal the runtime registry."""
import json, sys
from pathlib import Path
here = Path(__file__).resolve().parent
sys.path.insert(0, str(here))
from scripts_ch02_registry import build

tm = json.loads((here / "threatmodel/quill_invoice.json").read_text())
problems, rows = [], []
for t in tm["threats"]:
    owned = t["status"].startswith("planned:")
    if not t["control"]: problems.append(f"{t['id']}: no control")
    if not owned and not t["test"]: problems.append(f"{t['id']}: implemented control with no test")
    rows.append((t["id"], t["stride"], t["title"], t["control"], t["status"]))

def tool_diff(registry):
    declared = set(tm["declared_tools"]); actual = {x["name"] for x in registry.inventory()}
    return sorted(actual - declared), sorted(declared - actual)

res = {}
for label, dbg in (("registry_with_debug_tool", True), ("registry_clean", False)):
    r = build(dbg)
    extra, missing = tool_diff(r)
    res[label] = {"undeclared_in_runtime": extra, "declared_but_absent": missing,
                  "ungated_privileged": r.ungated_privileged(), "build_passes": not extra and not missing and not r.ungated_privileged()}
res["threat_table_problems"] = problems
res["threat_counts"] = {"total": len(tm["threats"]),
                        "implemented": sum(1 for t in tm["threats"] if t["status"] == "implemented"),
                        "planned": sum(1 for t in tm["threats"] if t["status"].startswith("planned"))}
(here / "results/ch02_threatmodel.json").write_text(json.dumps(res, indent=1))
print("id  stride  control  status")
for r_ in rows: print(f"{r_[0]}  {r_[1]}  {r_[3]:<26} {r_[4]}")
print(json.dumps(res, indent=1))
sys.exit(0 if res["registry_clean"]["build_passes"] and not problems else 1)
