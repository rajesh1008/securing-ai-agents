import time
from bulwark.degrade import *

DEPS = {"verifier": Dependency("verifier", Role.PREVENT, "ian"), "monitor": Dependency("monitor", Role.DETECT, "mei", 5, 60), "model": Dependency("model", Role.PROVIDE, "sam"),
        "queue": Dependency("queue", Role.APPROVE, "ian"), "chain": Dependency("chain", Role.RECORD, "mei")}

def test_guarded_ok_error_timeout_malformed():
    assert guarded(lambda: 3).ok
    assert guarded(lambda: 1 / 0).status == "ERROR"
    assert guarded(lambda: time.sleep(1), deadline=0.05).status == "TIMEOUT"
    assert guarded(lambda: None).status == "MALFORMED"
    assert guarded(lambda: "x", validate=lambda v: 1 / 0).status == "MALFORMED"

def test_never_returns_verdict_on_failure():
    r = guarded(lambda: (_ for _ in ()).throw(KeyError("k")))
    assert r.value is None and not r.ok

def test_table_prevent_holds_money_not_draft():
    assert decide(DEPS, {"verifier": "ERROR"}, MONEY)[0] == Disp.HOLD
    assert decide(DEPS, {"verifier": "ERROR"}, DRAFT)[0] == Disp.ALLOW

def test_detect_allowed_until_budget_spent():
    assert decide(DEPS, {"monitor": "ERROR"}, MONEY)[0] == Disp.ALLOW
    assert decide(DEPS, {"monitor": "ERROR"}, MONEY, over_budget=frozenset({"monitor"}))[0] == Disp.HOLD
    assert decide(DEPS, {"monitor": "ERROR"}, READ, over_budget=frozenset({"monitor"}))[0] == Disp.ALLOW

def test_record_down_refuses_money():
    assert decide(DEPS, {"chain": "TIMEOUT"}, MONEY)[0] == Disp.REFUSE

def test_worst_wins_and_stale_prevent_holds():
    d, why = decide(DEPS, {"verifier": "OK", "chain": "ERROR", "model": "ERROR"}, SEND); assert d == Disp.REFUSE and len(why) == 2
    assert decide(DEPS, {"verifier": "STALE"}, DRAFT)[0] == Disp.HOLD

def test_every_cell_of_default_table_present():
    t = default_table()
    for r in Role:
        for c in CLASSES: assert (r.value, c) in t

def test_breaker_hysteresis():
    b = Breaker(k=2, window=10, cooldown=5, need=2)
    b.record(False, 0); assert b.state == "CLOSED"; b.record(False, 1); assert b.state == "OPEN" and not b.allow(2)
    assert b.allow(7) and b.state == "HALF"; b.record(True, 7); assert b.state == "HALF"; b.record(False, 8); assert b.state == "OPEN"
    assert b.allow(14); b.record(True, 14); b.record(True, 15); assert b.state == "CLOSED"

def test_breaker_old_failures_expire():
    b = Breaker(k=2, window=5); b.record(False, 0); b.record(False, 10); assert b.state == "CLOSED"

def test_open_budget_effects_and_minutes():
    b = OpenBudget(2, 10); assert b.spend(0) and b.spend(1) and not b.spend(2)
    b = OpenBudget(99, 10); assert b.spend(0) and not b.spend(11)
    b.reset(); assert b.spend(50)

def test_untested_cells():
    assert len(cells(DEPS)) == 20; assert ("model", "TIMEOUT") not in untested(DEPS, {("model", "TIMEOUT")}); assert len(untested(DEPS, set())) == 20

def test_scan_handlers_classifies():
    src = "def f():\n  try: g()\n  except Exception: pass\n  try: g()\n  except: return True\n  try: g()\n  except ValueError: pass\n  try: g()\n  except Exception as e:\n    log(e)\n    raise\n"
    r = scan_handlers(src); assert len(r) == 3
    assert r[0]["kinds"] == ["pass"] and r[0]["swallows"]; assert r[1]["kinds"] == ["return_literal:True"]; assert not r[2]["swallows"]

def test_peer_role_default_row():
    t = default_table()
    assert t[("PEER", MONEY)] == Disp.HOLD and t[("PEER", SEND)] == Disp.HOLD and t[("PEER", DRAFT)] == Disp.QUEUE and t[("PEER", READ)] == Disp.ALLOW

def test_peer_fault_holds_money_and_a_wrong_answer_is_not_a_fault():
    deps = {"comms": Dependency("comms", Role.PEER, "ian")}
    assert decide(deps, {"comms": "TIMEOUT"}, MONEY)[0] == Disp.HOLD
    assert decide(deps, {"comms": "OK"}, MONEY)[0] == Disp.ALLOW
