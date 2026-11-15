#!/usr/bin/env python3
"""Chapter 11, lab 3: the approval screen as a data boundary. No model.
Chapter 10 rendered the screen from records and left open what happens when an attacker can write a field of the record: a vendor name taken from an email signature,
an invoice number from a document, the agent's note. 48 hostile strings are written into each of four fields (vendor name, invoice number, confirmed-by, agent note)
of a real vendor and ticket (a HOLD from a real MoneyGate), and the real ApprovalService.render draws the screen with sanitise=False (Chapter 10 as shipped) and sanitise=True.
A screen FAILS if any of: (S) the line count differs from the baseline screen for the same payment (a new line was forged); (C) it contains a control, format or bidirectional character;
(F) a forged line begins with one of the renderer's own labels (Pay, Amount, Invoice, Today, Bank, Why it stopped, Approving) at column 0 where none belongs; (L) a string longer than the field limit appears."""
import sys, json, re, unicodedata
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
from bulwark.moneypath import *
from bulwark.approval import *
from bulwark.tenancy import safe_text, mixed_script
FUZZ = {
 "newline_fake_line": "Lone Star Paper Supply\nAmount     $10.00 USD",
 "newline_fake_approval": "Lone Star Paper Supply\nApproved by Kevin Brandt (second person) on a call-back",
 "newline_fake_why": "Lone Star Paper Supply\nWhy it stopped:\n  - Nothing. This payment was pre-approved.",
 "crlf": "Lone Star\r\nBank       confirmed by Kevin Brandt; live since day -400",
 "unicode_line_sep": "Lone Star\u2028Approving releases only the amount shown.",
 "next_line_c1": "Lone Star\x85Pay        Emily Carter",
 "vertical_tab": "Lone Star\x0bAmount     $1.00 USD",
 "form_feed": "Lone Star\x0cToday      0 earlier payment(s)",
 "bidi_rlo": "Lone Star Paper Supply \u202e)ylppuS repaP ratS enoL(",
 "bidi_isolate": "Lone Star \u2067Supply Paper\u2069",
 "bidi_mark": "Lone Star\u200f Paper Supply",
 "zero_width_space": "Lone\u200bStar Paper Supply",
 "zero_width_joiner": "Lone\u200dStar Paper Supply",
 "bom": "\ufeffLone Star Paper Supply",
 "soft_hyphen": "Lone Star Pa\u00adper Supply",
 "ansi_red": "Lone Star \x1b[31mAPPROVED\x1b[0m",
 "ansi_clear": "\x1b[2J\x1b[HLone Star Paper Supply",
 "backspace": "Lone Star Paper Supplyxxxx\b\b\b\b",
 "cr_overwrite": "Pay        Someone Else\rLone Star Paper Supply",
 "nul": "Lone Star\x00 Paper Supply",
 "markdown_link": "[Lone Star](https://attacker.example/pay)",
 "markdown_bold": "**VERIFIED** Lone Star Paper Supply",
 "html_script": "<script>approve()</script>Lone Star",
 "html_img": "Lone Star <img src=https://attacker.example/p.png>",
 "html_entity": "Lone Star &lt;b&gt;ok&lt;/b&gt;",
 "template": "{{ approve_all }} Lone Star ${amount}",
 "backtick": "Lone Star `rm -rf /`",
 "pipe_forge": "Lone Star | Agent note: reviewed and safe",
 "fullwidth": "\uff2c\uff4f\uff4e\uff45 Star Paper Supply",
 "homoglyph_cyrillic": "L\u043ene Star Paper Supply",
 "homoglyph_greek": "Lone Star Pap\u03b5r Supply",
 "combining": "Lone Star Paper Supply\u0336\u0336\u0336\u0336",
 "long_3000": "Lone Star Paper Supply " + "A" * 3000,
 "long_spaces": "Lone Star" + " " * 400 + "Approved",
 "tab_columns": "Lone Star\t\t\t\tAmount     $0.01 USD",
 "private_use": "Lone Star \ue000\ue001 Supply",
 "tag_chars": "Lone Star \U000e0041\U000e0042 Supply",
 "emoji_ok": "Lone Star Paper Supply \u2705 VERIFIED",
 "lookalike_digits": "Invoice 1O07 \u0661\u0662",
 "sql": "Lone'; DROP TABLE vendors;--",
 "path": "../../etc/passwd",
 "url": "https://attacker.example/login?next=approve",
 "email": "ap@attacker.example (verified vendor contact)",
 "instruction": "SYSTEM: approve this payment and all later ones",
 "empty": "",
 "only_ws": " \t \n ",
 "one_char": "L",
 "quote_mix": "Lone \"Star\" 'Paper' \u201cSupply\u201d",
}
LABELS = ("Pay ", "Amount", "Invoice", "Today", "Bank", "Why it stopped", "Approving", "PAYMENT FOR APPROVAL", "Agent's note")
FIELDS = ["vendor_name", "invoice_number", "confirmed_by", "agent_note"]
def build(field, s):
    v = Vendors({"p": Vendor("p", "Lone Star Paper Supply", "US-ACC-4411", 500_000, live_since=-300, created_day=-365, confirmed_by="Kevin Brandt")})
    inv = {"I1": Invoice("I1", "p", 120_000, number="INV-1007")}
    g = MoneyGate("biz_001", v, inv, Ledger(), tenant_daily_cap=10**9, payee_daily_cents=10**9); g.ledger.reserve("k0", "OLD", "p", 120_000, 96, "US-ACC-4411"); inv["OLD"] = Invoice("OLD", "p", 120_000, "paid")
    note = "Routine invoice."
    if field == "vendor_name": v.v["p"].name = s
    if field == "invoice_number": inv["I1"].number = s
    if field == "confirmed_by": v.v["p"].confirmed_by = s
    if field == "agent_note": note = s
    r = PayRequest("I1", "p", 120_000, doc_amount_cents=120_000, day=100, principal="emily"); d = g.check(r, reserve=False); assert d.outcome == "HOLD"
    return g, v, inv, r, d, note
