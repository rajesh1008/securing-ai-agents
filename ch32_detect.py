#!/usr/bin/env python3
"""Chapter 32, lab 1-3: run the detectors of bulwark/detect.py over the Chapter 31 tenant with the injected attacks of ch32_world.py (SIMULATED traffic and attacks, real extractions).
Production route = candidate B (loosening shipped); the old pipeline (Chapter 31 LIVE) keeps deciding silently as the reverse shadow.  Detectors see only Obs fields.
Writes results/ch32_detect.json.  No model calls."""
import sys, json, random
from pathlib import Path
from collections import Counter, defaultdict
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
import ch14_live_extract as X
import ch31_shadow as SH, ch31_rollout as R
from bulwark.docagent import Document, Records, parse_rules
from bulwark.autoredteam import Envelope
from bulwark.detect import *
W = json.load(open(here / "results/ch32_world.json")); V = SH.V
def timeline():
    # legit-change vendors: later real invoices use the regenerated doc (same id + 'R')
    regen_by = defaultdict(dict)
    for e in W["regenerated"]: regen_by[e["id"]] = e
    out = []
    for e in SH.EV:
        out.append(regen_by.get(e["id"], e))
    for e in W["injected"]: out.append(dict(e, channel="vendor_mailbox", kind="inj"))
    for it in R.build_burst()["items"]:
        d = (it["week"] - 1) * 7 + (int(it["id"][1:]) % 3) * 2 + 1
        out.append(dict(it, day=d, arrive=d, kind="burst", acct=None))
    out.sort(key=lambda e: (e["arrive"], e["id"])); return out
def registry_at(pid, t):
    acct = V[pid]["account"]
    for c in W["changes"]:
        if c["pid"] == pid and c["day"] <= t: acct = c["new"]
    return acct
def build_obs(seed=3203):
    rng = random.Random(seed); obs = []; truth = {}; info = {}; seen_change = set(); counts = Counter()
    for e in timeline():
        t = e["arrive"]; pid = e["pid"]; acct = registry_at(pid, t)
        books = Records({pid: dict(name=V[pid]["name"], account=acct)}, {"X": dict(payee_id=pid, number=e["number"], amount_cents=e["amount"], status="open")})
        doc = Document(e["id"], e["visible"], e["hidden"]); ex = X.to_ex(e["ex"]) if e["ex"] else None
        reg = sorted(SH.REG[pid])[0]; env = Envelope(reg, reg if (not e.get("hostile") or e.get("channel", "vendor_mailbox") == "vendor_mailbox") else SH.STRANGER)
        route, old = SH.CAND_B(doc, ex, env, books), SH.LIVE(doc, ex, env, books)
        conflict = None
        if route == "AUTO" and old != "AUTO":
            exv = parse_rules(doc.visible); conflict = "PARSER_ABSTAIN" if (exv is None or exv.amount_cents is None) else "PARSER_CONFLICT"
        ready = t if route == "AUTO" else t + rng.randrange(2, 7); paid = next_friday(ready) if (route == "AUTO" or not e.get("hostile") and e.get("kind") not in ("inj", "burst")) else None
        conf = None
        for c in W["changes"]:
            if c["pid"] == pid and c["day"] <= t and (pid, c["day"]) not in seen_change: seen_change.add((pid, c["day"])); conf = c["confirmed"]
        o = Obs(e["id"], t, pid, e["amount"], acct, route, (), old, conflict, conf, paid); obs.append(o)
        cls = e.get("cls") if e.get("kind") in ("inj", "burst") else None
        if cls is None and any(c["kind"] == "tamper" and c["pid"] == pid and c["day"] <= t for c in W["changes"]): cls = "T2_registry_tamper"   # a real invoice of a tampered vendor is paid to the attacker's account if it goes AUTO
        info[e["id"]] = dict(cls=cls, hostile=bool(e.get("hostile")))
        if cls:
            counts[(cls, route)] += 1
            if route == "AUTO": truth[e["id"]] = 0 if cls.startswith("H7") else e["amount"]
    return obs, truth, info, counts
