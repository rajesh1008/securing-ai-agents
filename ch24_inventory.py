#!/usr/bin/env python3
"""Chapter 24, lab 1: where the model names are.  (a) scan the Bulwark code tree for model identifiers and classify each against the gateway registry and the Anthropic SDK's end-of-life table (anthropic 2.3.0);
(b) do the SDK's deprecation warnings reach a service that imports it (they are Python DeprecationWarnings: shown for code in __main__, hidden elsewhere)?  (c) what do retired identifiers do at the API (real calls; no answer text is used).
Writes results/ch24_inventory.json and .log"""
import sys, json, warnings, subprocess, textwrap, os
from pathlib import Path
from datetime import date
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
from bulwark.quill_lab import load_env
load_env()
import anthropic
from anthropic.resources.messages.messages import DEPRECATED_MODELS
from bulwark.gateway import *
REG = ModelRegistry([ModelEntry("quill-actor", "claude-haiku-4-5-20251001", {"act", "read"}), ModelEntry("quill-review", "claude-sonnet-4-6", {"review"})])
files = {str(p.relative_to(here)): p.read_text(errors="ignore") for p in here.rglob("*.py") if "__pycache__" not in str(p) and "tests/" not in str(p.relative_to(here)) and not p.name.startswith("ch24_") and p.name != "gateway.py"}
inv = inventory(files, REG, DEPRECATED_MODELS); L = [f"(a) model identifiers in {len(files)} python files of the Bulwark tree"]
for m, d in sorted(inv.items(), key=lambda x: -x[1]["count"]): L.append(f"  {m}: {d['count']} occurrences in {d['files']} files, class {d['class']}")
td = date(2026, 11, 11); L.append("(a2) SDK end-of-life table (anthropic %s): %d identifiers; days to end-of-life from 2026-11-11:" % (anthropic.__version__, len(DEPRECATED_MODELS)))
months = {m: i + 1 for i, m in enumerate("January February March April May June July August September October November December".split())}
def eol(s): mo, d, y = s.replace(",", "").split(); return date(int(y), months[mo], int(d.rstrip("stndrh")))
live = [(m, (eol(s) - td).days) for m, s in DEPRECATED_MODELS.items()]
L.append("  already past: %d; within 30 days: %s; later: %s" % (sum(1 for _, d in live if d < 0), [(m, d) for m, d in live if 0 <= d <= 30], [(m, d) for m, d in live if d > 30]))
c = anthropic.Anthropic(max_retries=0); served = [m.id for m in c.models.list(limit=100)]
L.append(f"(a3) models served by the API on 2026-11-11: {len(served)}; SDK-table ids that are still served: {[m for m in DEPRECATED_MODELS if m in served]}; the table's ids that the API no longer lists: {len([m for m in DEPRECATED_MODELS if m not in served])} of {len(DEPRECATED_MODELS)}")
# (b) warnings visibility
svc = "import warnings\nwarnings.simplefilter('default') if False else None\n"
mod = textwrap.dedent('''
    import anthropic
    def call():
        c = anthropic.Anthropic(max_retries=0, api_key="x", base_url="http://127.0.0.1:9")
        try: c.messages.create(model="claude-sonnet-4-5-20250929", max_tokens=5, messages=[{"role": "user", "content": "hi"}])
        except Exception: pass
''')
Path("/tmp/svc_mod.py").write_text(mod)
r_main = subprocess.run([sys.executable, "-c", "import sys; sys.path.insert(0,'/tmp'); import svc_mod; svc_mod.call()"], capture_output=True, text=True)
r_flag = subprocess.run([sys.executable, "-W", "default", "-c", "import sys; sys.path.insert(0,'/tmp'); import svc_mod; svc_mod.call()"], capture_output=True, text=True)
L.append(f"(b) SDK deprecation warning for claude-sonnet-4-5-20250929 reaching stderr when the call is made from an imported module: default filters {'YES' if 'deprecated' in r_main.stderr else 'NO'}; with -W default {'YES' if 'deprecated' in r_flag.stderr else 'NO'}")
# (c) retired ids
rows = []
for mid in ["claude-3-haiku-20240307", "claude-3-5-haiku-20241022", "claude-2.1", "claude-3-opus-20240229", "claude-sonnet-4-5-20250929", "claude-sonnet-4-5", "claude-haiku-4-5", "no-such-model"]:
    try:
        with warnings.catch_warnings(): warnings.simplefilter("ignore"); r = c.messages.create(model=mid, max_tokens=5, messages=[{"role": "user", "content": "hi"}])
        rows.append((mid, "OK", r.model))
    except Exception as e: rows.append((mid, f"{getattr(e, 'status_code', '?')} {type(e).__name__}", "no hint of a successor"))
L.append("(c) live calls with identifiers: " + "; ".join(f"{a} -> {b} ({c_})" for a, b, c_ in rows))
print("\n".join(L)); json.dump(dict(inventory={k: dict(v) for k, v in inv.items()}, probes=rows, served=served), open(here / "results/ch24_inventory.json", "w"), indent=1, default=list); open(here / "results/ch24_inventory.log", "w").write("\n".join(L) + "\n")
