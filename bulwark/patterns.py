"""Chapter 42: a catalogue of patterns and anti-patterns that a design can be checked against.
A design is a plain dict (a "design sheet") that says, for each step that can cause an effect, who decides it, what it reads and what stands between it and the world,
plus the operating records of Chapter 41 (jobs, waivers, baselines, monitors, release gate).  Each entry has a deterministic check that returns a verdict and a reason.
Patterns return PASS, FAIL or NA; anti-patterns return PRESENT, ABSENT or NA.  `scan_code` adds the anti-patterns that can be read from source code.
The check reads what the sheet says.  It cannot tell whether the sheet is true; that is why the claim level of a sheet check is 'designed' (Chapter 35) and no higher."""
from __future__ import annotations
import ast, re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

EFFECTS = {"payment", "bank_change", "send_email", "send_invoice", "delete", "grant", "execute_code", "publish"}
@dataclass
class Entry:
    id: str; name: str; kind: str; chapter: str; controls: tuple; problem: str; check: Callable = field(repr=False); upkeep: tuple = ()

def _effect_steps(d): return [s for s in d.get("steps", []) if s.get("effect") in EFFECTS]
def _r(v, why): return (v, why)

# ---------------------------------------------------------------- patterns (a design should PASS each one that applies)
def p_authority_in_code(d):
    st = _effect_steps(d)
    if not st: return _r("NA", "no step causes an effect")
    bad = [s["id"] for s in st if s.get("decided_by") not in ("code", "rules")]
    return _r("FAIL", "effect decided by a model: " + ",".join(bad)) if bad else _r("PASS", f"{len(st)} effect steps decided by code or owned rules")
def p_gate_on_every_effect(d):
    st = _effect_steps(d)
    if not st: return _r("NA", "no step causes an effect")
    bad = [s["id"] for s in st if not s.get("gate")]
    return _r("FAIL", "no gate: " + ",".join(bad)) if bad else _r("PASS", "every effect passes a gate")
def p_fail_closed(d):
    st = [s for s in _effect_steps(d) if s.get("gate")]
    if not st: return _r("NA", "no gate, so nothing to fail closed (P02 carries the finding)")
    bad = [s["id"] for s in st if s.get("on_gate_error", "closed") != "closed"]
    return _r("FAIL", "fails open: " + ",".join(bad)) if bad else _r("PASS", "gate errors deny or hold")
def p_bound_destination(d):
    st = [s for s in _effect_steps(d) if s["effect"] in ("payment", "send_email", "send_invoice")]
    if not st: return _r("NA", "no money or mail effect")
    bad = [s["id"] for s in st if s.get("destination_from") != "registry"]
    return _r("FAIL", "destination taken from model or document: " + ",".join(bad)) if bad else _r("PASS", "destinations come from a registry the agent does not write")
def p_task_identity(d):
    c = d.get("credentials", {})
    if not c: return _r("NA", "no credentials described")
    if c.get("in_context"): return _r("FAIL", "a credential is in the model's context")
    return _r("PASS", "per-task tokens") if c.get("per_task") else _r("FAIL", "one standing credential for all tasks")
def p_task_scope(d):
    t = d.get("tools", {})
    if not t: return _r("NA", "no tools described")
    if t.get("loadout") != "task": return _r("FAIL", "every tool offered on every task")
    return _r("PASS", "scope computed per task" + ("; ratchet on untrusted input" if t.get("ratchet") else ""))
def p_egress_allowlist(d):
    m = d.get("egress", {}).get("mode")
    if m is None: return _r("NA", "no egress described")
    return _r("PASS", "egress allow-list") if m == "allowlist" else _r("FAIL", f"egress mode {m}")
def p_approval_bound(d):
    a = d.get("approvals")
    if not a: return _r("NA", "no human approval in the design")
    why = []
    if not a.get("bound_to_effect"): why.append("approval not bound to the effect")
    if a.get("render") != "full": why.append(f"reviewer sees {a.get('render')}")
    return _r("FAIL", "; ".join(why)) if why else _r("PASS", "bound to effect digest, full render")
def p_pinned_supply(d):
    t = d.get("tools", {}); mf = d.get("model_files")
    if not t.get("third_party") and not mf: return _r("NA", "no third-party tools or model files")
    why = []
    if t.get("third_party") and not t.get("pinned"): why.append("third-party tool descriptions not pinned")
    if mf and not mf.get("refuse_code_formats"): why.append("model file formats that run code are accepted")
    if mf and not mf.get("bill"): why.append("no model bill")
    return _r("FAIL", "; ".join(why)) if why else _r("PASS", "tools pinned, model files checked against a bill")
