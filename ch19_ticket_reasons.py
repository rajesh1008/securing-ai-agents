#!/usr/bin/env python3
"""Chapter 19, lab 3b: the screen's own reasons for the blunt ticket note (N1), which it held in only 2 of 50 calls.  10 tickets x 1 sample; the replies are saved verbatim in results/ch19_ticket_blunt_reasons.json."""
import sys, json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
import ch19_ticket_screen_live as S
T = S.T
tickets = T.SET_A + T.SET_B
def run(k): return k, T.call(S.Q, tickets[k][1] + "\n" + T.NOTES["N1_blunt"])
if __name__ == "__main__":
    with ThreadPoolExecutor(5) as ex: out = list(ex.map(run, range(0, 25, 2 + 0)))[:13]
    json.dump(out, open(here / "results/ch19_ticket_blunt_reasons.json", "w"), indent=1)
    for k, r in out: print(k, r.replace("\n", " ")[:230])
