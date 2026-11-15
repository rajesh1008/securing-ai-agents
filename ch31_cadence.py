#!/usr/bin/env python3
"""Chapter 31, lab 5: the same candidate A (sibling review) on the same documents, with only the payment cadence changed.  Siblings are invoices of one vendor, same amount, both still open: how many
there are depends on how long invoices stay open, which is a property of the business and not of the control.  Writes results/ch31_cadence.json."""
import sys, json
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
import ch31_shadow as SH
CAD = {"every day": lambda d: d, "Tue and Fri": lambda d: d + min((1 - d) % 7, (4 - d) % 7), "weekly (Fri)": lambda d: d + ((4 - d) % 7), "every two weeks (Fri)": lambda d: d + ((4 - d) % 14)}
out = {}
for name, fn in CAD.items():
    SH.next_friday = fn; sa, sb, weekly, ph = SH.run(); t = sa.tally(); w = [weekly[k]["a_extra"] for k in sorted(weekly)][:12]
    out[name] = dict(live_auto=t["live_auto"], extra_holds=t["extra_holds"], rate=round(t["extra_holds"] / t["live_auto"], 3), worst_week=max(w), mean_week=round(sum(w) / 12, 1))
    print(name, out[name])
json.dump(out, open(here / "results/ch31_cadence.json", "w"), indent=1)