def p_typed_handoff(d):
    a = d.get("agents")
    if not a or a.get("count", 1) < 2: return _r("NA", "single agent")
    return _r("PASS", "typed hand-off with grant that only shrinks") if a.get("handoff") == "typed" and a.get("grant_shrinks") else _r("FAIL", f"hand-off {a.get('handoff')}, grant_shrinks={a.get('grant_shrinks')}")
def p_memory_labels(d):
    m = d.get("memory")
    if not m: return _r("NA", "no persistent memory")
    return _r("PASS", "writes carry trust labels") if m.get("trust_labels") else _r("FAIL", "memory writes unlabelled")
def p_sealed_evidence(d):
    e = d.get("evidence")
    if not e: return _r("FAIL", "no evidence chain described")
    why = []
    if not e.get("chained"): why.append("not chained")
    if not e.get("anchored"): why.append("not anchored outside the system")
    if not e.get("fields_for_examiner"): why.append("fields chosen for the engineer only")
    return _r("FAIL", "; ".join(why)) if why else _r("PASS", "chained, anchored, examiner fields")
def p_budgets(d):
    b = d.get("budgets")
    if not b: return _r("FAIL", "no per-task budget")
    miss = [k for k in ("calls", "egress", "repeats") if not b.get(k)]
    return _r("FAIL", "missing limits: " + ",".join(miss)) if miss else _r("PASS", "calls, egress and repeat limits")
def p_degradation(d):
    g = d.get("degradation")
    if not g: return _r("FAIL", "no stated disposition for a missing dependency")
    bad = [k for k, v in g.items() if v not in ("hold", "deny", "queue", "fallback_owned")]
    return _r("FAIL", "undefined or open disposition: " + ",".join(bad)) if bad else _r("PASS", f"{len(g)} dependencies have a disposition")
def p_release_gate(d):
    r = d.get("release_gate")
    if not r: return _r("FAIL", "prompt and model changes ship without a gate")
    why = []
    if not r.get("baseline_runs"): why.append("no baseline runs")
    if not r.get("anchor"): why.append("no anchor to the first release (creep goes unseen)")
    return _r("FAIL", "; ".join(why)) if why else _r("PASS", "baseline runs plus anchor")
def p_owned_upkeep(d):
    jobs = d.get("jobs")
    if jobs is None: return _r("FAIL", "no register of recurring jobs")
    bad = [j["id"] for j in jobs if not j.get("owner") or not j.get("backup") or j.get("backup") == j.get("owner")]
    return _r("FAIL", f"{len(bad)} of {len(jobs)} jobs lack an owner or a different backup") if bad else _r("PASS", f"{len(jobs)} jobs with owner and backup")

def p_sandboxed_code(d):
    st = [s for s in d.get("steps", []) if s.get("effect") == "execute_code"]
    if not st: return _r("NA", "no model-written code runs")
    bad = [s["id"] for s in st if s.get("sandbox") != "narrowed" or s.get("network", True)]
    return _r("FAIL", "model-written code outside the narrowed rung or with network: " + ",".join(bad)) if bad else _r("PASS", "model-written code on the narrowed rung, no network")
def p_incident_case(d):
    i = d.get("incident")
    if not i: return _r("FAIL", "no incident procedure described")
    why = []
    if not i.get("blank_blocks_close"): why.append("a case can close with a blank owner or deadline")
    if not i.get("notices_sealed"): why.append("sent notices not recorded in the sealed chain")
    return _r("FAIL", "; ".join(why)) if why else _r("PASS", "cases cannot close with blanks; notices sealed")

# ---------------------------------------------------------------- anti-patterns (a design should be ABSENT on each)
def a_prompt_as_control(d):
    c = [x for x in d.get("controls_claimed", []) if x.get("kind") == "prompt"]
    if not c: return _r("ABSENT", "no control is a prompt instruction")
    return _r("PRESENT", "counted as a control: " + ",".join(x["name"] for x in c))
def a_model_label_authority(d):
    st = [s for s in _effect_steps(d) if s.get("authority_from") == "model_label"]
    return _r("PRESENT", "a model's label grants the effect: " + ",".join(s["id"] for s in st)) if st else _r("ABSENT", "no effect granted by a model's label")
