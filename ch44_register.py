#!/usr/bin/env python3
"""Chapter 44, lab 1 (no model): check the decision-rights register for Quill.  DRAFT (as reconstructed from Chapters 1-43), REV1 (first fix), REV2 (spread), REVISED (REV2 plus deputies).
The deputy check was added after the departure test on REV2; the log shows each register under the checks without it and with it.  Writes results/ch44_register.json and .log."""
import sys, json
from collections import Counter
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
import ch44_org as O
def main():
    L = []; R = {}
    for name, f in (("DRAFT", O.draft), ("REV1", O.rev1), ("REV2", O.rev2), ("REVISED", O.revised)):
        r = f(); r.check_deputy = False; a = r.issues(); r.check_deputy = True; b = r.issues()
        R[name] = dict(without_deputy_check=a, with_deputy_check=b)
        L.append(f"{name}: {len(a)} issues without the deputy check, {len(b)} with it; " + ", ".join(f"{k} {n}" for k, n in Counter(k for k, _ in b).most_common()))
        if name == "DRAFT":
            for k, v in b:
                if k not in ("JOB_PERSON_NOT_A_PERSON", "NO_DEPUTY"): L.append(f"   {k:26} {v}")
            L.append(f"   ({sum(k == 'JOB_PERSON_NOT_A_PERSON' for k, _ in b)} JOB_PERSON_NOT_A_PERSON: jobs owned or backed up by 'security'; {sum(k == 'NO_DEPUTY' for k, _ in b)} NO_DEPUTY, listed in the json)")
        if name in ("REV1",): L.append("   " + "; ".join(f"{k} {v}" for k, v in a))
    load = Counter(); r = O.revised()
    for d in r.decisions: load[d.accountable] += 1
    for c, o in r.controls.items(): load[o] += 1
    L.append("REVISED accountable decisions plus owned controls: " + ", ".join(f"{k} {v}" for k, v in load.most_common()) + f" (concentration line {r.k_concentration})")
    for w in ("Rajesh", "Kevin", "Ian"):
        for name, f in (("REV2", O.rev2), ("REVISED", O.revised)):
            d = f().depart(w); R[f"depart_{w}_{name}"] = d
            L.append(f"depart {w:6} from {name:7}: decisions with nobody to take them {len(d['decisions'])} {d['decisions']}; to deputy {len(d['decisions_to_deputy'])}; controls needing a new owner {len(d['controls'])} {d['controls']}; jobs to backup {len(d['jobs_to_backup'])}; jobs orphaned {len(d['jobs_orphaned'])}")
    dep = Counter(O.DEPUTY.values()); L.append("deputy load in REVISED: " + ", ".join(f"{k} {v}" for k, v in dep.most_common()))
    for k in ("D05", "D07", "D12", "ZZ"):
        L.append(f"route({k}) -> {r.route(k)}")
    (here / "results/ch44_register.json").write_text(json.dumps(R, indent=1, default=str)); (here / "results/ch44_register.log").write_text("\n".join(L) + "\n"); print("\n".join(L))
if __name__ == "__main__": main()
