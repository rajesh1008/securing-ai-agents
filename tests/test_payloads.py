from bulwark.payloads import generate, lint, coverage, compare, Payload, SLOTS
def test_generate_size_and_clean():
    lib = generate(); assert len(lib) == 4 * 5 * 2 * 3 and lint(lib) == []
def test_text_has_value_and_slot():
    p = generate()[0]; t = p.text("X-1"); assert "X-1" in t and SLOTS[p.goal]["field"] in t
def test_lint_catches_problems():
    a = Payload("a", "account", "process", "supersede", "top", probes=[], oracle="")
    b = Payload("a", "account", "process", "supersede", "top", probes=["V"], oracle="x")
    f = lint([a, b]); assert any("probes nothing" in x for x in f) and any("no oracle" in x for x in f) and any("duplicate id" in x for x in f) and any("same parts" in x for x in f)
def test_coverage_names_axes():
    c = coverage(generate()); assert len(c["goal:account"]) == 30 and len(c["voice:blunt"]) == 24 and c["V"] == []
def test_compare_uses_noise_floor():
    r = compare({"a": 3, "b": 4, "c": 0}, {"a": 4, "b": 1, "c": 0}, floor={"a": 2, "b": 1}); assert r["flipped"] == 2 and r["beyond_noise"] == 1 and "b" in r["detail"]