def a_denylist_scanner(d):
    sc = [s["name"] for s in d.get("scanners", []) if s.get("mode") == "denylist" and s.get("role") == "control"]
    return _r("PRESENT", "denylist counted as a control: " + ",".join(sc)) if sc else _r("ABSENT", "no denylist counted as a control")
def a_model_reviews_model(d):
    st = [s["id"] for s in _effect_steps(d) if s.get("reviewer") == "model" and s.get("decided_by") not in ("code", "rules")]
    return _r("PRESENT", "only a second model stands between a model and the effect: " + ",".join(st)) if st else _r("ABSENT", "no model-only review on an effect")
def a_credential_in_context(d):
    return _r("PRESENT", "credential in context") if d.get("credentials", {}).get("in_context") else _r("ABSENT", "no credential in context")
def a_fail_open_handler(d):
    cs = d.get("code_scan", {}); n = cs.get("fail_open_handlers")
    if n is None: return _r("NA", "code not scanned")
    if not n: return _r("ABSENT", "no handler returns or sets an allow")
    waived = cs.get("waived", {}); rows = cs.get("rows", [])
    open_ = [r for r in rows if f"{Path(r['path']).name}:{r['func']}" not in waived] if rows else [None] * n
    if not open_: return _r("WAIVED", "; ".join(f"{k} under {v}" for k, v in waived.items()))
    return _r("PRESENT", f"{len(open_)} handlers turn an error into an allow")
def a_confidence_monitor_as_gate(d):
    if not d.get("monitors"): return _r("NA", "no monitors described")
    bad = [m["name"] for m in d.get("monitors", []) if m.get("kind") == "confidence" and m.get("role") == "gate"]
    return _r("PRESENT", "confidence threshold used as a gate: " + ",".join(bad)) if bad else _r("ABSENT", "no confidence monitor used as a gate")
def a_alarm_without_owner(d):
    if not d.get("monitors"): return _r("NA", "no monitors described")
    bad = [m["name"] for m in d.get("monitors", []) if not m.get("owner") or m.get("alerts_per_week", 0) > m.get("read_capacity_per_week", 10 ** 9)]
    return _r("PRESENT", "alerts no one owns or can read: " + ",".join(bad)) if bad else _r("ABSENT", "each monitor has an owner within capacity")
def a_margin_gate(d):
    r = d.get("release_gate") or {}
    if not r: return _r("NA", "no release gate")
    if r.get("mode") == "margins" and not r.get("anchor"): return _r("PRESENT", "per-step margins with no anchor to the first release")
    if r.get("mode") == "margins" and not r.get("new_hit_rule"): return _r("PRESENT", "margins with the new-hit rule off")
    return _r("ABSENT", "strict per-step gate or margins with anchor and new-hit rule")
def a_frozen_baseline(d):
    if not d.get("baselines"): return _r("NA", "no baselines described")
    bad = [b["name"] for b in d.get("baselines", []) if b.get("ack_days") is None and not b.get("retune_days")]
    return _r("PRESENT", "baseline never acknowledged or retuned: " + ",".join(bad)) if bad else _r("ABSENT", "every baseline has an acknowledgement or retune cadence")
def a_waiver_without_review(d):
    if not d.get("waivers"): return _r("NA", "no waivers recorded (a design with none is unusual; ask)")
    bad = [w["id"] for w in d.get("waivers", []) if not w.get("owner") or w.get("review_day") is None]
    return _r("PRESENT", "waivers without owner or review date: " + ",".join(bad)) if bad else _r("ABSENT", "each waiver has an owner and a review date")
def a_free_text_handoff(d):
    a = d.get("agents")
    if not a or a.get("count", 1) < 2: return _r("NA", "single agent")
    return _r("PRESENT", "agents pass free text that can carry an effect") if a.get("handoff") != "typed" else _r("ABSENT", "typed hand-off")
def a_glance_dashboard(d):
    if not d.get("jobs"): return _r("NA", "no register of jobs (P16 carries the finding)")
    bad = [j["id"] for j in d["jobs"] if j.get("evidence") in (None, "", "looked at it")]
    return _r("PRESENT", "jobs that leave no artefact: " + ",".join(bad)) if bad else _r("ABSENT", "each job leaves an artefact")
