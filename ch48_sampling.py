#!/usr/bin/env python3
"""Chapter 48, lab 2 (no model): what a clean sample proves.  Attribute sampling tables from bulwark/reperform.py, then a simulation: a population of 2,000 payments in a quarter, 12 of which have a deviation
(no call-back before a bank-account change took effect), sampled at n = 29, 59, 149, 300 and by risk (all payments over $2,000 plus a random 59 of the rest).  10,000 draws each, seed 48.  Writes results/ch48_sampling.json and .log."""
import sys, json, random
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
import bulwark.reperform as R
L = []; say = lambda s: (L.append(s), print(s)); res = {}
say("A sample size for 95% confidence, zero deviations expected:  tolerable rate -> n:  " + "  ".join(f"{int(t*100)}%->{R.attr_n(t)}" for t in (0.10, 0.05, 0.03, 0.02, 0.01)) + f"  0.5%->{R.attr_n(0.005)}")
say("   n for 5% tolerable with 1, 2, 3 deviations allowed: " + ", ".join(str(R.attr_n(0.05, dev=d)) for d in (1, 2, 3)))
say("B upper limit on the true rate after the sample (95%, one-sided):  " + "  ".join(f"n={n},dev={d}: {R.upper_bound(n, d)*100:.1f}%" for n, d in ((29, 0), (59, 0), (59, 1), (149, 0), (149, 2), (300, 0), (300, 3), (1000, 0))))
res["A"] = {str(t): R.attr_n(t) for t in (0.10, 0.05, 0.03, 0.02, 0.01, 0.005)}
N, K, DRAWS = 2000, 12, 10_000; rng = random.Random(48)
amounts = [int(rng.lognormvariate(10.2, 1.1)) for _ in range(N)]   # cents; heavy tail
bad = set(rng.sample(range(N), K)); big = [i for i in range(N) if amounts[i] >= 200_000]
say(f"C population {N} payments, {K} with a deviation ({K/N*100:.1f}%); amounts over $2,000: {len(big)}; deviations among them: {len(bad & set(big))}; dollar value of the deviating payments {sum(amounts[i] for i in bad)/100:,.0f} of {sum(amounts)/100:,.0f} total")
res["C"] = dict(N=N, K=K, big=len(big), bad_big=len(bad & set(big)))
say("   random sample of n: share of 10,000 audits that find at least one deviation / that report 'no deviations' (and the 95% limit they would then state)")
res["random"] = {}
for n in (29, 59, 149, 300, 600):
    found = sum(1 for _ in range(DRAWS) if bad & set(rng.sample(range(N), n))); p = found / DRAWS
    say(f"   n={n:4d}: finds >=1 in {p*100:5.1f}%; clean in {100-p*100:5.1f}%, and a clean audit would state 'rate below {R.upper_bound(n, 0)*100:.1f}%' while the true rate is {K/N*100:.1f}%")
    res["random"][n] = dict(found=p, limit=R.upper_bound(n, 0))
rest = [i for i in range(N) if i not in set(big)]; bigs = set(big); f_all = 0; f_nobig = 0; n_nobig = 0; T = 0
for pl in range(200):
    bd = set(rng.sample(range(N), K)); nb = not (bd & bigs)
    for _ in range(50):
        hit = bool(bd & (bigs | set(rng.sample(rest, 59)))); f_all += hit; T += 1
        if nb: f_nobig += hit; n_nobig += 1
say(f"   risk-based (all {len(big)} payments over $2,000 plus 59 random of the other {len(rest)}; {len(big)+59} rows), over 200 random placements of the 12 deviations x 50 draws: finds >=1 in {f_all/T*100:.1f}%; when none of the 12 happens to be over $2,000 ({n_nobig//50} of 200 placements): {f_nobig/max(n_nobig,1)*100:.1f}%")
res["risk"] = dict(found=f_all / T, found_when_none_big=f_nobig / max(n_nobig, 1), placements_none_big=n_nobig // 50, rows=len(big) + 59)
tot = 0; reach = 0
for _ in range(DRAWS):
    s = rng.sample(range(N), 59); tot += sum(amounts[i] for i in s); reach += sum(amounts[i] for i in s) / sum(amounts)
say(f"   dollar coverage: a random 59 covers {reach/DRAWS*100:.1f}% of the quarter's dollars on average; the risk-based sample covers {(sum(amounts[i] for i in big)+59*sum(amounts[i] for i in rest)/len(rest))/sum(amounts)*100:.1f}%")
res["coverage"] = dict(random59=reach / DRAWS)
# automated population test: all rows
say(f"D testing the whole population by code: {N} of {N} examined, {len(bad)} found; cost is the run time of the procedure (Chapter 48 lab 1: 100,000 rows in about a second for the chain, 0.3 s for P5-P7)")
json.dump(dict(res, log=L), open(here / "results/ch48_sampling.json", "w"), indent=1); open(here / "results/ch48_sampling.log", "w").write("\n".join(L) + "\n")
