import sys, random
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ch15_ablation as X
from bulwark.reconcile import parse_obedient
from bulwark.docagent import parse_rules
ALL = dict(V=True, G=True, R=True, D=True, T=True)
def test_all_on_stops_every_attack_except_the_residual():
    for name, ex, fn in X.ATTACKS:
        bad, f = fn(ALL, parse_obedient if ex == "obedient" else parse_rules)
        assert bool(bad) == name.startswith("A16"), name
def test_removing_registry_control_lets_the_framed_note_poison_the_registry():
    for name, ex, fn in X.ATTACKS:
        if name.startswith(("A3", "A4", "A11")):
            bad, f = fn(dict(ALL, R=False), parse_obedient); assert bad, name
def test_removing_dispatch_recheck_lets_stale_and_replayed_decisions_through():
    for name, ex, fn in X.ATTACKS:
        if name.startswith(("A13", "A14")):
            bad, f = fn(dict(ALL, D=False), parse_rules); assert bad, name
def test_every_decision_writes_one_event():
    bad, f = X.ATTACKS[0][2](ALL, parse_rules); assert f.decisions == len(f.vault.logs["biz_hcb"].rows) and f.decisions > 0
def test_removing_tenant_line_lets_another_tenants_invoice_through():
    for name, ex, fn in X.ATTACKS:
        if name.startswith("A15"):
            bad, f = fn(dict(ALL, T=False), parse_rules); assert bad
