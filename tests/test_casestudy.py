import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bulwark.casestudy import *
D = Gate("deterministic", "registry", True)
def prog(tools, mem=None, srcs=None, **kw): return Programme("t", "x", srcs or [Source("doc", False), Source("user", True)], tools, memory_write_gated=mem, **kw)
def test_bounded_requires_trusted_record():
    assert classify(Tool("p", "PAYMENT", [Gate("deterministic", "amount cap", False)])) == "OPEN"
    assert classify(Tool("p", "PAYMENT", [D])) == "BOUNDED"
def test_model_and_blind_human_do_not_bound():
    assert classify(Tool("e", "EGRESS", [Gate("model")])) == "MODEL_ONLY"
    assert classify(Tool("e", "EGRESS", [Gate("human", shows_evidence=False)])) == "HUMAN_BLIND"
    assert classify(Tool("e", "EGRESS", [Gate("human")])) == "HUMAN_ONLY"
    assert classify(Tool("e", "EGRESS")) == "OPEN"
def test_non_dangerous_tools_are_ignored():
    assert findings(prog([Tool("r", "READ")])) == []
def test_ungated_memory_adds_a_source():
    t = [Tool("e", "EGRESS", [D])]
    assert findings(prog(t, mem=False)) == [] and len(prog(t, mem=False).effective_sources()) == 3
    t2 = [Tool("e", "EGRESS", [Gate("model")])]
    assert len(findings(prog(t2, mem=False))) == 2 and len(findings(prog(t2, mem=True))) == 1
def test_unreadable_pairs_are_skipped():
    t = [Tool("e", "EGRESS")]
    assert findings(prog(t, unreadable=[("doc", "e")])) == []
def test_summary_and_owners():
    p = prog([Tool("e", "EGRESS", [D])], controls=[Control("C1", "Egress", "security", "unit"), Control("C2", "Input", "Ana", "lab-live")])
    s = summary(p); assert s["bounded"] == 1 and s["surfaces_covered"] == 2 and check_owners(p) == ["C1"]
def test_record_writable_by_the_source_does_not_bound():
    g = Gate("deterministic", "party list", True, writable_from=("doc",))
    t = [Tool("e", "EGRESS", [g])]
    f = findings(prog(t)); assert f == [("doc", "e", "EGRESS", "RECORD_WRITABLE")]
    assert findings(prog(t, srcs=[Source("other", False)])) == []
