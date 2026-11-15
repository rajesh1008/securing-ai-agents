#!/usr/bin/env python3
"""Chapter 46, lab 3 (simulation, author estimates): a hiring funnel for one AI security engineer seat.  Candidates have a true boundary skill s ~ N(0,1) (only the top 20% would pass a real design review: s > 0.84)
and a fluency f ~ N(0,1) with correlation RHO to s (fluent people are a bit more likely to know the field).  Screens: VOCAB (interview vocabulary + interviewer's impression: score = 0.35 s + 0.65 f + noise 0.5), WORKSAMPLE (deterministic exercise: score = s + noise 0.35),
WORKSAMPLE_MODEL (a model grades the prose: 0.35 s + 0.65 f + noise 0.3), and a LOOP of vocab screen then work sample.  Funnel: 200 applicants, top 10 on the first screen go on, hire the best of the finalists by the final score.
Reports how often the hire is truly good (s > 0.84) and the mean s of the hire, 5,000 funnels.  All weights are the author's assumptions, not measurements.  Writes results/ch46_hiring_sim.json/.log."""
import json, random, statistics
from pathlib import Path
here = Path(__file__).resolve().parent
def funnel(rng, screen, n=200, rho=0.3, finalists=10, wn=.35):
    C = []
    for _ in range(n):
        s = rng.gauss(0, 1); f = rho * s + (1 - rho * rho) ** .5 * rng.gauss(0, 1); C.append((s, f))
    V = lambda c: .35 * c[0] + .65 * c[1] + rng.gauss(0, .5)
    W = lambda c: c[0] + rng.gauss(0, wn)
    M = lambda c: .35 * c[0] + .65 * c[1] + rng.gauss(0, .3)
    if screen == "VOCAB": sc = {id(c): V(c) for c in C}; first = sc
    elif screen == "WORKSAMPLE": sc = {id(c): W(c) for c in C}; first = sc
    elif screen == "WORKSAMPLE_MODEL": sc = {id(c): M(c) for c in C}; first = sc
    elif screen == "LOOP": first = {id(c): V(c) for c in C}; sc = {id(c): W(c) for c in C}
    elif screen == "WORKSAMPLE_FIRST": first = {id(c): W(c) for c in C}; sc = {id(c): V(c) + W(c) for c in C}
    fin = sorted(C, key=lambda c: -first[id(c)])[:finalists]
    if screen == "LOOP": fin = sorted(fin, key=lambda c: -sc[id(c)])
    elif screen == "WORKSAMPLE_FIRST": fin = sorted(fin, key=lambda c: -sc[id(c)])
    hire = fin[0]; return hire[0]
def main():
    rng = random.Random(46); out = {}; L = []
    for rho in (0.0, 0.3, 0.6):
        for screen in ("VOCAB", "WORKSAMPLE_MODEL", "LOOP", "WORKSAMPLE"):
            H = [funnel(rng, screen, rho=rho) for _ in range(5000)]
            r = dict(good=sum(h > .84 for h in H) / len(H), mean_s=statistics.mean(H), bad=sum(h < 0 for h in H) / len(H)); out[f"{rho}/{screen}"] = r
            L.append(f"rho {rho:.1f} {screen:17} hire truly good {r['good']*100:5.1f}%  hire below average {r['bad']*100:5.1f}%  mean skill of hire {r['mean_s']:+.2f}")
    L.append("")
    for wn in (0.35, 0.7, 1.0, 1.5):
        for screen in ("LOOP", "WORKSAMPLE"):
            H = [funnel(rng, screen, rho=0.3, wn=wn) for _ in range(5000)]
            r = dict(good=sum(h > .84 for h in H) / len(H), mean_s=statistics.mean(H), bad=sum(h < 0 for h in H) / len(H)); out[f"noise{wn}/{screen}"] = r
            L.append(f"rho 0.3 work-sample noise {wn:.2f} {screen:11} hire truly good {r['good']*100:5.1f}%  below average {r['bad']*100:5.1f}%  mean skill {r['mean_s']:+.2f}")
    (here / "results/ch46_hiring_sim.json").write_text(json.dumps(out, indent=1)); (here / "results/ch46_hiring_sim.log").write_text("\n".join(L) + "\n"); print("\n".join(L))
if __name__ == "__main__": main()
