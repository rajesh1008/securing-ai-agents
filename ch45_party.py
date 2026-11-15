#!/usr/bin/env python3
"""Chapter 45, lab 1c (no model): the Harbour and Vale fix is itself a claim.  'Recipients must be parties named on the claim record' bounds send_correspondence only if no untrusted source can write the party list.
Two versions of the day-120 stage: AS BUILT (the list is writable from claimant email through the clerk's add-a-party step), CLERK GATED (adding a party needs an adjuster who sees the source document and a call-back to the number on the policy: the write path is a human gate on evidence, so the claimant email cannot write it)..
Writes results/ch45_party.log."""
import sys, copy
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
from bulwark.casestudy import *
import ch45_programmes as P
def stage(kind):
    p = P.D_fixed()
    p.stage = f"day 120, party list {kind}"
    for t in p.tools:
        if t.id == "send_correspondence":
            t.gates = [Gate("deterministic", "parties named on the claim record", True, writable_from=("claimant_email", "attachments") if kind == "as built" else ())] + [g for g in t.gates if g.kind != "deterministic" or not g.trusted_record]
    return p
def main():
    L = []
    for kind in ("as built", "clerk gated"):
        p = stage(kind); f = findings(p)
        L.append(f"{p.stage:42} unbounded paths {len(f)}: " + ("; ".join(f"{a}->{b} ({c})" for a, b, e, c in f) if f else "none"))
    (here / "results/ch45_party.log").write_text("\n".join(L) + "\n"); print("\n".join(L))
if __name__ == "__main__": main()
