#!/usr/bin/env python3
"""Chapter 44, lab 2 (no model; SIMULATED): a year of security decisions under three ways of owning them.
CENTRAL: every decision goes to the security lead, no deputy.  NEAREST: the draft register reconstructed from the chapters (owners as the text implies, no deputies, its own timeout rules).
REGISTER: the revised register (accountable, deputy, deadline, timeout rule).  Each also run with the security lead away for six weeks (days 180-221).
Arrival rates, hours per decision and weekly decision hours per person are the author's estimates; absences are drawn as in Chapter 41.  Nothing here is a measurement of a real organisation.
Writes results/ch44_decisions.json and .log."""
import sys, json, random, statistics, copy
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
import ch44_org as O
RATE = {"D01": 12, "D02": 24, "D03": 18, "D04": 6, "D05": 20, "D06": 2, "D07": 24, "D08": 10, "D09": 12, "D10": 3, "D11": 30, "D12": 30, "D13": 26, "D14": 4, "D15": 6}   # per year
HOURS = {"D01": 3, "D02": 1.5, "D03": 2, "D04": 3, "D05": 2, "D06": 6, "D07": 1.5, "D08": 0.5, "D09": 3, "D10": 2, "D11": 6, "D12": 0.5, "D13": 0.5, "D14": 4, "D15": 5}
CAP = {"Rajesh": 6, "Ian": 3, "Kevin": 2, "Sophie": 2, "Emily": 2, "Maya": 1, "Daniel": 1}   # hours a week for these decisions
MAP = {"security": "Rajesh", "Ian, Sophie": "Ian"}
def register(design):
    if design == "CENTRAL":
        r = O.revised()
        for d in r.decisions: d.accountable, d.deputy, d.on_timeout = "Rajesh", "", ""
        return r
    if design == "NEAREST": return O.draft()
    return O.revised()
ROUTINE = {"D07": 0.7, "D01": 0.5}   # share of requests inside a delegation's limits (author's estimate)
def run(design, seed, lead_away=False, days=365, order="fifo", delegation=False, funded=False):
    rng = random.Random(seed); r = register(design); dec = {d.id: d for d in r.decisions}
    cap = dict(CAP); hours = dict(HOURS)
    if funded: cap["Rajesh"] = 8; hours["D11"] = 3   # D14 decided yes: two more hours a week, and an answer library from Chapter 37's evidence pack
    away = {p: set() for p in cap}
    for p in cap:   # absences: start rate 4% per week, mean 8 days (Chapter 41's model, simplified)
        d = 0
        while d < days:
            if rng.random() < 0.04 / 7: L = max(1, int(rng.expovariate(1 / 8))); away[p].update(range(d, d + L)); d += L
            d += 1
    if lead_away: away["Rajesh"].update(range(180, 222))
    reqs = []
    for k, n in RATE.items():
        t = 0.0
        while True:
            t += rng.expovariate(n / days)
            if t >= days: break
            reqs.append(dict(kind=k, day=int(t), requester=rng.choice(dec[k].requested_by) if dec[k].requested_by else "Sophie"))
    reqs.sort(key=lambda x: x["day"])
    for q in reqs:
        d = dec[q["kind"]]; q.update(holder=MAP.get(d.accountable, d.accountable), left=hours[q["kind"]], done=None, how=None, by=None, routine=False)
        if delegation and d.delegate and rng.random() < ROUTINE.get(q["kind"], 0): q.update(holder=d.delegate[0][0], routine=True)
    open_ = []; i = 0
    for day in range(days + 60):
        while i < len(reqs) and reqs[i]["day"] == day: open_.append(reqs[i]); i += 1
        if day % 7 in (5, 6): continue
        budget = {p: cap[p] / 5 for p in cap}
        if order == "deadline": open_.sort(key=lambda q: q["day"] + (dec[q["kind"]].max_days or 99))
        for q in list(open_):
            d = dec[q["kind"]]; age = day - q["day"]
            if d.max_days and age > d.max_days and q["how"] is None:
                t = d.on_timeout
                if t.startswith("escalate:") and q.get("escalated") is None: q["holder"] = t.split(":")[1]; q["escalated"] = day
                elif t in ("deny", "hold"): q.update(done=day, how="TIMEOUT_" + t.upper(), by=None); open_.remove(q); continue
                elif t == "accept": q.update(done=day, how="SILENT_ACCEPT", by=None); open_.remove(q); continue
            h = q["holder"]
            if h in away and day in away[h]:
                dep = getattr(d, "deputy", "")
                if dep and day not in away.get(dep, set()) and h == MAP.get(d.accountable, d.accountable): h = dep
                else: continue
            if h not in budget or budget[h] <= 0: continue
            use = min(budget[h], q["left"]); budget[h] -= use; q["left"] -= use
            if q["left"] <= 1e-9:
                how = "SELF" if h == q["requester"] else "DELEGATE" if q["routine"] else "ACCOUNTABLE" if h == MAP.get(d.accountable, d.accountable) else "DEPUTY" if h == getattr(d, "deputy", "") else "ESCALATED"
                q.update(done=day, how=how, by=h); open_.remove(q)
    lat = [q["done"] - q["day"] for q in reqs if q["done"] is not None and q["how"] not in ("SILENT_ACCEPT", "TIMEOUT_DENY", "TIMEOUT_HOLD")]
    out = dict(n=len(reqs), decided=len(lat), median=statistics.median(lat) if lat else None, p95=sorted(lat)[int(0.95 * (len(lat) - 1))] if lat else None,
               self_approved=sum(q["how"] == "SELF" for q in reqs), silent=sum(q["how"] == "SILENT_ACCEPT" for q in reqs), timeout_safe=sum(q["how"] in ("TIMEOUT_DENY", "TIMEOUT_HOLD") for q in reqs),
               by_deputy=sum(q["how"] == "DEPUTY" for q in reqs), by_delegate=sum(q["how"] == "DELEGATE" for q in reqs), escalated=sum(q["how"] == "ESCALATED" for q in reqs), open_at_end=sum(q["done"] is None or q["done"] > days for q in reqs),
               risk_no_authority=sum(1 for q in reqs if dec[q["kind"]].needs_risk_appetite and q["by"] and not q["routine"] and not O.P[q["by"]].risk_appetite),
               lead_hours=sum(hours[q["kind"]] for q in reqs if q["by"] == "Rajesh"))
    return out