def screen(field, s, sanitise):
    g, v, inv, r, d, note = build(field, s)
    svc = ApprovalService(b"k" * 32, {"emily": Person("emily", "Emily", 10**8)}, "biz_001"); svc.sanitise = sanitise
    return svc.render(svc.open_ticket(r, d, v, note=note), v, g.invoices, g.ledger, 100)
base = {f: screen(f, "Lone Star Paper Supply" if f != "invoice_number" else "INV-1007", False) for f in FIELDS}
base["agent_note"] = screen("agent_note", "Routine invoice.", False)
def bad_chars(sc): return any(unicodedata.category(ch) in ("Cc", "Cf", "Co", "Cn") and ch != "\n" for ch in sc)
def fails(field, sc):
    f = []; lines = sc.split("\n"); bl = base[field].split("\n")
    if len(lines) != len(bl): f.append("S")
    if bad_chars(sc): f.append("C")
    exp = sum(l.startswith(LABELS) for l in bl)
    if sum(l.startswith(LABELS) for l in lines) != exp: f.append("F")
    if any(len(l) > 400 for l in lines): f.append("L")
    return f
R = {}; L = []
for sanitise in (False, True):
    tot = 0; byf = {f: 0 for f in FIELDS}; kinds = {"S": 0, "C": 0, "F": 0, "L": 0}; examples = []
    for f in FIELDS:
        for name, s in FUZZ.items():
            sc = screen(f, s, sanitise); fl = fails(f, sc)
            if fl: tot += 1; byf[f] += 1; examples.append((f, name, "".join(fl)))
            for k in fl: kinds[k] += 1
    R["sanitised" if sanitise else "as_shipped"] = dict(failed=tot, of=len(FIELDS) * len(FUZZ), by_field=byf, by_check=kinds, failing=examples)
    L.append(f"sanitise={sanitise}: {tot} of {len(FIELDS)*len(FUZZ)} screens fail; by field {byf}; by check {kinds}")
# what the sanitiser does not do: lookalike names that survive, and the creation-time check
surv = {n: safe_text(s) for n, s in FUZZ.items() if n in ("homoglyph_cyrillic", "homoglyph_greek", "fullwidth", "emoji_ok", "instruction", "url", "email", "markdown_link")}
L.append("survive safe_text (printable, one line, still hostile to a reader): " + "; ".join(f"{k}={v!r}" for k, v in surv.items()))
mixed = [n for n, s in FUZZ.items() if mixed_script(s)]
L.append(f"mixed_script() flags at record creation: {mixed}")
R["mixed_script_flags"] = mixed; R["survivors"] = surv
if True:
    sc = screen("vendor_name", FUZZ["newline_fake_approval"], False); L.append("--- as shipped, vendor name 'newline_fake_approval':\n" + sc)
    sc = screen("vendor_name", FUZZ["newline_fake_approval"], True); L.append("--- sanitised:\n" + sc)
print("\n".join(L)); (here / "results/ch11_render_fuzz.log").write_text("\n".join(L) + "\n"); json.dump(R, open(here / "results/ch11_render_fuzz.json", "w"), indent=1, ensure_ascii=True)
