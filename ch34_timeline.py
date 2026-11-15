#!/usr/bin/env python3
"""Chapter 34, lab 1 (no model): what can honestly be said, and how often does it have to be corrected?
Replays the Chapter 32 world (SIMULATED tenant and attacks).  For the first alert of each attack class, at lag 0/2/5 days, a notice states 'N payments are under review' where N is the size of
the scope set (the question Chapter 33 found best for that class) restricted to items that have arrived by then, and 'M payments have gone' = scoped items already paid.
Compare with the final truth.  Then run Chapter 34's corrections() between successive notices.  Writes results/ch34_timeline.json."""
import sys, json
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
import ch32_detect as D
from bulwark.detect import merge
from bulwark.incident import scope
from bulwark.disclosure import Fact, Claim, corrections, CONFIRMED, SUSPECTED
BEST = {"T1_inflated_booking": "same_vendor", "T2_registry_tamper": "same_account", "H7_label_confusion": "same_conflict", "T4_drift": "same_vendor"}
def main():
    obs, truth, info, counts = D.build_obs(); byid = {o.id: o for o in obs}
    al, _, _ = D.run(obs); m = sorted(merge(al), key=lambda a: (a.day, a.id)); res = {}
    classes = sorted({info[i]["cls"] for i in truth}); cls_ids = {c: {i for i in truth if info[i]["cls"] == c} for c in classes}
    first = {}
    for a in m:
        c = info[a.id]["cls"] if a.id in truth else None
        if c and c not in first: first[c] = a
    print("classes", {c: len(v) for c, v in cls_ids.items()}, "first alert", {c: (a.id, a.day) for c, a in first.items()})
    for c, a in first.items():
        trig = byid[a.id]; sc = scope(trig, obs); key = BEST.get(c) or "same_vendor"
        # the question is asked on day t: only items that have arrived by t exist
        rows = []; prev = None; prevfacts = None; corr_total = 0
        for lag in (0, 2, 5, 14):
            t = trig.day + lag
            ids = {i for i in sc[key] if byid[i].day <= t}
            sc_t = scope(trig, [o for o in obs if o.day <= t]); ids = sc_t[key] if key in sc_t else ids
            paid = {i for i in ids if byid[i].paid_day is not None and byid[i].paid_day <= t and byid[i].route == "AUTO"}
            attack_in = ids & cls_ids[c]; attack_all = cls_ids[c]; gone_attack = {i for i in attack_in if byid[i].paid_day is not None and byid[i].paid_day <= t}
            facts = {"n": Fact("n", f"{len(ids)} payments are under review", SUSPECTED, numbers=(str(len(ids)),)),
                     "g": Fact("g", f"{len(paid)} of them have been paid", CONFIRMED, numbers=(str(len(paid)),))}
            cl = [Claim(f"{len(ids)} payments are under review", ("n",)), Claim(f"{len(paid)} of them have been paid", ("g",))]
            corr = corrections(prev, facts, prevfacts) if prev else []
            if corr: corr_total += 1
            rows.append(dict(lag=lag, day=t, under_review=len(ids), paid_in_set=len(paid), attack_in_set=len(attack_in), attack_gone_in_set=len(gone_attack), class_total_final=len(attack_all), corrections_needed=len(corr)))
            print(f"  {c:22s} lag {lag:2d} (day {t}): under review {len(ids):3d}, paid {len(paid):3d}, attack payments inside {len(attack_in):2d} of final {len(attack_all):2d}; corrections to the previous notice: {len(corr)}")
            prev, prevfacts = cl, facts
        res[c] = dict(trigger=a.id, day=trig.day, key=key, rows=rows, notices_corrected=corr_total)
    json.dump(res, open(here / "results/ch34_timeline.json", "w"), indent=1)
if __name__ == "__main__": main()
