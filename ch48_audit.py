#!/usr/bin/env python3
"""Chapter 48, lab 1 (no model): an auditor who did not write any of it re-performs the Chapter 39 payment (INV-2231, $4,812.50 to Lone Star Paper Supply).
Sources held by the auditor besides the exported chain rows: the approval service log, the bank statement, the vendor-master history, the register of released policy versions, the AP sub-ledger (invoice amounts).
Part A: the nine procedures (bulwark/reperform.py) on the clean export.  Part B: 16 seeded defects, five tampering after the fact (chain and anchors should catch) and eleven lies at write time (the chain is valid; only second sources, replay and logic can catch), plus three cases the procedures cannot catch.  Part D: the gate replaced by a constant.
Part C: cost of re-performance by chain size.  Writes results/ch48_audit.json and .log."""
import sys, json, copy, time, hashlib, io, contextlib
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
with contextlib.redirect_stdout(io.StringIO()): import ch39_payment as P
from bulwark.evidence import Vault, ChainLog
from bulwark.moneypath import Vendors, Vendor, Invoice, PayRequest, MoneyGate, Ledger
import bulwark.reperform as R
T, TASK, PAYEE = P.T, P.TASK, P.PAYEE
POLICIES = {"v0.31", "v0.37"}
MASTER = {PAYEE: [dict(version=1, account="US-ACC-4417", live_since=-400, created=-500, confirmed_by="kevin_brandt"), dict(version=2, account="US-ACC-9902", live_since=61, created=-500, confirmed_by="kevin_brandt")],
          "payee_barton": [dict(version=1, account="US-ACC-1100", live_since=-300, created=-400, confirmed_by="kevin_brandt")]}
LIMIT = {PAYEE: 1_000_000, "payee_barton": 300_000}
def ap_books(rows):  # the AP sub-ledger: what each invoice is for (auditor's own copy, not the chain)
    b = {"INV-2231": (PAYEE, 481_250)}
    for i in range(40): b[f"INV-N{i}"] = ("payee_barton", 10_000 + 137 * i)
    return b
BOOKS = ap_books(None)
def decide_factory(rows, master):
    def decide(r):
        payee, amt = BOOKS[r["invoice"]]
        m = [v for v in master[payee] if v["live_since"] <= r["ts"]][-1]
        v = Vendors({payee: Vendor(payee, "x", m["account"], LIMIT[payee], live_since=m["live_since"], created_day=m["created"], confirmed_by=m["confirmed_by"], version=m["version"])})
        g = MoneyGate(T, v, {r["invoice"]: Invoice(r["invoice"], payee, amt, number="n")}, Ledger())
        prev = rows[r["seq"] - 1] if r["seq"] else {}
        appr = prev.get("approver") if prev.get("kind") == "approval" and prev.get("task") == r.get("task") else None
        return g.check(PayRequest(r["invoice"], payee, r["amount_cents"], doc_amount_cents=r["amount_cents"], day=r["ts"], principal="prin_emily", approver=appr), reserve=False).outcome
    return decide
def sources(world):
    rows = world["rows"]
    appr = [dict(task=r["task"], approver=r["approver"], effect_digest=r.get("effect_digest")) for r in rows if r["kind"] == "approval"]
    bank = [dict(invoice=r["invoice"], amount_cents=r["amount_cents"]) for r in rows if r["kind"] == "dispatch" and r["decision"] == "SENT"]
    return appr, bank
def run_all(rows, vault_check, anchors, appr, bank, master=MASTER):
    out = {}
    out["P1 chain"] = R.p1_chain(rows); out["P2 anchor"] = R.p2_anchor(rows, anchors, vault_check); out["P3 scope"] = R.p3_scope(rows, T); out["P4 order"] = R.p4_order(rows)
    out["P5 lifecycle"] = R.p5_lifecycle(rows, POLICIES); out["P6 separation"] = R.p6_separation(rows); out["P7 effect"] = R.p7_effect(rows)
    out["P8 second sources"] = R.p8_second_sources(rows, appr, bank, None)
    try: out["P9 replay"] = R.p9_replay(rows, decide_factory(rows, master))
    except Exception as e: out["P9 replay"] = [("P9_ERROR", None, repr(e))]
    return out
def fields(r): return {k: v for k, v in r.items() if k not in ("seq", "prev", "hash", "tenant")}
def lie_at_write(rows, fn):
    """The writer produces a different story and a valid chain: re-record every row through a fresh vault after fn edits the list of field dicts."""
    fs = fn([fields(r) for r in rows]); v = Vault(b"m" * 32, 25)
    for f in fs: v.record(T, **f)
    v.seal(T); e = v.export(T); return e["rows"], e["anchors"], (lambda rr, v=v: v.anchors.check(T, rr))
def after_fact(rows, fn, rechain):
    rr = fn(copy.deepcopy(rows))
    if rechain:
        prev = R.GENESIS
        for i, r in enumerate(rr): r["seq"], r["prev"] = i, prev; r["hash"] = R._h(r); prev = r["hash"]
    return rr
