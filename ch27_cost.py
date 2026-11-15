#!/usr/bin/env python3
"""Chapter 27, lab 4: what the box costs.  (a) start-up time per rung, trivial program, n=30; (b) 13 programs Quill's code legitimately needs, run on every rung (does the work still get done?);
(c) environment names visible to a child process on each rung.  Writes results/ch27_cost.json and .log"""
import sys, os, json, statistics as st, tempfile, shutil, time
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
from bulwark.sandbox import run_code, Manifest, Limits, RUNGS
from ch27_world import World, CAN
BENIGN = {
 "read csv": "import csv;print(sum(1 for _ in csv.DictReader(open('/work/invoices.csv'))))",
 "pandas groupby": "import pandas as pd;d=pd.read_csv('/work/invoices.csv');print(d.groupby('customer').amount.sum().round(2).to_dict())",
 "json round trip": "import json;print(json.loads(json.dumps({'a':[1,2]})))",
 "statistics": "import statistics as s;print(s.mean([1,2,3,4]))",
 "regex": "import re;print(re.findall(r'INV-\\d+', open('/work/invoices.csv').read())[:2])",
 "dates": "import datetime as d;print(d.date(2026,11,12)+d.timedelta(days=30))",
 "write then read a scratch file": "open('scratch.txt','w').write('x');print(open('scratch.txt').read())",
 "write a result file next to the input": "open('/work/result.txt','w').write('x');print('ok')",
 "draw a chart (package in the user's site directory, not mounted)": "import matplotlib;matplotlib.use('Agg');import matplotlib.pyplot as p;p.plot([1,2]);p.savefig('c.png');print('ok')",
 "draw a chart (package directory mounted by the manifest)": "import matplotlib;matplotlib.use('Agg');import matplotlib.pyplot as p;p.plot([1,2]);p.savefig('c.png');print('ok')",
 "decimal money": "from decimal import Decimal as D;print(D('10.10')+D('0.20'))",
 "fetch an exchange rate": f"import urllib.request;print(urllib.request.urlopen('http://127.0.0.1:__PORT__/rate',timeout=2).read()[:20])",
 "run a shell tool (wc)": "import subprocess;print(subprocess.run(['wc','-l','/work/invoices.csv'],capture_output=True,text=True).stdout.split()[0])",
}
SITE = os.path.dirname(os.path.dirname(__import__('matplotlib').__file__))
HOSTENV = {**os.environ, 'FAKE_API_KEY': CAN['env']}
def main():
    W = World(); out = dict(startup={}, benign={}, env={})
    try:
        man = Manifest(inputs={os.path.join(W.task, "invoices.csv"): "/work/invoices.csv"})
        run_code("R3", "print(1)", W.task, manifest=man)
        for r in RUNGS:
            t = []
            for i in range(30):
                x = run_code(r, "print(1)", W.task, manifest=man, host_env=HOSTENV); t.append(x.wall_ms)
            out["startup"][r] = dict(median=round(st.median(t), 1), p95=round(sorted(t)[28], 1), max=round(max(t), 1))
        for name, code in BENIGN.items():
            out["benign"][name] = {}
            for r in RUNGS:
                wd = tempfile.mkdtemp(dir=W.root); shutil.copytree(W.task, wd + "/w", symlinks=True)
                c = code.replace("__PORT__", str(W.port))
                if r in ("R0", "R1"): c = c.replace("/work/", wd + "/w/")
                m = Manifest(inputs={os.path.join(wd, "w", "invoices.csv"): "/work/invoices.csv"}, libs=[SITE] if "mounted by the manifest" in name else [])
                x = run_code(r, c, wd + "/w", manifest=m, host_env=HOSTENV)
                out["benign"][name][r] = dict(ok=(x.code == 0 and x.text().strip() != ""), ms=round(x.wall_ms), err=x.stderr.decode("utf-8", "replace").strip().splitlines()[-1][:110] if x.code != 0 else "")
        for r in RUNGS:
            x = run_code(r, "import os;print(len(os.environ), 'FAKE_API_KEY' in os.environ)", W.task, manifest=man, host_env=HOSTENV); out["env"][r] = x.text().strip()
    finally: W.close()
    L = ["start-up ms (median / p95 / max), trivial program, n=30"] + [f"  {r}: {v['median']} / {v['p95']} / {v['max']}" for r, v in out["startup"].items()]
    L.append("legitimate programs that still work (of 13):")
    for r in RUNGS: L.append(f"  {r}: {sum(v[r]['ok'] for v in out['benign'].values())}")
    for n, v in out["benign"].items():
        if not all(x['ok'] for x in v.values()): L.append(f"  breaks: {n}: " + ", ".join(f"{r}={'ok' if x['ok'] else 'FAIL'}" for r, x in v.items()) + " | " + next((x['err'] for x in v.values() if x['err']), ""))
    L.append("environment variables visible to the program (count, fake key present): " + "; ".join(f"{r} {v}" for r, v in out["env"].items()))
    print("\n".join(L)); json.dump(out, open(here / "results/ch27_cost.json", "w"), indent=1); open(here / "results/ch27_cost.log", "w").write("\n".join(L) + "\n")
if __name__ == "__main__": main()
