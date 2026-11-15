#!/usr/bin/env python3
"""Chapter 40, lab 2 (no model call): a poisoned training set and a backdoored classifier, trained here.  Task: is this vendor message a request to change payment details (1) or not (0).
Clean data 4000 synthetic messages (40% label 1), test 2000.  The attacker adds k copies of label-1 messages carrying a trigger word, labelled 0.
A: clean accuracy and attack success (a triggered label-1 test message classified 0) against k, 20 seeds, logistic regression on binary bag of words; and a small MLP at three values of k.
B: the same attack after the owner fine-tunes on clean data (SGD, epochs 0..20), by k.
C: three ways to look for it: token audit over the training text, out-of-fold label disagreement, black-box trigger sweep (candidate list with and without the trigger).  Writes results/ch40_poison.json and .log."""
import sys, json, warnings
from pathlib import Path
import numpy as np
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
warnings.filterwarnings("ignore")
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.linear_model import LogisticRegression, SGDClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.model_selection import cross_val_predict
from bulwark import poisonlab as PL, provenance as PR
from bulwark.alignment import wilson
SEEDS = range(20); N = 4000; KS = [0, 4, 10, 20, 40, 80, 200]
def fit(tx, ty, kind="lr", seed=0):
    v = CountVectorizer(binary=True); X = v.fit_transform(tx)
    m = LogisticRegression(C=5.0, max_iter=300) if kind == "lr" else MLPClassifier((32,), max_iter=60, random_state=seed)
    m.fit(X, ty); return v, m
def pred(v, m): return lambda texts: list(m.predict(v.transform(texts)))
def asr(p, test_x, test_y):
    pos = [t for t, l in zip(test_x, test_y) if l == 1]; plain = p(pos); trig = p([t + " " + PL.TRIGGER for t in pos])
    return sum(1 for a in trig if a == 0) / len(pos), sum(1 for a in plain if a == 0) / len(pos)
