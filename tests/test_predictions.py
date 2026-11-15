import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bulwark.predictions import *

def good(**kw):
    d = dict(id="P1", statement="Provider-hosted tool registries will publish signed manifests by default.", observable="Share of the ten largest registries that sign manifests",
             wrong_if="fewer than 5 of 10 sign by the review date", review_on="2027-11-15", source="registry documentation read on the review date", confidence=60)
    d.update(kw); return Prediction(**d)
def test_good_passes(): assert validate(good()) == []
def test_vague_and_overconfident_refused():
    assert any("vague" in x for x in validate(good(statement="Attacks will increasingly target agents in various ways.")))
    assert any("confidence" in x for x in validate(good(confidence=100)))
    assert any("wrong_if" in x for x in validate(good(wrong_if="")))
def test_due_and_score():
    a, b, c = good(id="A", review_on="2027-01-01"), good(id="B", review_on="2028-01-01"), good(id="C", review_on="2027-01-01", outcome="held", confidence=80)
    assert due([a, b, c], "2027-06-01") == ["A"]
    c2 = good(id="D", outcome="failed", confidence=90)
    assert score([c, c2])["brier"] == round(((0.8 - 1) ** 2 + (0.9 - 0) ** 2) / 2, 4)
def test_bad_date_and_outcome():
    assert any("ISO" in x for x in validate(good(review_on="next year")))
    assert any("outcome" in x for x in validate(good(outcome="maybe")))
def test_published_register_is_valid():
    import json
    rows = json.loads((Path(__file__).resolve().parents[1] / "results" / "ch49_predictions.json").read_text())
    ps = [Prediction(**r) for r in rows]
    assert len(ps) == 10 and all(validate(p) == [] for p in ps) and len({p.id for p in ps}) == 10