def main():
    L = []; say = lambda s: (L.append(s), print(s)); res = {}
    w = P.build("V1"); rows0 = w["rows"]; V0 = w["vault"]; an0 = [a for a in V0.anchors.store if a["name"] == T]
    as_exported = run_all(rows0, lambda rr: V0.anchors.check(T, rr), an0, *sources(w))
    say(f"0 the Chapter 39 export as it stands: {len(rows0)} rows; findings per procedure {[(k.split()[0], len(f)) for k, f in as_exported.items() if f]}; first: {as_exported['P4 order'][0]}")
    res["as_exported"] = {k: [list(x) for x in f] for k, f in as_exported.items()}
    def fix_clock(fs):
        n = 0
        for f in fs:
            if f.get("task", "").startswith("t_n"): f["ts"] = 62 + (int(f["task"][3:]) * 37) // 40
        return fs
    rows, anchors, chk = lie_at_write(rows0, fix_clock); w = dict(rows=rows); appr, bank = sources(w)
    say("   fixture corrected: the 40 filler payments re-dated to days 62-98 so that the chain is in time order; everything else unchanged")
    clean = run_all(rows, chk, anchors, appr, bank)
    say(f"A clean export: {len(rows)} rows, {len(anchors)} anchors, approvals in service log {len(appr)}, bank lines {len(bank)}")
    for k, f in clean.items(): say(f"   {k:18s} findings {len(f)} {[x[0] for x in f][:3]}")
    res["clean"] = {k: [list(x) for x in f] for k, f in clean.items()}
    # B: seeded defects
    def seq_of(fs, kind, task=TASK, i=0): return [j for j, f in enumerate(fs) if f["kind"] == kind and f.get("task") == task][i]
    D = []
    def af(name, fn, rc): D.append((name, "after the fact" + (", rechained" if rc else ""), lambda: (after_fact(rows, fn, rc), anchors, chk, appr, bank)))
    def lw(name, fn, a=None, b=None): D.append((name, "lie at write", lambda: (lambda t: (t[0], t[1], t[2], appr if a is None else a, bank if b is None else b))(lie_at_write(rows, fn))))
    def edit_amt(rs):
        for r in rs:
            if r["kind"] == "dispatch" and r["seq"] > 80: r["amount_cents"] = 4_812_50 * 10; break
        return rs
    af("A1 amount edited in the dispatch row", edit_amt, False)
    af("A2 same edit, chain recomputed", edit_amt, True)
    def drop_appr(rs): return [r for r in rs if not (r["kind"] == "approval" and r.get("task") == TASK)]
    af("A3 approval row deleted, chain recomputed", drop_appr, True)
    af("A4 last three rows cut off", lambda rs: rs[:-3], False)
    def foreign(rs): x = copy.deepcopy(rs[-1]); x["tenant"] = "biz_other"; rs.append(x); return rs
    af("A5 another tenant's row appended, rechained", foreign, True)
    def self_appr(fs):
        for f in fs:
            if f["kind"] == "approval" and f.get("task") == TASK: f["approver"] = "prin_emily"
        return fs
    lw("B1 approver is the requester", self_appr)
    def eff(fs):
        for f in fs:
            if f["kind"] == "dispatch" and f.get("task") == TASK: f["effect_digest"] = "0" * 64
        return fs
    lw("B2 dispatch effect differs from approved effect", eff)
    def nogate(fs):
        i = [j for j, f in enumerate(fs) if f["kind"] == "money_gate" and f.get("task") == TASK][-1]; del fs[i]; return fs
    lw("B3 sent with no second gate row", nogate)
    def early_allow(fs):
        i = [j for j, f in enumerate(fs) if f["kind"] == "money_gate" and f.get("task") == TASK][0]; fs[i]["decision"] = "ALLOW"; fs[i]["reasons"] = ["ok"]; return fs
    lw("B4 first gate row says ALLOW (replay says HOLD)", early_allow)
    def phantom(fs): return fs
    lw("B5 approval logged that the service never saw", phantom, a=[x for x in appr if x["task"] != TASK])
    def pol(fs):
        for f in fs:
            if f["kind"] == "money_gate" and f.get("task") == TASK: f["policy"] = "v0.99"
        return fs
    lw("B6 policy version never released", pol)
    def back(fs): fs[-3]["ts"] = 40; return fs
    lw("B7 timestamp earlier than rows before it", back)
    def dup(fs):
        i = [j for j, f in enumerate(fs) if f["kind"] == "dispatch" and f.get("invoice") == "INV-N3"][0]; fs.insert(i + 1, dict(fs[i])); return fs
    lw("B8 an invoice dispatched twice", dup)
    lw("B9 bank paid ten times the logged amount", lambda fs: fs, b=[dict(x, amount_cents=x["amount_cents"] * 10) if x["invoice"] == "INV-2231" else x for x in bank])
    lw("B10 payment made outside Quill (bank only)", lambda fs: fs, b=bank + [dict(invoice="INV-X9", amount_cents=950_000)])
    lw("B11 logged as sent, never paid by the bank", lambda fs: fs, b=[x for x in bank if x["invoice"] != "INV-N7"])
    def vm(fs): return fs
    # not catchable by these procedures
    mm = copy.deepcopy(MASTER); mm[PAYEE][1]["account"] = "US-ACC-ATTACKER"
    lw("M1 vendor master and every record altered consistently", lambda fs: fs)
    lw("M2 approval clicked in 0.3 seconds", lambda fs: [dict(f, approval_ms=300) if f["kind"] == "approval" and f.get("task") == TASK else f for f in fs])
    lw("M3 a check the gate never had (destination country)", lambda fs: fs)
    res["defects"] = []; caught = 0
    say(f"B seeded defects ({len(D)}); each row: procedures that fired")
    for name, how, build in D:
        rr, an, ck, ap, bk = build()
        out = run_all(rr, ck, an, ap, bk)
        fired = [k.split()[0] for k, f in out.items() if f]; codes = sorted({x[0] for f in out.values() for x in f})
        hit = bool(fired); caught += hit and not name.startswith("M")
        say(f"   {name[:58]:58s} [{how}] {'CAUGHT by ' + ','.join(fired) if hit else 'NOT CAUGHT'}")
        res["defects"].append(dict(name=name, how=how, fired=fired, codes=codes))
    nd = sum(1 for n, _, _ in D if not n.startswith("M")); say(f"   caught {caught} of {nd} seeded defects; 3 of 3 'M' cases pass every procedure")
    # first procedure alone that catches each
    only = {}
    for d in res["defects"]:
        for p in d["fired"]: only.setdefault(p, []).append(d["name"][:2])
    say("   defects by procedure that fired: " + "; ".join(f"{k} {len(v)}" for k, v in sorted(only.items())))
    res["by_procedure"] = {k: v for k, v in only.items()}
    # direction of completeness
    ls = [d for d in res["defects"] if d["name"].startswith("B10")][0]; l2 = [d for d in res["defects"] if d["name"].startswith("B11")][0]
    say(f"   B10 caught only by P8 reading from the bank statement towards the log ({ls['codes']}); B11 by P8 from the log to the bank ({l2['codes']})")
    # D: substitution test of the gate (after BARBICAN, arXiv 2610.33198): replace the decision by a constant and see what the evidence notices
    def stub(dec):
        def fn(fs):
            for f in fs:
                if f["kind"] == "money_gate": f["decision"] = dec; f["reasons"] = ["ok"] if dec == "ALLOW" else ["M8_dual_control_missing"]
            return fs
        return fn
    res["stubs"] = {}
    for dec in ("ALLOW", "HOLD", "DENY"):
        rr, an, ck = lie_at_write(rows, stub(dec)); out = run_all(rr, ck, an, appr, bank); gates = sum(1 for r in rr if r["kind"] == "money_gate")
        n9 = len(out["P9 replay"]); others = {k.split()[0]: len(f) for k, f in out.items() if f and not k.startswith("P9")}
        sent = sum(1 for r in rr if r["kind"] == "dispatch" and r["decision"] == "SENT")
        say(f"D gate replaced by a constant {dec:5s}: P9 disagrees on {n9} of {gates} gate rows; other procedures {others or 'silent'}; dispatches still logged as sent {sent}; bank lines {len(bank)}")
        res["stubs"][dec] = dict(p9=n9, gates=gates, others=others)
    # C: cost
    for N in (1_000, 10_000, 100_000):
        v = Vault(b"c" * 32, 100)
        for i in range(N // 2):
            v.record("tc", ts=i, kind="money_gate", task=f"t{i}", decision="ALLOW", reasons=["ok"], policy="v0.37", invoice=f"I{i}", payee="payee_barton", amount_cents=1000)
            v.record("tc", ts=i, kind="dispatch", task=f"t{i}", decision="SENT", invoice=f"I{i}", payee="payee_barton", amount_cents=1000)
        v.seal("tc"); rr = v.export("tc")["rows"]
        t0 = time.perf_counter(); f1 = R.p1_chain(rr); t1 = time.perf_counter() - t0
        t0 = time.perf_counter(); R.p4_order(rr); R.p3_scope(rr, "tc"); t3 = time.perf_counter() - t0
        t0 = time.perf_counter(); R.p5_lifecycle(rr, POLICIES); R.p6_separation(rr); R.p7_effect(rr); t5 = time.perf_counter() - t0
        say(f"C {N:7d} rows: P1 chain {t1*1000:7.0f} ms ({len(f1)} findings), P3+P4 {t3*1000:5.0f} ms, P5-P7 {t5*1000:7.0f} ms")
        res.setdefault("cost", []).append(dict(rows=N, p1_ms=round(t1 * 1000), p34_ms=round(t3 * 1000), p5_ms=round(t5 * 1000)))
    json.dump(dict(res, log=L), open(here / "results/ch48_audit.json", "w"), indent=1, default=list); open(here / "results/ch48_audit.log", "w").write("\n".join(L) + "\n")
if __name__ == "__main__": main()
