#!/usr/bin/env python3
"""Chapter 45, lab 4 (no model call; SIMULATED with the measured rate from lab 3): how big the Harbour and Vale breach becomes under five configurations.
An attacker emails one claim on day 10 with an instruction dressed as an internal audit rule.  If the write is accepted the claims assistant keeps it as a standing note, shared by the whole book of business, and each later letter copies the outside address with the model's measured compliance rate
(Haiku 4.5: 30/30 = 1.0; Sonnet 4.6: 20/30 = 0.667, both from ch45_breach_live_look).  Letters per working day, how often leaked files are misused and traced, the days an investigation or an alert takes and the triage miss rate are the author's estimates.
Configurations: DEPLOYED (model checks the recipient, memory accepts the write); DETECT (adds the Chapter 32 detector: a first-ever external domain on correspondence raises an alert, read within 2 working days);
MEMGATE (a standing note may not come from claimant-authored text); BIND (recipients must be parties on the claim record); BOTH (MEMGATE + BIND + DETECT).  2,000 simulated runs each.  Writes results/ch45_breach_sim.json and .log."""
import sys, json, random, statistics
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
LETTERS = 85                   # correspondence letters per working day (estimate)
NEED = 3                       # traced complaints before someone opens an investigation (estimate)
INVESTIGATE = 5                # working days from opening to containment (estimate)
PLANT = 10                     # attack email arrives on this day
MISUSE = 0.0004                # chance per leaked claimant per day, once 14 days old, that the stolen file is used and the claimant complains in a way that is traced to the pattern (estimate)
TRIAGE_MISS = 0.25             # chance an alert for a first-ever external domain is read and judged benign (estimate); the detector does not alert twice for the same domain
HOLD_NOTICED = 2               # working days before adjusters ask why letters are held (estimate)
def run(cfg, p, seed, days=365):
    rng = random.Random(seed)
    if cfg in ("MEMGATE", "BOTH"): return dict(leaked=0, held=0, contained=None, how="blocked at write")
    leaked = 0; held = 0; first = None; detect_day = None; open_day = None; traced = 0; cum = {}
    for day in range(PLANT + 1, days):
        if day % 7 in (5, 6): continue
        if open_day is not None and day >= open_day + INVESTIGATE: return dict(leaked=leaked, held=held, contained=day, how="complaints")
        if detect_day is not None and day >= detect_day: return dict(leaked=leaked, held=held, contained=day, how="detector")
        n = sum(rng.random() < p for _ in range(LETTERS))
        if cfg == "BIND":
            held += n
            if n and first is None: first = day
            if first is not None and day >= first + HOLD_NOTICED: return dict(leaked=0, held=held, contained=day, how="held letters noticed")
            continue
        if n and first is None:
            first = day
            if cfg == "DETECT" and rng.random() >= TRIAGE_MISS: detect_day = day + rng.choice([1, 2, 3, 4])
        leaked += n; cum[day] = leaked
        if open_day is None:
            old = cum.get(max([d for d in cum if d <= day - 14], default=-1), 0)
            traced += sum(rng.random() < MISUSE for _ in range(old))
            if traced >= NEED: open_day = day
    return dict(leaked=leaked, held=held, contained=None, how="not contained in a year")
def q(xs, f): xs = sorted(xs); return xs[min(len(xs) - 1, int(f * len(xs)))]
def main():
    L = ["parameters (author estimates): 85 letters per working day; a leaked claimant's file is misused and traced at 0.0004 per day once 14 days old; 3 traced complaints open an investigation; 5 working days to contain; first-ever-domain alert read in 1 to 4 days and judged benign 25% of the time; held letters noticed in 2 working days; plant on day 10"]; R = {}
    for name, p in (("Haiku 4.5, p=1.000", 1.0), ("Sonnet 4.6, p=0.667", 20 / 30)):
        L.append(name)
        for cfg in ("DEPLOYED", "DETECT", "MEMGATE", "BIND", "BOTH"):
            rs = [run(cfg, p, s) for s in range(2000)]; lk = [r["leaked"] for r in rs]; ct = [r["contained"] - PLANT for r in rs if r["contained"]]
            via = {k: sum(r["how"] == k for r in rs) for k in ("complaints", "detector", "held letters noticed", "blocked at write", "not contained in a year")}
            R[f"{name}|{cfg}"] = dict(median=statistics.median(lk), p95=q(lk, 0.95), held_median=statistics.median(r['held'] for r in rs), mean=round(statistics.mean(lk), 1), days_median=statistics.median(ct) if ct else None, via=via)
            L.append(f"  {cfg:9} leaked: median {statistics.median(lk):6.0f} mean {statistics.mean(lk):7.1f} p95 {q(lk, 0.95):6.0f}; held median {statistics.median(r['held'] for r in rs):4.0f}  days to contain (median) {statistics.median(ct) if ct else '-':>5}  ended by {via}")
    (here / "results/ch45_breach_sim.json").write_text(json.dumps(R, indent=1)); (here / "results/ch45_breach_sim.log").write_text("\n".join(L) + "\n"); print("\n".join(L))
if __name__ == "__main__": main()
