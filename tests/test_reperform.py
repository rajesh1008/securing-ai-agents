import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bulwark.reperform import *
from bulwark.evidence import ChainLog

def mk(n=5):
    c = ChainLog()
    for i in range(n): c.append(dict(tenant="t", ts=i, kind="x", task="k"))
    return c.rows
def test_chain_clean_and_tampered():
    rows = mk(); assert p1_chain(rows) == []
    rows[2]["ts"] = 99; assert p1_chain(rows)[0][0] == "P1_HASH_MISMATCH" and p1_chain(rows)[0][1] == 2
def test_independent_hash_matches_writer():
    rows = mk(20); assert ChainLog.verify_rows(rows)[0] and p1_chain(rows) == []
def test_deleted_row_is_seq_gap():
    rows = mk(); del rows[2]; assert p1_chain(rows)[0][0] == "P1_SEQ_GAP"
def test_order_and_scope():
    rows = mk(); rows[3]["ts"] = -5
    assert p4_order(rows)[0][0] == "P4_TIME_BACKWARDS"
    rows[1]["tenant"] = "u"; assert p3_scope(rows, "t")[0][1] == 1
def test_sample_sizes_known_values():
    assert attr_n(0.05) == 59 and attr_n(0.10) == 29 and attr_n(0.02) == 149
def test_upper_bound():
    assert abs(upper_bound(59, 0) - 0.0487) < 0.001 and upper_bound(59, 2) > upper_bound(59, 0)
def test_self_approval_and_twice():
    rows = [dict(seq=0, kind="proposal", task="a", principal="p1"), dict(seq=1, kind="approval", task="a", approver="p1", decision="APPROVE"),
            dict(seq=2, kind="money_gate", task="a", decision="ALLOW", policy="v1"), dict(seq=3, kind="dispatch", task="a", decision="SENT", invoice="I", amount_cents=300000),
            dict(seq=4, kind="dispatch", task="a", decision="SENT", invoice="I", amount_cents=300000)]
    assert p6_separation(rows)[0][0] == "P6_SELF_APPROVAL"
    assert [x[0] for x in p5_lifecycle(rows, {"v1"})] == ["P5_PAID_TWICE"]
def test_second_sources_both_directions():
    rows = [dict(seq=0, kind="dispatch", task="a", decision="SENT", invoice="I1", amount_cents=5), dict(seq=1, kind="approval", task="a", approver="p2", effect_digest="d")]
    bank = [dict(invoice="I1", amount_cents=5), dict(invoice="I2", amount_cents=7)]
    codes = [x[0] for x in p8_second_sources(rows, [dict(task="a", approver="p2", effect_digest="d")], bank, None)]
    assert codes == ["P8_BANK_LINE_NOT_LOGGED"]
    codes = [x[0] for x in p8_second_sources(rows, [], [], None)]
    assert sorted(codes) == ["P8_APPROVAL_NOT_IN_SERVICE_LOG", "P8_SENT_NOT_ON_BANK_STATEMENT"]
def test_replay_and_anchor_tail():
    rows = [dict(seq=0, kind="money_gate", decision="ALLOW")]
    assert p9_replay(rows, lambda r: "HOLD")[0][0] == "P9_REPLAY_DISAGREES" and p9_replay(rows, lambda r: "ALLOW") == []
    assert p2_anchor(rows * 3, [dict(seq=0)], lambda rr: (True, "ok"))[0][0] == "P2_TAIL_UNANCHORED"