def run(obs, frozen=True, which=("amount", "account", "reverse", "run"), anchor=None):
    A = AmountDetector(frozen=frozen, anchor=anchor); Ac = AccountDetector(); Rs = ReverseShadow(); Rn = RunDetector(); al = []
    for o in obs:
        for nm, d in (("amount", A), ("account", Ac), ("reverse", Rs), ("run", Rn)):
            if nm in which and (a := d.see(o)): al.append(a)
    return al, A, Rs
def per_class(alerts, truth, info):
    got = {a.id for a in alerts}; d = defaultdict(lambda: [0, 0])
    for i in truth: d[info[i]["cls"]][1] += 1; d[info[i]["cls"]][0] += i in got
    return {k: f"{v[0]}/{v[1]}" for k, v in sorted(d.items())}
CAD = {"online": lambda a: a.day - 0.5, "nightly": lambda a: a.day + 1, "weekly_monday": lambda a: a.day + (7 - a.day % 7)}
def main():
    obs, truth, info, counts = build_obs(); O = {o.id: o for o in obs}; out = {}
    print("injected/escape routes (class, route): count", dict(counts)); out["counts"] = {f"{k[0]}|{k[1]}": v for k, v in counts.items()}
    print("truth items", len(truth), "loss cents", sum(truth.values()), "benign events", sum(1 for i in info.values() if not i['cls']))
    out["truth_n"] = len(truth); out["truth_loss"] = sum(truth.values())
    # lab 1: each detector alone and all merged; frozen vs adaptive baseline
    res = {}
    for name, which, fr in [("amount(frozen)", ("amount",), True), ("amount(adaptive)", ("amount",), False), ("account", ("account",), True), ("run", ("run",), True), ("reverse_shadow", ("reverse",), True), ("all(frozen)", ("amount", "account", "reverse", "run"), True), ("all(adaptive)", ("amount", "account", "reverse", "run"), False)]:
        al, A, Rs = run(obs, fr, which); al = merge(al)
        r = score(al, truth, O, reach=CAD["online"]); r["per_class"] = per_class(al, truth, info); r["false_per_week"] = round(r["false_alerts"] / 12, 2); res[name] = r
        print(f"{name:18s} caught {r['caught']}/{r['n_truth']} alerts {r['alerts']} false {r['false_alerts']} ({r['false_per_week']}/wk) precision {r['precision']:.2f} {r['per_class']}")
    for an in (4, 6, 8):
        al_, A_, _ = run(obs, True, ("amount",), anchor=an); al_ = merge(al_); r = score(al_, truth, O, reach=CAD["online"]); r["per_class"] = per_class(al_, truth, info); r["false_per_week"] = round(r["false_alerts"] / 12, 2); res[f"amount(anchor={an})"] = r
        print(f"amount(anchor={an})".ljust(18), f"caught {r['caught']}/{r['n_truth']} alerts {r['alerts']} false {r['false_alerts']} ({r['false_per_week']}/wk) {r['per_class']}")
    out["detectors"] = res
    al, A, Rs = run(obs); out["amount_silent"] = A.silent; out["reverse_kind_counts"] = Rs.counts; print("amount cold-start silent obs", A.silent, "of", len(obs), "| reverse-shadow disagreement kinds", Rs.counts)
    al = merge(al); out["alerts_all"] = [a.__dict__ for a in al]
    # lab 2: cadence -> money paid before anyone knew
    cad = {}
    for k, f in CAD.items():
        r = score(al, truth, O, reach=f); cad[k] = dict(in_time=r["in_time"], caught=r["caught"], loss_paid_before_alert=r["loss_paid_before_alert"], median_days_to_alert=r["median_days_to_alert"]); print("cadence", k, cad[k])
    none = score([], truth, O); cad["no_detection"] = dict(loss_paid_before_alert=none["loss_paid_before_alert"]); out["cadence"] = cad; print("no detection: loss paid", none["loss_paid_before_alert"])
    # lab 3: alert budget
    bud = {}
    for cap in (2, 4, 6, 10, 1000):
        kept, shed = Budget(cap).apply(al); r = score(kept, truth, O, reach=CAD["online"]); bud[cap] = dict(kept=len(kept), shed=len(shed), caught=r["caught"], false=r["false_alerts"], missed_in_shed=sum(1 for a in shed if a.id in truth)); print("budget", cap, bud[cap])
    out["budget"] = bud
    # false alerts by detector
    fa = Counter(a.detector for a in al if a.id not in truth); out["false_by_detector"] = dict(fa); print("false alerts by detector", dict(fa))
    # the online Monitor must reproduce the manual run exactly
    mon = Monitor(DetectConfig()); [mon.see(o) for o in obs]; same = sorted(a.id for a in mon.log) == sorted(a.id for a in al); shown, shed = mon.weekly_view()
    out["monitor"] = dict(config_digest=DetectConfig().digest(), alerts=len(mon.log), same_as_manual=same, shown=len(shown), shed=len(shed)); print("monitor", out["monitor"])
    # lab 4: rate detector on the disagreement indicator vs kind-split
    cal = [o for o in obs if o.day < 28 and o.route == "AUTO"]; live = [o for o in obs if o.day >= 28 and o.route == "AUTO"]; first_burst = min(o.day for o in obs if info[o.id]["cls"] and info[o.id]["cls"].startswith("H7"))
    streams = {"any_disagreement": lambda o: int(o.old_route is not None and o.old_route != "AUTO"), "conflict_kind_only": lambda o: int(o.conflict == "PARSER_CONFLICT")}
    out["cusum"] = {}
    for sn, ind in streams.items():
        p0 = max(sum(map(ind, cal)) / len(cal), 0.5 / len(cal)); out["cusum"][sn] = dict(p0=round(p0, 4), calibration_n=len(cal), first_burst_day=first_burst)
        for mult in (1.5, 2.0, 4.0):
            p1 = min(p0 * mult, 0.9)
            for h in (3.0, 5.0):
                c = Cusum(p0, p1, h); fired = None; nfire = None
                for k, o in enumerate(live):
                    if c.see(ind(o), o.day): fired = o.day; nfire = k + 1; break
                a = arl0(p0, p1, h, runs=400)
                out["cusum"][sn][f"x{mult},h={h}"] = dict(p1=round(p1, 4), fired_day=fired, decisions_to_fire=nfire, arl0_obs=round(a)); print("cusum", sn, f"p0={p0:.4f} p1={p1:.4f} h={h} fired day", fired, "after", nfire, "AUTO decisions | ARL0", round(a), "| burst starts day", first_burst)
    # reverse-shadow timing on the burst
    bur = [a for a in al if info[a.id]["cls"] and info[a.id]["cls"].startswith("H7")]; print("burst items alerted", len(bur), "of 12; detectors", Counter(a.detector for a in bur))
    out["burst_alerted"] = len(bur)
    t2 = [o for o in obs if info[o.id]["cls"] == "T2_registry_tamper"]; inj_ids = {e["id"] for e in W["injected"]}
    out["t2"] = dict(attacker_invoices_paid=sum(o.id in inj_ids and o.route == "AUTO" for o in t2), real_invoices_paid_to_new_account=sum(o.id not in inj_ids and o.route == "AUTO" for o in t2), real_invoices_held=sum(o.id not in inj_ids and o.route != "AUTO" for o in t2))
    print("T2:", out["t2"])
    json.dump(out, open(here / "results/ch32_detect.json", "w"), indent=1, default=str)
if __name__ == "__main__": main()