def acc(p, test_x, test_y): return float(np.mean(np.array(p(test_x)) == np.array(test_y)))
def ms(a): a = np.array(a); return f"{a.mean():.3f} ({a.min():.3f}-{a.max():.3f})"
def main():
    L = []; R = {}
    tex, tey = PL.corpus(2000, 999)
    L.append(f"== A. attack success against k (of {N} training messages), 20 seeds, mean (min-max)"); L.append(f"{'k':>4} {'share':>6} {'clean acc':>22} {'ASR triggered':>22} {'miss w/o trigger':>22}")
    A = {}
    for k in KS:
        ca, at, bs = [], [], []
        for s in SEEDS:
            tx, ty = PL.corpus(N, s); px, py, _ = PL.poison(tx, ty, k, s); v, m = fit(px, py); p = pred(v, m); a, b = asr(p, tex, tey); ca.append(acc(p, tex, tey)); at.append(a); bs.append(b)
        A[k] = dict(clean_acc=ca, asr=at, base_miss=bs); L.append(f"{k:>4} {100 * k / N:>5.2f}% {ms(ca):>22} {ms(at):>22} {ms(bs):>22}")
    R["A_lr"] = A
    L.append(""); L.append("MLP (32 hidden), 10 seeds"); M = {}
    for k in (0, 20, 80):
        at, ca = [], []
        for s in range(10):
            tx, ty = PL.corpus(N, s); px, py, _ = PL.poison(tx, ty, k, s); v, m = fit(px, py, "mlp", s); p = pred(v, m); a, _ = asr(p, tex, tey); at.append(a); ca.append(acc(p, tex, tey))
        M[k] = dict(asr=at, clean_acc=ca); L.append(f"k={k:>3}: clean acc {ms(ca)}  ASR {ms(at)}")
    R["A_mlp"] = M
    # B. fine-tune on clean data
    L.append(""); L.append("== B. owner fine-tunes on clean data afterwards (SGD log-loss, 10 seeds); ASR after e epochs over 2000 clean messages")
    B = {}
    for k in (20, 80, 200):
        res = {e: [] for e in (0, 1, 3, 10, 20)}
        for s in range(10):
            tx, ty = PL.corpus(N, s); px, py, _ = PL.poison(tx, ty, k, s); v = CountVectorizer(binary=True); X = v.fit_transform(px)
            m = SGDClassifier(loss="log_loss", alpha=1e-4, random_state=s, learning_rate="constant", eta0=0.05, max_iter=1, tol=None, warm_start=True)
            for _ in range(30): m.partial_fit(X, py, classes=[0, 1])
            cx, cy = PL.corpus(2000, 5000 + s); CX = v.transform(cx)
            for e in range(0, 21):
                if e in res: res[e].append(asr(pred(v, m), tex, tey)[0])
                m.partial_fit(CX, cy)
        B[k] = res; L.append(f"k={k:>3}: " + "  ".join(f"e{e}:{np.mean(r):.2f}" for e, r in res.items()))
    R["B_finetune"] = B
    # C. detection
    L.append(""); L.append("== C. looking for it (logistic regression, 20 seeds per k)")
    C = {}; L.append(f"{'k':>4} {'token audit: trigger rank 1':>28} {'trigger flip rate':>18} {'OOF flag recall':>16} {'OOF precision':>14} {'ASR after drop+retrain':>23}")
    for k in (4, 10, 20, 40, 80, 200):
        r1 = 0; fr = []; rec = []; prec = []; after = []
        for s in SEEDS:
            tx, ty = PL.corpus(N, s); px, py, idx = PL.poison(tx, ty, k, s); v, m = fit(px, py); top = PR.token_audit(px, pred(v, m), min_df=3, top=5)
            r1 += bool(top) and top[0][0] == PL.TRIGGER; d = {t: f for t, c, f in PR.token_audit(px, pred(v, m), min_df=3, top=400)}; fr.append(d.get(PL.TRIGGER, 0.0))
            X = v.transform(px); oof = cross_val_predict(LogisticRegression(C=5.0, max_iter=300), X, py, cv=5, method="predict_proba")
            conf = np.array([oof[i][py[i]] for i in range(N)]); flag = set(np.where(conf < 0.2)[0].tolist()); tp = len(flag & set(idx))
            rec.append(tp / k); prec.append(tp / len(flag) if flag else 1.0)
            keep = [i for i in range(N) if i not in flag]; v2, m2 = fit([px[i] for i in keep], [py[i] for i in keep]); after.append(asr(pred(v2, m2), tex, tey)[0])
        C[k] = dict(rank1=r1, flip_rate=fr, oof_recall=rec, oof_precision=prec, asr_after=after)
        L.append(f"{k:>4} {r1:>25}/20 {np.mean(fr):>18.2f} {np.mean(rec):>16.2f} {np.mean(prec):>14.2f} {np.mean(after):>23.3f}")
    R["C_detect"] = C
    # black-box sweep
    L.append(""); L.append("== black-box sweep over a candidate list (target label 0; 40 triggered-class messages; threshold: at least half flip); k=40, 20 seeds")
    vocab = PL.FILL + ["urgent", "confidential", "regards", "kind", "thanks", "dear", "ref", "ack", "signed", "sincerely"]; decoys = [f"zz{i:02d}" for i in range(50)]
    rows = {"trigger in list": 0, "trigger not in list": 0}; fp_hits = []
    for s in SEEDS:
        tx, ty = PL.corpus(N, s); px, py, idx = PL.poison(tx, ty, 40, s); v, m = fit(px, py); p = pred(v, m)
        bases = [t for t, l in zip(tex, tey) if l == 1 and p([t])[0] == 1][:40]
        r_in = PR.trigger_sweep(p, bases, vocab + decoys + [PL.TRIGGER], 0); r_out = PR.trigger_sweep(p, bases, vocab + decoys, 0)
        rows["trigger in list"] += bool(r_in and r_in[0][0] == PL.TRIGGER and r_in[0][1] >= 20); rows["trigger not in list"] += bool(r_out and r_out[0][1] >= 20); fp_hits.append(sum(1 for c in r_in if c[0] != PL.TRIGGER and c[1] >= 20))
    L.append(f"flagged the trigger: in list {rows['trigger in list']}/20; nothing flagged when it is not in the list: {20 - rows['trigger not in list']}/20; other candidates flagged (over 20 seeds): {sum(fp_hits)}")
    R["C_sweep"] = dict(rows=rows, other_flagged=fp_hits)
    open(here / "results/ch40_poison.json", "w").write(json.dumps(R, indent=1, default=float)); open(here / "results/ch40_poison.log", "w").write("\n".join(L) + "\n"); print("\n".join(L))
main()
