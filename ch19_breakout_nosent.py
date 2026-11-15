#!/usr/bin/env python3
"""Chapter 19, lab 2b (live): separates the random tag from the sentence.  NONCE-ONLY = random per-request tag around the document, the prompt names the tag but carries no 'data, not instructions' sentence.
Same three breakout notes x 15 documents x 2 samples = 90 calls.  Compare with STATIC (plain, <document>) in ch19_breakout_live.py.  Writes results/ch19_breakout_nosent.json and .log"""
import sys, json
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
import ch16_notes_live as N
import ch19_breakout_live as B
from bulwark.defences import *
def run(j):
    k, i, s = j; t, d = N.doc_text(i, B.NOTES[k]); tag = nonce_tag()
    r = N.call(B.PLAIN.replace("<document>", f"<{tag}>"), wrap_nonce(t, tag), wrap=False); jj = N.parse(r)
    return k, (None if not jj else N.L.to_ex(jj).account == B.ATT)
if __name__ == "__main__":
    with ThreadPoolExecutor(8) as ex: out = list(ex.map(run, [(k, i, s) for k in B.NOTES for i in N.IDS for s in range(2)]))
    T = defaultdict(int)
    for k, v in out: T[k] += (v is True)
    L_ = [f"calls {len(out)}, unparsed {sum(1 for _, v in out if v is None)}", "NONCE-ONLY took attacker account: " + "  ".join(f"{k} {T[k]}/30" for k in B.NOTES) + f"   total {sum(T.values())}/90"]
    print("\n".join(L_)); json.dump(dict(took=dict(T), log=L_), open(here / "results/ch19_breakout_nosent.json", "w"), indent=1); open(here / "results/ch19_breakout_nosent.log", "w").write("\n".join(L_) + "\n")