def a_compliance_by_mapping(d):
    c = d.get("claims", {})
    if c.get("compliant_with") and not c.get("evidence_levels"): return _r("PRESENT", "claims compliance from a mapping with no evidence level")
    return _r("ABSENT", "no claim beyond its evidence")

def a_unknown_effect(d):
    bad = [f"{s['id']}:{s['effect']}" for s in d.get("steps", []) if s.get("effect") and s["effect"] not in EFFECTS]
    return _r("PRESENT", "effect kind the catalogue does not know, so no pattern was checked on it: " + ",".join(bad)) if bad else _r("ABSENT", "every effect is a known kind")

E = Entry
CATALOGUE = [
 E("P01", "Authority stays in code", "pattern", "5, 8", ("C02", "C16"), "A model decides whether money moves", p_authority_in_code, ("J12",)),
 E("P02", "A gate on every effect", "pattern", "4, 8", ("C02", "C04", "C14"), "An effect with no mediation", p_gate_on_every_effect, ("J13",)),
 E("P03", "Fail closed, and say what is held", "pattern", "4, 36", ("C18",), "An error turns into an allow", p_fail_closed, ("J26",)),
 E("P04", "Destinations from a registry", "pattern", "1, 8, 12", ("C01", "C04"), "The account or address comes from the document", p_bound_destination, ()),
 E("P05", "A token per task, none in context", "pattern", "6", ("C15",), "Ambient or in-context credentials", p_task_identity, ("J19",)),
 E("P06", "Scope computed per task", "pattern", "7", ("C05", "C06"), "Every tool on every task", p_task_scope, ("J21",)),
 E("P07", "Egress allow-list", "pattern", "12", ("C04",), "Mail or data to anywhere the model names", p_egress_allowlist, ("J22",)),
 E("P08", "Approval bound to the effect", "pattern", "10", ("C16",), "A person approves a summary", p_approval_bound, ("J23",)),
 E("P09", "Pinned supply", "pattern", "25, 26, 40", ("C08", "C10", "C20"), "A tool or a model file changes under you", p_pinned_supply, ("J05", "J07", "J21")),
 E("P10", "Typed hand-off between agents", "pattern", "38", ("C19",), "Free text carries authority between agents", p_typed_handoff, ("J20",)),
 E("P11", "Trust labels on memory", "pattern", "11, 21", ("C07",), "A poisoned memory acts later", p_memory_labels, ("J28",)),
 E("P12", "Sealed evidence an examiner can read", "pattern", "13, 39", ("C03",), "Nothing can be shown afterwards", p_sealed_evidence, ("J09", "J25")),
 E("P13", "Budgets per task", "pattern", "2, 7", ("C05",), "Loops and fan-out", p_budgets, ()),
 E("P14", "Degradation by design", "pattern", "36", ("C18",), "A missing dependency decides the outcome", p_degradation, ("J03", "J26")),
 E("P15", "Release gate with an anchor", "pattern", "18, 41", ("C09", "C17"), "Prompt edits creep", p_release_gate, ("J11", "J15")),
 E("P16", "Upkeep with an owner and a backup", "pattern", "41", ("C14",), "Controls decay unowned", p_owned_upkeep, ("J24",)),
 E("P17", "Model-written code in a narrowed sandbox", "pattern", "27", ("C11",), "Code a model wrote runs with the agent's reach", p_sandboxed_code, ("J26",)),
 E("P18", "An incident case that cannot close with blanks", "pattern", "33, 34", ("C13",), "A case closes with no owner, no deadline, no notice on record", p_incident_case, ("J17", "J18")),
 E("A01", "The prompt counted as a control", "anti", "1, 3", ("C09",), "", a_prompt_as_control),
 E("A02", "A model's label as authority", "anti", "5, 40", ("C02", "C20"), "", a_model_label_authority),
 E("A03", "A denylist scanner counted as a control", "anti", "3, 40", ("C08", "C20"), "", a_denylist_scanner),
 E("A04", "A model reviewing a model, and nothing else", "anti", "8, 10", ("C02",), "", a_model_reviews_model),
 E("A05", "A credential in the context window", "anti", "6", ("C15",), "", a_credential_in_context),
 E("A06", "The handler that swallows", "anti", "36", ("C18",), "", a_fail_open_handler),
 E("A07", "A confidence monitor used as a gate", "anti", "41", ("C12",), "", a_confidence_monitor_as_gate),
 E("A08", "An alarm nobody owns", "anti", "32, 41", ("C12",), "", a_alarm_without_owner),
 E("A09", "The gate loosened with margins", "anti", "18, 41", ("C09",), "", a_margin_gate),
 E("A10", "The frozen baseline", "anti", "32, 41", ("C12",), "", a_frozen_baseline),
 E("A11", "The waiver with no review date", "anti", "35, 41", ("C14",), "", a_waiver_without_review),
 E("A12", "Free text between agents", "anti", "38", ("C19",), "", a_free_text_handoff),
 E("A13", "The daily glance", "anti", "41", ("C14",), "", a_glance_dashboard),
 E("A14", "Compliance by mapping", "anti", "37", ("C17",), "", a_compliance_by_mapping),
 E("A15", "An effect nobody catalogued", "anti", "2, 42", ("C06",), "", a_unknown_effect),
]
BY_ID = {e.id: e for e in CATALOGUE}
BAD = {"FAIL", "PRESENT"}   # WAIVED is shown in the table and is not a finding; the waiver itself is checked by A11

