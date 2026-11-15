#!/usr/bin/env python3
"""Chapter 41, lab 1: the twelve-month rota.  Part A: the register of recurring jobs the earlier chapters created, written the first afternoon (every job to the security lead, backups where they came to mind), checked with Rota.issues().
Part B: the same jobs after one rebalancing pass; issues again, load per person, and a first-quarter schedule.  Part C: 400 synthetic years of absences (SIMULATED people; minutes per run are the author's estimates, not measurements)
under four arrangements: no backup/no alarm, alarm only, backup only, backup plus alarm.  No model calls.  Writes results/ch41_rota.json."""
import sys, json
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
from bulwark.rota import Job, Rota, simulate
S, K, SO, I, N = "security", "Kevin", "Sophie", "Ian", "Nina"
# id, name, chapter, owner_A, backup_A, owner_B, backup_B, minutes, evidence, cadence, trigger, per_year, grace
R = [
 ("J01", "alert queue review (weekly top alerts)", 32, S, K, S, K, 60, "alert log with disposition", 7, "", 0, 2),
 ("J02", "detector baselines and thresholds review; acknowledge known repricings", 32, S, "", K, S, 90, "baseline ledger entry", 91, "", 0, 14),
 ("J03", "open-budget check on degraded dependencies", 36, S, "", K, S, 10, "budget log line", 1, "", 0, 1),
 ("J04", "model fingerprint series check", 40, S, "", K, S, 5, "series point and step-alarm state", 1, "", 0, 1),
 ("J05", "model bill review date", 40, S, "", K, S, 45, "re-signed bill", 91, "", 0, 14),
 ("J06", "load-site scan failure follow-up", 40, S, "", K, S, 30, "scan result and decision", 0, "load_site_failure", 4, 0),
 ("J07", "trigger-list sweep on every alias move", 40, S, K, K, S, 120, "sweep result with the list", 0, "alias_move", 8, 0),
 ("J08", "training-data audit (own models only)", 40, S, "", K, SO, 180, "audit result", 182, "", 0, 21),
 ("J09", "examiner rehearsal and coverage release test", 39, S, "", S, SO, 240, "rehearsal record", 91, "", 0, 14),
 ("J10", "crosswalk as-of date and edition check", 37, S, "", S, I, 45, "crosswalk diff", 30, "", 0, 7),
 ("J11", "payload library refresh from research", 17, S, "", S, N, 120, "library version and diff", 30, "", 0, 7),
 ("J12", "red-team exercise against the current release", 29, S, "", N, S, 600, "findings register", 182, "", 0, 30),
 ("J13", "release bundle assembly and verify", 35, S, K, S, K, 90, "bundle and verify output", 0, "release", 12, 0),
 ("J14", "release bundle signature", 35, I, "", I, S, 20, "signed bundle", 0, "release", 12, 0),
 ("J15", "prompt release gate noise recalibration", 18, S, "", K, S, 120, "baseline runs", 91, "", 0, 14),
 ("J16", "canary replay glance", 31, S, K, K, S, 20, "canary report", 7, "", 0, 2),
 ("J17", "incident tabletop", 33, S, "", S, I, 180, "tabletop record", 182, "", 0, 21),
 ("J18", "disclosure template and contact list check", 34, S, "", SO, S, 60, "contact verification record", 182, "", 0, 21),
 ("J19", "credential and token rotation", 24, S, "", K, S, 60, "rotation record", 91, "", 0, 7),
 ("J20", "agent inventory and cards review", 38, S, "", SO, K, 60, "card diff", 91, "", 0, 14),
 ("J21", "tool manifest change review", 25, S, K, K, S, 30, "manifest diff and decision", 0, "manifest_change", 24, 0),
 ("J22", "egress allow-list review", 12, S, "", K, S, 60, "allow-list diff", 91, "", 0, 14),
 ("J23", "approval queue statistics review (rubber-stamp rate)", 10, S, "", SO, S, 45, "queue statistics note", 30, "", 0, 7),
 ("J24", "waiver expiry sweep", 18, S, "", S, I, 30, "waiver list with dates", 30, "", 0, 7),
 ("J25", "evidence retention purge and segment verification", 39, S, "", K, S, 90, "verification output", 91, "", 0, 14),
 ("J26", "dependency fault drill (degradation table)", 36, S, "", K, S, 120, "drill grid", 91, "", 0, 14),
 ("J27", "customer security questionnaire", 37, S, "", S, SO, 180, "answered questionnaire", 0, "questionnaire", 10, 0),
 ("J28", "memory store audit", 22, S, "", S, K, 60, "audit result", 91, "", 0, 14),
 ("J29", "new tenant isolation test", 28, S, "", K, S, 90, "tenancy test output", 0, "new_tenant", 12, 0),
 ("J30", "provider status and terms change review", 24, S, "", SO, K, 30, "dated note", 30, "", 0, 7),
]
EXC = {"J03": ("budget_opened", 12, 30), "J04": ("fingerprint_step_alarm", 6, 45)}   # rota C: the two daily glances become exception-only jobs: the machine checks daily, a person is paged when it fires
def build(which):
    o, b = (3, 4) if which == "A" else (5, 6)
    jobs = []
    for r in R:
        j = Job(r[0], r[1], r[2], r[o], r[b], r[7], r[8], r[9], r[10], r[11], r[12])
        if which == "C" and r[0] in EXC: t, n, m = EXC[r[0]]; j.cadence, j.trigger, j.per_year, j.minutes, j.grace = 0, t, n, m, 0
        jobs.append(j)
    return Rota(jobs, head=I, cap_minutes={I: 120, N: 200, SO: 300, K: 600, S: 600}, default_cap=480)
