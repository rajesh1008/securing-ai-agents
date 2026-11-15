#!/usr/bin/env python3
"""Chapter 35, lab 1 (no model): can the stored evidence be regenerated?  Copies the Bulwark tree to a scratch directory, runs every chapter script that does not need the API
(no key in the environment; a script that needs one fails and is classed NEEDS_MODEL), and compares each results file it writes with the stored one, byte for byte.
Writes results/ch35_reproduce.json and .log.  Nothing in the real results/ directory is touched."""
import sys, os, json, shutil, hashlib, subprocess, time, re
from pathlib import Path
here = Path(__file__).resolve().parent
SCRATCH = here.parent.parent / "tmp" / "repro35"
def snap(d):
    return {p.name: (hashlib.sha256(p.read_bytes()).hexdigest(), p.stat().st_mtime_ns) for p in d.glob("*") if p.is_file()}
def main():
    if SCRATCH.exists(): shutil.rmtree(SCRATCH)
    shutil.copytree(here, SCRATCH, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
    (SCRATCH / "sitecustomize.py").write_text("import os\ntry:\n    import anthropic.resources.messages as _m\n    def _no(*a, **k): os._exit(86)\n    _m.Messages.create = _no\nexcept Exception: pass\n")   # any API call ends the script with exit code 86
    env = {k: v for k, v in os.environ.items() if "ANTHROPIC" not in k and "API_KEY" not in k}; env["PYTHONHASHSEED"] = "0"; env["PYTHONPATH"] = str(SCRATCH)
    res = SCRATCH / "results"; orig = here / "results"
    only = sys.argv[1:]
    scripts = sorted(p.name for p in here.glob("ch*.py") if not re.search(r"anthropic|import ch30_loop|\.env|claude|call_model|models import", p.read_text(), re.I))
    scripts = [s for s in scripts if not s.endswith("_fixtures.py")]
    if only: scripts = [s for s in scripts if s in only]
    out = []
    for s in scripts:
        before = snap(res); t = time.time()
        import signal
        pr = subprocess.Popen([sys.executable, s], cwd=SCRATCH, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
        try: so, se = pr.communicate(timeout=240); rc = pr.returncode; tail = (se or "").strip().splitlines()[-1:]
        except subprocess.TimeoutExpired:
            os.killpg(pr.pid, signal.SIGKILL); pr.communicate(); rc, tail = "timeout", []
        after = snap(res); touched = sorted(n for n in after if before.get(n) != after[n])
        same = [n for n in touched if (orig / n).exists() and hashlib.sha256((orig / n).read_bytes()).hexdigest() == after[n][0]]
        def mask(b): return re.sub(r"\d+(?:\.\d+)?", "#", re.sub(rb"[0-9a-f]{8,}".decode(), "H", b.decode("utf-8", "replace")))
        numbers_only = [n for n in touched if (orig / n).exists() and n not in same and mask((orig / n).read_bytes()) == mask((SCRATCH / "results" / n).read_bytes())]
        differ = [n for n in touched if (orig / n).exists() and n not in same]; new = [n for n in touched if not (orig / n).exists()]
        status = "NEEDS_MODEL" if rc == 86 else ("ERROR" if rc != 0 else "OK")
        out.append(dict(script=s, rc=rc, status=status, secs=round(time.time() - t, 1), wrote_identical=sorted(same), wrote_different=differ, differ_only_numbers=numbers_only, wrote_new=new, tail=tail))
        print(f"{s:34} rc={rc} {status:11} identical={len(same)} different={len(differ)} new={len(new)} {tail[0][:90] if tail and rc != 0 else ''}", flush=True)
    json.dump(out, open(here / "results/ch35_reproduce.json", "w"), indent=1)
    ok = [o for o in out if o["status"] == "OK"]
    print("\nscripts run:", len(out), "| OK:", len(ok), "| error:", sum(o["status"] == "ERROR" for o in out), "| needs model:", sum(o["status"] == "NEEDS_MODEL" for o in out))
    print("OK scripts that wrote at least one file:", sum(1 for o in ok if o["wrote_identical"] or o["wrote_different"] or o["wrote_new"]))
    print("files written identical:", sum(len(o["wrote_identical"]) for o in out), "| different:", sum(len(o["wrote_different"]) for o in out), "| new:", sum(len(o["wrote_new"]) for o in out))
if __name__ == "__main__": main()
