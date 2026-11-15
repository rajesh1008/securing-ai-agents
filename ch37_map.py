#!/usr/bin/env python3
"""Chapter 37, lab 2 (no model): the author's crosswalk for the Bulwark bundle (18 controls: Ch35's 17 plus C18, degraded modes of Chapter 36), checked, counted, broken.
1 check the mapping against the catalogue.  2 coverage and gaps per standard.  3 where an item rests on one control, or only on controls that are `designed`/lab-simulated.  4 mutations: wrong item id, mixed edition,
a relation above the evidence, an applicability date, the sources read too long ago.  5 the 2023-24 / 2025 renumbering applied to the rows.  6 Chapter 36's drill grid carried into the rows that mention degraded modes.
Writes results/ch37_map.json and prints the log."""
import sys, json, copy, re
from pathlib import Path
from collections import Counter, defaultdict
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
import ch35_collect as B
from bulwark.crosswalk import Row, check, gaps, coverage, unmapped_controls, drift, rendered, LEVELS
from bulwark.crosswalk_data import CAT, rows, na_rows, EDN, STANDARDS
AS_OF = "2026-11-13"
LV = {c[0]: c[5] for c in B.CONTROLS}; LV["C18"] = "measured_in_simulation"
def tally(iss): return dict(sorted(Counter(k for k, _ in iss).items()))
def main():
    res = {}; R = rows(); NA = na_rows(); allr = R + NA
    print(f"mapping: {len(R)} rows from {len({r.control for r in R})} controls to {len({(r.std, r.item) for r in R})} distinct items in {len({r.std for r in R})} standards; {len(NA)} NA rows (author judged out of scope)")
    res["rows"] = len(R); res["na_rows"] = len(NA); res["distinct_items"] = len({(r.std, r.item) for r in R}); res["by_rel"] = dict(Counter(r.rel for r in R)); print("relations:", res["by_rel"])
    iss = check(allr, CAT, LV, as_of=AS_OF); res["check"] = tally(iss); print("1 check on the real mapping:", res["check"])
    for k, d in iss[:6]: print("    ", k, d)
    res["check_detail"] = iss
    print("controls with no non-NA row:", unmapped_controls(allr, LV)); res["unmapped_controls"] = unmapped_controls(allr, LV)
    # 2 coverage
    cov = coverage(allr, CAT); res["coverage"] = cov; g = gaps(allr, CAT); res["gaps"] = g
    for s, c in cov.items(): print(f"2 coverage {s}: items {c['items']:3}  mapped {c['mapped']:3}  NA with reason {c['na']:2}  empty {c['empty']:3}", "" if not g[s] or len(g[s]) > 12 else g[s])
    print("   rows to incomplete catalogues (EUAI, ATLS) have no coverage figure by design")
    # 3 support
    sup = defaultdict(list)
    for r in R: sup[(r.std, r.item)].append(r)
    single = [(k, v[0].control) for k, v in sup.items() if len({x.control for x in v}) == 1 and CAT.std[k[0]].complete]
    res["single_control_items"] = [f"{s}:{i} <- {c}" for (s, i), c in single]
    print("3 items of complete catalogues that rest on ONE control:", len(single), "of", len([1 for k in sup if CAT.std[k[0]].complete]), "mapped items"); print("   ", res["single_control_items"][:20])
    weak = []
    for (s, i), v in sup.items():
        if not CAT.std[s].complete: continue
        best = max(LEVELS.index(LV[x.control]) for x in v if x.rel in ("ADDRESSES", "EVIDENCE_FOR")) if any(x.rel in ("ADDRESSES", "EVIDENCE_FOR") for x in v) else -1
        if best < 0: weak.append(f"{s}:{i}")
    res["items_with_partial_only"] = weak; print("   items where every row is PARTIAL or ALIGNED_WITH (no control ADDRESSES it or is EVIDENCE_FOR it):", weak)
    per_ctrl = Counter(r.control for r in R); res["rows_per_control"] = dict(sorted(per_ctrl.items())); print("   rows per control:", dict(sorted(per_ctrl.items())))
    lvl = Counter(LV[r.control] for r in R); res["rows_by_level"] = dict(lvl); print("   rows by control claim level:", dict(lvl))
    # 4 mutations
    mut = {}
    r1 = copy.deepcopy(allr); r1.append(Row("C01", "LLM25", "LLM11", EDN["LLM25"], "ADDRESSES", "x")); r1.append(Row("C02", "I42K", "A.6.2.9", EDN["I42K"], "EVIDENCE_FOR", "x")); mut["invented ids (LLM11, A.6.2.9)"] = tally(check(r1, CAT, LV, as_of=AS_OF))
    r2 = rows({"LLM25": "2023-24 (v1.1)"}) + NA; mut["rows written against the 2023-24 edition, catalogue is 2025"] = tally(check(r2, CAT, LV, as_of=AS_OF))
    lv3 = dict(LV); lv3["C08"] = "designed"; lv3["C04"] = "designed"; mut["C04 and C08 downgraded to 'designed'"] = tally(check(allr, CAT, lv3, as_of=AS_OF))
    r4 = copy.deepcopy(allr); [setattr(x, "rel", "EVIDENCE_FOR") for x in r4 if x.std == "EUAI"]; mut["EU AI Act rows turned into EVIDENCE_FOR"] = tally(check(r4, CAT, LV, as_of=AS_OF))
    mut["same rows, as of 2027-12-03 (high-risk dates passed)"] = tally(check([x for x in r4], CAT, LV, as_of="2027-12-03"))
    mut["sources last read 120 days before"] = tally(check(allr, CAT, LV, as_of="2027-03-13"))
    r6 = copy.deepcopy(allr); r6[0].limit = ""; r6[5].title = "Tool Misuse"; mut["blank limit; title typed from memory"] = tally(check(r6, CAT, LV, as_of=AS_OF))
    res["mutations"] = mut
    for k, v in mut.items(): print("4", k, "->", v)
    # 5 renumbering
    ll = [r for r in R if r.std == "LLM25"]; d = drift(ll, CAT, CAT, "LLM25", "LLM23"); res["renumber"] = dict(rows=len(ll), same=d["same"], changed=d["changed"], gone=d["gone"], items=sorted({r.item for r in ll}))
    print(f"5 {len(ll)} LLM25 rows read against the 2023-24 list by id: same title {d['same']}, a different item {d['changed']}, id absent {d['gone']}")
    for c, i, a, b in d["detail"][:14]: print(f"    {c} {i}: '{a}' (2025) is '{b}' in 2023-24")
    res["renumber_detail"] = d["detail"]
    # 6 drill grid
    fl = json.load(open(here / "results/ch36_flap.json")); un = fl["untested"] if "untested" in fl else None
    grid = fl.get("untested") or {}; n_un = sum(len(v) for v in grid.values()) if isinstance(grid, dict) else len(grid)
    print("6 drill grid from Chapter 36: untested cells", n_un, "of 36")
    res["drill"] = dict(untested=n_un, total=36, drilled=36 - n_un)
    rr = [r for r in R if r.control == "C18"]; res["c18_sentences"] = [rendered(r, CAT, LV[r.control]) for r in rr]
    for s in res["c18_sentences"]: print("   ", s)
    # sample auditor sentences for three standards
    res["samples"] = [rendered(r, CAT, LV[r.control]) for r in R if (r.control, r.item) in (("C04", "LLM02"), ("C16", "Art14"), ("C03", "A.6.2.8"))]
    for s in res["samples"]: print("   ", s)
    # 7 the digest next to the bundle's
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from bulwark.bundle import sign, check_signature, bundle_digest
    from bulwark.crosswalk import digest
    import time
    now = time.time(); b = B.build(now); b.controls.append(B.Control("C18", "Degraded modes", "Ian Walsh", ("T06",), "table of modes", "measured_in_simulation", ("E22",))); pk = Ed25519PrivateKey.generate()
    d0 = digest(allr, CAT); s0 = sign(b, [], {}, pk, "Ian Walsh", "CISO", f"release bulwark-0.37; crosswalk digest {d0[:16]}", now)
    ok0 = check_signature(b, s0, pk.public_key())[0]; stated = s0["payload"]["statement"].split("digest ")[1]
    r2 = copy.deepcopy(allr); r2[0].limit += " (edited)"; d1 = digest(r2, CAT); r3 = copy.deepcopy(allr); r3[3].edition = "2023-24 (v1.1)"; d2 = digest(r3, CAT)
    res["digest"] = dict(signature_ok=ok0, mapping=d0[:16], after_limit_edit=d1[:16], after_edition_edit=d2[:16], stated_matches_unedited=stated == d0[:16], stated_matches_limit_edit=stated == d1[:16], stated_matches_edition_edit=stated == d2[:16], bundle_digest_unchanged=bundle_digest(b)[:16])
    print("7 signature over bundle verifies:", ok0, "| statement carries crosswalk digest", stated, "| matches unedited rows", stated == d0[:16], "| after a limit-sentence edit", stated == d1[:16], "| after an edition edit", stated == d2[:16], "| the bundle signature still verifies after either edit:", check_signature(b, s0, pk.public_key())[0])
    json.dump(res, open(here / "results/ch37_map.json", "w"), indent=1, default=list)
if __name__ == "__main__": main()
