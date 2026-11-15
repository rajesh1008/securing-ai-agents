#!/usr/bin/env python3
"""Chapter 33, labs 1-3 (no model): replay the response to the first alert of each attack class in the Chapter 32 world (SIMULATED tenant and attacks; extractions are real Haiku outputs from Ch32).
Lab 1: scoping questions vs truth.  Lab 2: containment actions x response lag.  Lab 3: tampering with the exported evidence chain, with and without anchors.  Writes results/ch33_contain.json."""
import sys, json
from pathlib import Path
from collections import Counter, defaultdict
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
import ch32_detect as D
from bulwark.detect import merge, Budget, DetectConfig
from bulwark.incident import scope, contain, standing_hold, tamper_checks, Case, Decision, REVERSIBILITY
from bulwark.evidence import Vault, ChainLog
def main():
    obs, truth, info, counts = D.build_obs(); byid = {o.id: o for o in obs}
    al, _, _ = D.run(obs); m = sorted(merge(al), key=lambda a: (a.day, a.id)); res = {}
    classes = sorted({info[i]["cls"] for i in truth}); cls_ids = {c: {i for i in truth if info[i]["cls"] == c} for c in classes}
    # also: T2 real invoices of a tampered vendor paid to the attacker's account are in truth (loss = amount)
    first = {}
    for a in m:
        c = info[a.id]["cls"] if a.id in truth else None
        if c and c not in first: first[c] = a
    print("attack payments by class:", {c: len(v) for c, v in cls_ids.items()}, "loss", {c: sum(truth[i] for i in v) / 100 for c, v in cls_ids.items()})
    print("first caught alert by class:", {c: (a.id, a.day, a.detector) for c, a in first.items()}, "| no alert for:", [c for c in classes if c not in first])
    # Lab 1
    q = {}
    for c, a in first.items():
        sc = scope(byid[a.id], obs); row = {}
        for k, ids in sc.items():
            ids_auto = {i for i in ids if byid[i].route == "AUTO" and byid[i].paid_day is not None and byid[i].day >= byid[a.id].day - 0}  # same day or later
            hit = ids & cls_ids[c]; later = {i for i in cls_ids[c] if byid[i].day >= byid[a.id].day}
            row[k] = dict(size=len(ids), true_in_set=len(hit), class_total=len(cls_ids[c]), class_from_alert_on=len(later), true_later_in_set=len(ids & later), false_in_set=len(ids - cls_ids[c] - set()))
        q[c] = row
        print(f"\nLab 1 scope for {c} (alert {a.id} day {a.day}, vendor {a.id and byid[a.id].vendor}):")
        for k, r in row.items(): print(f"  {k:16s} size {r['size']:4d}  attack payments in set {r['true_in_set']:2d}/{r['class_total']:2d} (from alert day on: {r['true_later_in_set']}/{r['class_from_alert_on']})")
    res["scope"] = q
    # Lab 2
    t = {}
    for c, a in first.items():
        trig = byid[a.id]; sc = scope(trig, obs); chg_vendors = {byid[i].vendor for i in sc["changed_vendors"]}; t[c] = []
        print(f"\nLab 2 containment for {c} (trigger day {trig.day}); attack money in class ${sum(truth[i] for i in cls_ids[c]) / 100:,.0f}; all classes ${sum(truth.values()) / 100:,.0f}")
        for lag in (0, 2, 5):
            for act in REVERSIBILITY:
                r = contain(obs, {i: truth[i] for i in cls_ids[c]}, trig, act, lag, changed_vendors=chg_vendors); t[c].append(r)
                print(f"  lag {lag} {act:17s} (rev {REVERSIBILITY[act]}) prevented ${r['prevented'] / 100:9,.0f} gone ${r['gone'] / 100:9,.0f} remaining ${r['remaining'] / 100:9,.0f} | collateral {r['collateral_items']:3d} items ${r['collateral_cents'] / 100:10,.0f}")
    res["contain"] = t
    print("\nLab 2b standing rule (hold a payment to a destination that is new for the vendor until 3 have gone there), class T2, from the first T2 alert day")
    st = []; tr2 = {i: truth[i] for i in cls_ids["T2_registry_tamper"]}; d0 = byid[first["T2_registry_tamper"].id].day
    for lag in (0, 2, 5):
        for hc in (False, True):
            r = standing_hold(obs, tr2, d0 + lag, honour_confirmation=hc); r.update(lag=lag, honour_confirmation=hc); st.append(r)
            print(f"  lag {lag} honour_confirmation={hc!s:5} prevented ${r['prevented'] / 100:7,.0f} gone ${r['gone'] / 100:7,.0f} remaining ${r['remaining'] / 100:7,.0f} | collateral {r['collateral_items']} items ${r['collateral_cents'] / 100:,.0f}")
    res["standing"] = st
    # Lab 3
    v = Vault(b"ch33-lab-master", anchor_every=25); T = "quill_tenant"
    for o in obs: v.record(T, kind="decision", principal="pipeline", task=o.id.replace(":", "_")[:48], decision=o.route, route=o.route, tool="pay", ts=o.day)
    v.seal(T); ex = v.export(T); rows = ex["rows"]
    # the chain rows do not carry amount; edit the 'route' field for the first-scenario edit
    import bulwark.incident as I
    rows_copy = rows
    for r in rows_copy: r["amount"] = 0
    # rebuild hashes so that 'amount' is part of the chain (lab convenience): re-record with amount as an extra attribute is not allowed by the closed schema, so edit 'ts' instead
    for r in rows_copy: r.pop("amount")
    def edit_field(rs): rs[len(rs) // 2]["ts"] = 9999
    import copy, hashlib as h
    from bulwark.evidence import canon
    out = {}
    def rehash(rs, start=0):
        prev = rs[start - 1]["hash"] if start else "0" * 64
        for i in range(start, len(rs)):
            rs[i]["seq"] = i; rs[i]["prev"] = prev; rs[i]["hash"] = h.sha256(canon({k: x for k, x in rs[i].items() if k != "hash"})).hexdigest(); prev = rs[i]["hash"]
    def verdict(rs): ok, bad = ChainLog.verify_rows(rs); return dict(chain=ok, bad_row=bad, anchor=v.anchors.check(T, rs))
    flip = "REVIEW" if rows[len(rows) // 2]["decision"] == "AUTO" else "AUTO"
    r = copy.deepcopy(rows); r[len(r) // 2]["decision"] = flip; out["edit_row_keep_hash"] = verdict(r)
    r = copy.deepcopy(rows); del r[len(r) // 2]; out["delete_row_keep_hashes"] = verdict(r)
    r = copy.deepcopy(rows); r[len(r) // 2]["decision"] = flip; rehash(r, len(r) // 2); out["edit_row_rechain_to_end"] = verdict(r)
    r = copy.deepcopy(rows); del r[len(r) // 2]; rehash(r, 0); out["delete_row_rechain_all"] = verdict(r)
    r = copy.deepcopy(rows)[:-40]; out["truncate_last_40"] = verdict(r)
    r = copy.deepcopy(rows)[:-3]; out["truncate_last_3"] = verdict(r)
    from bulwark.evidence import Anchors
    a2 = Anchors(v.anchors._key); a2.store = [a for a in v.anchors.store if a["seq"] != len(rows) - 1]   # the same anchors without the final seal
    r = copy.deepcopy(rows)[:-3]; out["truncate_last_3_no_seal"] = dict(chain=ChainLog.verify_rows(r)[0], bad_row=None, anchor=a2.check(T, r))
    r = copy.deepcopy(rows); r[-2]["decision"] = "AUTO" if r[-2]["decision"] != "AUTO" else "REVIEW"; rehash(r, len(r) - 2); out["edit_last_2_rechain_no_seal"] = dict(chain=ChainLog.verify_rows(r)[0], bad_row=None, anchor=a2.check(T, r))
    print(f"\nLab 3 chain {len(rows)} rows, {len(v.anchors.store)} anchors (every 25 + seal), last anchor seq {v.anchors.last_seq(T)}")
    for k, x in out.items(): print(f"  {k:26s} chain_ok={x['chain']!s:5} bad_row={x['bad_row']} anchor={x['anchor']}")
    res["tamper"] = {k: dict(chain=x["chain"], bad_row=x["bad_row"], anchor=list(x["anchor"])) for k, x in out.items()}
    # Lab 4: the case file closes only when decisions have owners and sourced deadlines
    case = Case("INC-1", first[classes[0]].id, [dict(id=o.id, day=o.day, route=o.route) for o in obs[:50]], DetectConfig().digest())
    case.add(Decision("hold payments to account", "Sophie", "2026-01-09", "bank agreement s4.2", True)); case.add(Decision("notify bank of possible fraud", "Sophie", None, None))
    case.add(Decision("regulator notification assessed", "", "5 days", "VERIFY"))
    print("\nLab 4 case digest", case.digest(), "open:", case.open_questions(), "can_close", case.can_close())
    res["case"] = dict(digest=case.digest(), open=case.open_questions())
    json.dump(res, open(here / "results/ch33_contain.json", "w"), indent=1, default=str)
if __name__ == "__main__": main()