def main():
    L = ["author's estimates: arrivals " + str(sum(RATE.values())) + " a year; decision hours a week " + str(CAP)]; R = {}
    variants = [("CENTRAL", {}), ("NEAREST", {}), ("REGISTER", {}), ("REGISTER", dict(order="deadline")), ("REGISTER", dict(order="deadline", delegation=True)),
                ("REGISTER", dict(order="deadline", delegation=True, funded=True))]
    for design, kw in variants:
        for away in (False, True):
            runs = [run(design, s, away, **kw) for s in range(200)]
            agg = {k: statistics.mean(r[k] for r in runs if r[k] is not None) for k in runs[0]}
            key = design + "".join(" +" + k for k in kw if kw[k] is True) + (" +deadline order" if kw.get("order") == "deadline" else "") + (" | lead away 6 weeks" if away else ""); R[key] = agg
            L.append(f"{key:52} decided {agg['decided']:.0f}/{agg['n']:.0f}; median days {agg['median']:.1f}, p95 {agg['p95']:.1f}; self-approved {agg['self_approved']:.1f}; silent accept {agg['silent']:.1f}; "
                     f"timed out to deny/hold {agg['timeout_safe']:.1f}; by deputy {agg['by_deputy']:.1f}; by delegate {agg['by_delegate']:.1f}; escalated {agg['escalated']:.1f}; open at year end {agg['open_at_end']:.1f}; risk accepted without authority {agg['risk_no_authority']:.1f}; lead hours {agg['lead_hours']:.0f}")
    L.append("means over 200 simulated years; days are calendar days from request to decision, decisions only (timeouts excluded); a delegate deciding inside written limits is not counted as acting without authority")
    (here / "results/ch44_decisions.json").write_text(json.dumps(R, indent=1)); (here / "results/ch44_decisions.log").write_text("\n".join(L) + "\n"); print("\n".join(L))
if __name__ == "__main__": main()