def summarise(rota):
    iss = rota.issues(); kinds = {}
    for k, w in iss: kinds[k] = kinds.get(k, 0) + 1
    return iss, kinds
def main():
    out = {}
    for which in "ABC":
        rt = build(which); iss, kinds = summarise(rt); load = {p: round(m) for p, m in sorted(rt.load().items())}
        print(f"\nrota {which}: {len(rt.jobs)} jobs, {sum(j.periodic() for j in rt.jobs)} periodic, {sum(not j.periodic() for j in rt.jobs)} triggered; issues {len(iss)} {kinds}")
        print("  minutes per 30-day month:", load, " total", sum(load.values()), "= %.1f hours" % (sum(load.values()) / 60))
        for k, w in iss:
            if k in ("OVERLOAD", "SINGLE_POINT"): print("   ", k, w)
        out[which] = dict(jobs=len(rt.jobs), issues=len(iss), kinds=kinds, load=load, issue_list=iss)
    rt = build("B"); sch = rt.schedule(0, 91); per_week = [0] * 13
    mins = {j.id: j.minutes for j in rt.jobs}
    for d, jid in sch: per_week[d // 7] += mins[jid]
    print("\nrota B first quarter: %d scheduled periodic runs; minutes per week" % len(sch), per_week)
    out["B"]["quarter_runs"] = len(sch); out["B"]["quarter_minutes_per_week"] = per_week
    print("\nsimulated years (400 each; absence start rate 0.04/mean-length per day per person, mean 8 days)")
    cases = {"A no backup, no alarm": ("A", False, False), "A alarm only": ("A", False, True), "B backup only": ("B", True, False), "B backup + alarm": ("B", True, True), "A with its own backups": ("A", True, False), "C backup only": ("C", True, False)}
    sim = {}
    for name, (w, ub, al) in cases.items():
        rt = build(w); rs = [simulate(rt, s, ub, al) for s in range(400)]
        runs = rs[0]["runs"]; ms = sorted(r["missed"] for r in rs); mean = sum(ms) / len(ms)
        sim[name] = dict(runs=runs, mean_missed=round(mean, 1), share=round(mean / runs, 4), p5=ms[20], p95=ms[379], mean_lag=round(sum(r["mean_lag"] for r in rs) / len(rs), 2))
        print(f"  {name:26s} runs/yr {runs}  missed mean {mean:6.1f} ({100*mean/runs:5.2f}%)  5th-95th pct {ms[20]}-{ms[379]}  mean lag {sim[name]['mean_lag']} days")
    out["simulation"] = sim
    rt = build("B"); rs = [simulate(rt, s, False, True, alarm_check=1) for s in range(400)]; ms = sorted(r["missed"] for r in rs)
    sim["A-style (no backup) with owners of B, daily alarm"] = dict(mean_missed=round(sum(ms) / 400, 1))
    print("  (rota B owners, no backup used, daily alarm instead of weekly): missed mean %.1f" % (sum(ms) / 400))
    json.dump(out, open(here / "results/ch41_rota.json", "w"), indent=1, default=str)

if __name__ == "__main__": main()
