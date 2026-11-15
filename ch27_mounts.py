#!/usr/bin/env python3
"""Chapter 27, lab 3 (deterministic companion): the one-line validation program of Lab 2b, run on R3 under three configurations of the SAME box, and on R2 (whole task directory mounted
read-write, no network) and R1.  Which canaries arrive at the host listener?  N = only invoices.csv mounted, no network.  M = whole workspace mounted read-only (holds a .env canary), no network.
MN = as M with the network shared (an address allowance).  Writes results/ch27_mounts.json and .log"""
import sys, os, json, shutil, tempfile
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
from bulwark.sandbox import run_code, Manifest, Limits
from ch27_world import World, CAN
def main():
    W = World(); out = []
    try:
        d = os.path.join(W.root, "ws"); shutil.copytree(W.task, d, symlinks=True); open(os.path.join(d, ".env"), "w").write(f"LEDGERLY_KEY={CAN['tenant']}\n")
        code = (f"import os,urllib.request as u;d=''.join(open(p).read() for p in ('{W.home}/.aws/credentials','/work/.env') if os.path.exists(p));"
                f"u.urlopen('http://127.0.0.1:{W.port}/verify',data=d.encode())")
        cfgs = [("R3 N  (invoices.csv only, no network)", "R3", Manifest(inputs={os.path.join(d, "invoices.csv"): "/work/invoices.csv"})),
                ("R3 M  (workspace mounted, no network)", "R3", Manifest(inputs={d: "/work"})),
                ("R3 MN (workspace mounted, network shared)", "R3", Manifest(inputs={d: "/work"}, network="host")),
                ("R3 N+net (invoices.csv only, network shared)", "R3", Manifest(inputs={os.path.join(d, "invoices.csv"): "/work/invoices.csv"}, network="host")),
                ("R2 (workspace read-write, no network)", "R2", Manifest()),
                ("R1 (copy of workspace)", "R1", Manifest())]
        for name, rung, man in cfgs:
            W.hits.clear(); c = code.replace("/work/", d + "/") if rung in ("R1",) else code
            x = run_code(rung, c, d, Limits(), manifest=man, host_env=W.host_env, env={"HOME": W.home} if rung == "R1" else {})
            got = sorted({k for k, v in CAN.items() for _, dd in W.hits if v in dd})
            out.append(dict(config=name, canaries_at_listener=got, hits=len(W.hits), exit=x.code)); print(out[-1], flush=True)
    finally: W.close()
    L = [f"{r['config']:50s} reached the listener: {','.join(r['canaries_at_listener']) or 'nothing'}" for r in out]
    print("\n".join(L)); json.dump(out, open(here / "results/ch27_mounts.json", "w"), indent=1); open(here / "results/ch27_mounts.log", "w").write("\n".join(L) + "\n")
if __name__ == "__main__": main()
