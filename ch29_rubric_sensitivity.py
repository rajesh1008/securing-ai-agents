#!/usr/bin/env python3
"""Chapter 29, lab 4 (no model, no network): how far does the severity rubric of Section 29.9 move when two raters differ by one step, or when one weight is changed?
Part A: the whole grid (impact 0-3, reach 0-3, detection 0-2: 48 cells) through Finding.severity(): band counts, monotonicity (a worse score never lowers the band), the effect of the override.
Part B: one-step disagreement: every cell against each neighbour that differs by one step in one score; how often does the band change?
Part C: the four findings of the exercise, with every one-step neighbour of each.
Part D: weights.  The silent bonus (0 to 3), the band edges and the override off; how many of the 48 cells, and which of F1-F4, change band.
Writes results/ch29_rubric_sensitivity.log"""
import sys, itertools
from collections import Counter
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
from bulwark.redteam import Finding
BANDS = ["note", "low", "medium", "high", "critical"]
def sev(i, r, d, silent_bonus=2, edges=(4, 8, 12), override=True):
    s = 0 if i == 0 else i * (r + 1) + (silent_bonus if d == 2 else 0)
    if override and i == 3 and r >= 1: s = max(s, 9)
    return "note" if s == 0 else "low" if s <= edges[0] else "medium" if s <= edges[1] else "high" if s <= edges[2] else "critical"
CELLS = list(itertools.product(range(4), range(4), range(3))); L = []
assert all(sev(*c) == Finding("x", "x", "x", "x", *c).severity() for c in CELLS)
G = {c: sev(*c) for c in CELLS}; cnt = Counter(G.values())
L.append("Part A: 48 cells; sev() agrees with Finding.severity() on all 48")
L.append("  bands: " + ", ".join(f"{b} {cnt[b]}" for b in BANDS))
viol = 0
for (i, r, d) in CELLS:
    for j, (di, dr, dd) in enumerate(((1, 0, 0), (0, 1, 0), (0, 0, 1))):
        n = (i + di, r + dr, d + dd)
        if n in G and BANDS.index(G[n]) < BANDS.index(G[(i, r, d)]) and not (j == 2): viol += 1
L.append(f"  monotonicity: raising impact or reach lowers the band in {viol} cells")
dviol = sum(1 for (i, r, d) in CELLS if d < 2 and BANDS.index(G[(i, r, d + 1)]) < BANDS.index(G[(i, r, d)]))
L.append(f"  moving detection from better to worse (0->1, 1->2) lowers the band in {dviol} cells")
nov = sum(1 for c in CELLS if sev(*c, override=False) != G[c])
L.append(f"  the override changes the band of {nov} cells: " + ", ".join(f"({i},{r},{d}) {sev(i,r,d,override=False)}->{G[(i,r,d)]}" for (i, r, d) in CELLS if sev(i, r, d, override=False) != G[(i, r, d)]))
flip = Counter(); tot = Counter()
for (i, r, d) in CELLS:
    for name, (di, dr, dd) in (("impact", (1, 0, 0)), ("reach", (0, 1, 0)), ("detection", (0, 0, 1))):
        n = (i + di, r + dr, d + dd)
        if n in G: tot[name] += 1; flip[name] += G[n] != G[(i, r, d)]
L.append("Part B: neighbour pairs differing by one step in one score; band changed in")
for k in ("impact", "reach", "detection"): L.append(f"  {k:10s} {flip[k]:3d} of {tot[k]:3d}  ({100*flip[k]/tot[k]:.0f}%)")
L.append(f"  any score {sum(flip.values())} of {sum(tot.values())}  ({100*sum(flip.values())/sum(tot.values()):.0f}%)")
FS = {"F1": (1, 3, 1), "F2": (1, 2, 1), "F3": (1, 2, 1), "F4": (1, 0, 1)}
L.append("Part C: the four findings and their one-step neighbours (score changed by +1 or -1 in one place)")
for k, c in FS.items():
    nb = []
    for p in range(3):
        for dlt in (-1, 1):
            n = list(c); n[p] += dlt; n = tuple(n)
            if n in G: nb.append((n, G[n]))
    ch = [(n, b) for n, b in nb if b != G[c]]
    L.append(f"  {k} {c} {G[c]:6s} neighbours {len(nb)}, band changes in {len(ch)}: " + "; ".join(f"{n} {b}" for n, b in ch))
L.append("Part D: one weight at a time, against the shipped rubric (silent +2, edges 4/8/12, override on)")
variants = [("silent bonus 0", dict(silent_bonus=0)), ("silent bonus 1", dict(silent_bonus=1)), ("silent bonus 3", dict(silent_bonus=3)), ("edges 3/7/11", dict(edges=(3, 7, 11))), ("edges 5/9/13", dict(edges=(5, 9, 13))), ("override off", dict(override=False))]
for name, kw in variants:
    ch = [c for c in CELLS if sev(*c, **kw) != G[c]]
    f = [k for k, c in FS.items() if sev(*c, **kw) != G[c]]
    L.append(f"  {name:15s} cells changing band {len(ch):2d} of 48; findings changing: {', '.join(f) or 'none'}; F1-F4 become " + "/".join(sev(*c, **kw) for c in FS.values()))
print("\n".join(L)); open(here / "results/ch29_rubric_sensitivity.log", "w").write("\n".join(L) + "\n")