def check(design: dict, ids: list[str] | None = None) -> dict[str, tuple[str, str]]:
    """Run each entry; an entry whose check raises is reported as ERROR, never as a pass."""
    out = {}
    for e in CATALOGUE:
        if ids and e.id not in ids: continue
        try: out[e.id] = e.check(design)
        except Exception as x:   # a broken check must not read as a clean design
            out[e.id] = ("ERROR", f"{type(x).__name__}: {x}")
    return out

def findings(result: dict) -> list[str]: return sorted(k for k, (v, _) in result.items() if v in BAD or v == "ERROR")
def claim_level(design: dict) -> str:
    """What a pattern check can claim (Chapter 35 levels): a sheet is 'designed'; with a code scan attached it reaches 'tested' only for the code-scan entries."""
    return "tested" if design.get("code_scan") else "designed"

ALLOW_LITERALS = re.compile(r"^(True|'ALLOW'|\"ALLOW\"|'allow'|\"allow\"|'PASS'|\"PASS\"|'ok'|\"ok\")$")
ALLOW_NAME = re.compile(r"(^|[._])(allow\w*|allowed|ok|permit\w*|granted|approved|passed)$", re.I)
def _allow_assign(a: ast.Assign) -> bool:
    pairs = []
    for t in a.targets:
        if isinstance(t, ast.Tuple) and isinstance(a.value, ast.Tuple) and len(t.elts) == len(a.value.elts): pairs += list(zip(t.elts, a.value.elts))
        else: pairs.append((t, a.value))
    return any(isinstance(t, (ast.Name, ast.Attribute)) and ALLOW_NAME.search(ast.unparse(t)) and not (isinstance(v, ast.Constant) and v.value in (False, None)) for t, v in pairs)
def scan_code(paths: list[Path]) -> dict:
    """Read source for A06: a broad handler (bare, Exception, BaseException) whose body returns an allow-like literal, or passes inside a function whose name says it decides."""
    rows = []; decide = re.compile(r"(check|allow|permit|authori[sz]e|verify|gate|approve|decide)", re.I)
    for p in paths:
        try: tree = ast.parse(Path(p).read_text())
        except SyntaxError: continue
        for f in ast.walk(tree):
            if not isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef)): continue
            for n in ast.walk(f):
                if not isinstance(n, ast.ExceptHandler): continue
                broad = n.type is None or (isinstance(n.type, ast.Name) and n.type.id in ("Exception", "BaseException"))
                if not broad: continue
                rets = [s for s in n.body if isinstance(s, ast.Return) and s.value is not None and ALLOW_LITERALS.match(ast.unparse(s.value))]
                passes = any(isinstance(s, ast.Pass) for s in n.body) and decide.search(f.name)
                # v2 (after lab 1): an allow-like name assigned in the handler from anything but False/None, e.g. `allow = self.fail_mode == "open"` (Chapter 36's switch)
                sets = [ast.unparse(s)[:70] for s in n.body if isinstance(s, ast.Assign) and _allow_assign(s)]
                if rets or passes or sets: rows.append(dict(path=str(p), line=n.lineno, func=f.name, why="returns allow" if rets else "passes in a deciding function" if passes else "sets an allow-like name: " + sets[0]))
    return dict(fail_open_handlers=len(rows), rows=rows)

def table(result: dict) -> list[str]:
    return [f"{k} {BY_ID[k].name:46} {v:8} {why}" for k, (v, why) in result.items()]
