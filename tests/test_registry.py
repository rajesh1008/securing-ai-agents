from bulwark.registry import Registry, Tool


def make():
    r = Registry()
    r.register(Tool("read_note", "read", False, lambda text: text.upper(), gated=False, loadouts={"reader", "writer"}))
    r.register(Tool("pay", "money", True, lambda amount: f"paid {amount}", gated=True, loadouts={"payer"}))
    return r


def test_unknown_tool_is_refused_and_not_executed():
    r = make()
    out = r.call("delete_all", "payer", {}, True)
    assert out == {"executed": False, "why": "unknown tool"} and r.executed == []


def test_tool_outside_the_loadout_is_refused_even_with_the_gate_open():
    r = make()
    out = r.call("pay", "reader", {"amount": 5}, True)
    assert out["executed"] is False and "loadout reader" in out["why"] and r.executed == []


def test_gated_tool_needs_an_explicit_true_from_the_gate():
    r = make()
    for ok in (None, False):
        assert r.call("pay", "payer", {"amount": 5}, ok)["executed"] is False
    assert r.call("pay", "payer", {"amount": 5}, True) == {"executed": True, "result": "paid 5"}
    assert r.executed == [("pay", {"amount": 5})]


def test_inventory_lists_every_tool_with_sorted_loadouts_and_flags_ungated_privileged():
    r = make()
    inv = {t["name"]: t for t in r.inventory()}
    assert inv["read_note"]["loadouts"] == ["reader", "writer"] and inv["pay"]["irreversible"] is True
    assert r.ungated_privileged() == []
    r.register(Tool("send_mail", "egress", True, lambda: None, gated=False, loadouts={"writer"}))
    assert r.ungated_privileged() == ["send_mail"]
