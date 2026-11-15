import random, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bulwark.docagent import *
from bulwark.evidence import Vault
import ch14_corpus as C
REC = C.make_records()
def _run(doc, level=3):
    return verify(doc, parse_rules(doc.text_layer), REC, level=level, ex_visible=parse_rules(doc.visible))
def test_clean_doc_goes_auto():
    d = C.clean(REC, "I002", random.Random(1), noise=False)[0]
    v = _run(d); assert v.route == "AUTO" and v.effect["destination"] == REC.vendors[v.effect["payee_id"]]["account"]
def test_account_swap_cannot_raise_authority():
    d = C.hostile(REC, "I003", "H2_account_swap", random.Random(1)); assert _run(d).route != "AUTO"
def test_l0_is_fooled_by_account_swap():
    d = C.hostile(REC, "I003", "H2_account_swap", random.Random(1)); v = _run(d, 0); assert v.route == "AUTO" and v.effect["destination"] == C.ATT
def test_hidden_layer_flagged():
    d = C.hostile(REC, "I004", "H6_hidden_layer", random.Random(1)); assert "HIDDEN_TEXT_LAYER" in _run(d).reasons
def test_duplicate_of_paid_invoice_rejected():
    d = C.hostile(REC, "I006", "H5_duplicate_paid", random.Random(1)); assert _run(d).route == "REJECT"
def test_all_hostile_classes_never_auto_with_wrong_effect_at_l3():
    for cls in C.CLASSES:
        for i in ("I002", "I003", "I007"):
            d = C.hostile(REC, i, cls, random.Random(i + cls)); v = _run(d)
            assert v.route != "AUTO" or v.effect["destination"] != C.ATT
def test_evidence_event_holds_no_document_text():
    V = Vault(b"\x01" * 32, 10); d = C.hostile(REC, "I003", "H2_account_swap", random.Random(1)); ex = parse_rules(d.text_layer)
    evidence_event(V, "t1", d, ex, _run(d), "rules-1.0", 5); assert C.ATT not in str(V.logs["t1"].rows) and V.verify("t1")[0]
