#!/usr/bin/env python3
"""Chapter 38, lab 6 (no model): the Chapter 37 crosswalk with C19 (the agent boundary) added, and the Chapter 36 degradation table with a PEER role.
Part 1  Chapter 37's 63 rows + 13 rows for C19: checker issues, coverage per standard before and after, the ASI07 row rendered as the sentence an auditor reads, digest before/after, items resting on one control.
Part 2  the six agents as dependencies of the coordinator (role PEER): decide() for every (peer, fault, action class) and the drill that actually calls a stub peer through guarded() with each fault; and the fault the table cannot see (a peer that answers well-formed and wrong).
Writes results/ch38_crosswalk.json and .log."""
import sys, json, time
from collections import Counter, defaultdict
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
import ch35_collect as B
from bulwark.crosswalk import check, coverage, gaps, rendered, digest
from bulwark.crosswalk_data import CAT, rows, rows38, na_rows
from bulwark.degrade import Dependency, Role, decide, guarded, default_table, FAULTS, CLASSES, MONEY, SEND, DRAFT, READ, cells
AS_OF = "2026-11-13"; L = []; res = {}
LV = {c[0]: c[5] for c in B.CONTROLS}; LV["C18"] = "measured_in_simulation"; LV["C19"] = "measured_live_model"
def part1():
    old = rows() + na_rows(); new = rows38() + na_rows()
    for name, rr in (("Ch37 (63 rows, 18 controls)", old), ("Ch38 (76 rows, 19 controls)", new)):
        iss = check(rr, CAT, LV, as_of=AS_OF); c = Counter(k for k, _ in iss); cov = coverage(rr, CAT)
        L.append(f"{name}: checker {dict(c)}; coverage " + "; ".join(f"{s} {v['mapped']}/{v['items']} (+{v['na']} NA)" for s, v in cov.items() if s in ('LLM25', 'ASI26', 'N600', 'I42K')))
        res[name] = dict(issues=dict(c), coverage=cov, rows=len([r for r in rr if r.rel != 'NA']))
    g_old = gaps(old, CAT)["ASI26"]; g_new = gaps(new, CAT)["ASI26"]; L.append(f"ASI26 gaps before: {g_old}; after: {g_new}")
    sup = defaultdict(set)
    for r in rows38():
        if r.std in ("ASI26", "LLM25", "N600", "I42K"): sup[(r.std, r.item)].add(r.control)
    single = sorted(f"{s}:{i}" for (s, i), v in sup.items() if len(v) == 1); L.append(f"items resting on one control: {len(single)} of {len(sup)} mapped (Ch37: 18 of 32)")
    asi07 = [r for r in rows38() if r.item == "ASI07"][0]; L.append("ASI07 as rendered: " + rendered(asi07, CAT, LV["C19"]))
    L.append(f"digest Ch37 {digest(old, CAT)[:16]}  Ch38 {digest(new, CAT)[:16]}")
    by = Counter(r.rel for r in rows38() if r.control == "C19"); L.append(f"C19 rows by relation: {dict(by)}; ADDRESSES rows for C19: 0 (the weakest true word was chosen for ASI07)")
    res["asi07_row"] = rendered(asi07, CAT, LV["C19"]); res["single"] = single
PEERS = ["intake", "research", "comms", "payments", "bank", "verifier"]
def stub(fault):
    def f():
        if fault == "ERROR": raise RuntimeError("peer down")
        if fault == "TIMEOUT": time.sleep(0.4); return {"status": "CREDITED"}
        if fault == "MALFORMED": return None
        if fault == "STALE": return {"status": "CREDITED", "as_of": "2026-11-01"}
        if fault == "WRONG": return {"status": "CREDITED", "as_of": "2026-11-13"}      # well-formed, fresh, and false
        return {"status": "CREDITED", "as_of": "2026-11-13"}
    return f
def part2():
    deps = {p: Dependency(p, Role.PEER if p != "verifier" else Role.PREVENT, "ian") for p in PEERS}
    t = default_table(); L.append(f"default table: {len(t)} (role, class) cells, of which PEER {sum(1 for k in t if k[0] == 'PEER')}: " + ", ".join(f"{c}->{t[('PEER', c)].value}" for c in CLASSES))
    grid = []; wrong = []
    for p in PEERS:
        for f in FAULTS + ("WRONG",):
            r = guarded(stub(f), deadline=0.15, validate=lambda v: isinstance(v, dict) and "as_of" in v)
            st = "STALE" if r.ok and r.value["as_of"] < "2026-11-12" else r.status          # freshness is a check on the value, made by the caller; guarded() itself has no STALE
            for a in CLASSES:
                d, _ = decide(deps, {p: st}, a)
                grid.append((p, f, a, st, d.value))
    drilled = {(p, f) for p, f, *_ in grid if f != "WRONG"}; ok = sum(1 for p, f, a, st, d in grid if f != "WRONG" and st != "OK")
    L.append(f"drill: {len(PEERS)} peers x {len(FAULTS)} fault kinds = {len(cells(deps))} cells, all drilled through guarded(); statuses seen {dict(Counter(st for p, f, a, st, d in grid if f != 'WRONG' and a == MONEY))}")
    w = [(p, a, d) for p, f, a, st, d in grid if f == "WRONG"]; L.append(f"the WRONG fault (well-formed, fresh, false): status {set(st for p, f, a, st, d in grid if f == 'WRONG')} -> dispositions {dict(Counter(d for p, a, d in w))}: the table allows everything, as Chapter 36 said it would")
    pm = {(p, f): {a: d for p2, f2, a, st, d in grid if p2 == p and f2 == f} for p in PEERS for f in FAULTS}
    L.append("coordinator with comms down: " + str(pm[("comms", "ERROR")]) + "; with bank STALE: " + str(pm[("bank", "STALE")]) + "; with intake TIMEOUT: " + str(pm[("intake", "TIMEOUT")]))
    res["peer_grid"] = [list(g) for g in grid]; res["cells"] = len(cells(deps)); res["wrong_dispositions"] = dict(Counter(d for p, a, d in w))
if __name__ == "__main__":
    part1(); part2(); print("\n".join(L)); json.dump(dict(res, log=L), open(here / "results/ch38_crosswalk.json", "w"), indent=1, default=list); open(here / "results/ch38_crosswalk.log", "w").write("\n".join(L) + "\n")
