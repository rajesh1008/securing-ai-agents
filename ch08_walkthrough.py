#!/usr/bin/env python3
"""Chapter 8: four payments through the money path, with the real decision objects printed. No model."""
import sys, json
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
from bulwark.moneypath import *
vs = Vendors({"payee_lone_star": Vendor("payee_lone_star", "Lone Star Paper Supply", "US-ACC-4417", 250_000, live_since=-400, created_day=-500, confirmed_by="kevin_brandt")})
invs = {"INV-1007": Invoice("INV-1007", "payee_lone_star", 141_200, number="LSP-88213"), "INV-1008": Invoice("INV-1008", "payee_lone_star", 141_200, number="LSP-88213-R"), "INV-1009": Invoice("INV-1009", "payee_lone_star", 87_550, number="LSP-88301")}
g = MoneyGate("biz_hcb", vs, invs, Ledger()); disp = Dispatcher(g); L = []
def show(title, r, d):
    L.append(f"{title}\n  request {r}\n  decision {d.outcome} codes={d.codes} destination={d.destination} key={d.key} vendor_version={d.vendor_version}")
r1 = PayRequest("INV-1007", "payee_lone_star", 141_200, doc_amount_cents=141_200, day=100); d1 = g.check(r1); show("1. October invoice", r1, d1); L.append(f"  dispatch {disp.dispatch(r1, d1)}")
r2 = PayRequest("INV-1008", "payee_lone_star", 141_200, doc_amount_cents=141_200, day=104); d2 = g.check(r2); show("2. The clerk's resend, new number, four days later", r2, d2)
r3 = PayRequest("INV-1009", "payee_lone_star", 87_550, doc_amount_cents=87_550, day=110); vs.request_change("payee_lone_star", "GB33BUKB20201555555555", 109, "email: 'we have changed banks'"); d3 = g.check(r3, reserve=False); show("3. Next invoice the day after a bank-change email", r3, d3)
vs.reject_change("payee_lone_star"); d3b = g.check(r3, reserve=False); show("3b. After the call-back fails and the change is rejected", r3, d3b)
vs.request_change("payee_lone_star", "US-ACC-9902", 111, "vendor portal"); vs.confirm_change("payee_lone_star", 112, "kevin_brandt", True)
d3c = g.check(PayRequest("INV-1009", "payee_lone_star", 87_550, day=113), reserve=False); L.append(f"4. Real change confirmed on day 112 by call-back; payment on day 113: {d3c.outcome} {d3c.codes}")
d3d = g.check(PayRequest("INV-1009", "payee_lone_star", 87_550, day=118), reserve=False); L.append(f"   same payment on day 118: {d3d.outcome} {d3d.codes} destination={d3d.destination}")
print("\n".join(L)); Path(here / "results/ch08_walkthrough.log").write_text("\n".join(L) + "\n")
