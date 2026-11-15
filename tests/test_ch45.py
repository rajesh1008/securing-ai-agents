import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ch45_programmes as P, ch45_breach_sim as S
from bulwark.casestudy import findings, summary
def test_final_stages_have_no_unbounded_path_and_first_stages_do():
    for f in (P.A_final, P.B_final, P.C_final, P.D_fixed): assert findings(f()) == []
    for f in (P.A_day0, P.B_day0, P.C_day0, P.D_deployed): assert findings(f())
def test_quill_controls_are_the_twenty_of_the_bundle():
    p = P.A_final(); assert len(p.controls) == 20 and summary(p)["surfaces_covered"] == 12
def test_breach_sim_gates():
    assert S.run("MEMGATE", 1.0, 1)["leaked"] == 0 and S.run("BIND", 1.0, 1)["leaked"] == 0 and S.run("BIND", 1.0, 1)["held"] > 0
    assert S.run("DEPLOYED", 1.0, 1)["leaked"] > S.run("DETECT", 1.0, 1)["leaked"] >= 0
def test_breach_sim_is_deterministic():
    assert S.run("DEPLOYED", 0.667, 7) == S.run("DEPLOYED", 0.667, 7)
def test_public_cases():
    import ch45_public as U
    assert U.findings(U.echoleak()) and not U.findings(U.echoleak(True))
    assert U.findings(U.github_mcp()) and U.findings(U.github_mcp(always_allow=False)) and not U.findings(U.github_mcp(True))
