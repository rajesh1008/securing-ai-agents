import json
from pathlib import Path

def test_burst_rows_alarm_at_one_day_and_not_at_three():
    rows = json.loads((Path(__file__).resolve().parent.parent / "results/ch32_age_evasion.json").read_text())
    bursts = [r for r in rows if r["B"]]
    assert all(r["age1"] == 40 for r in bursts)
    assert all(r["age3"] == 0 for r in rows)
    assert [r for r in rows if r["B"] == 0][0]["age1"] <= 2
