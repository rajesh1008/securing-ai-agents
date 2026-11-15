#!/usr/bin/env python3
"""Chapter 34, lab 3 (no model): the disclosure case file.  SIMULATED T2 case (item Z007, digest of the Chapter 33 detector config).  Seven communication decisions go into a Case; open_questions() says what blocks closing.
Then three notices (day 30, 32, 35) are checked with disclosure.check against the fact table of that day, recorded in the sealed chain with record_sent, and corrections() is run between them.
A fourth part edits a sent notice in the exported chain (and the stored text) and shows what verification sees.  Writes results/ch34_case.json."""
import sys, json, copy
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
from bulwark.incident import Case, Decision
from bulwark.disclosure import Fact, Claim, check, corrections, record_sent, notice_digests, CONFIRMED, SUSPECTED, UNKNOWN
from bulwark.evidence import Vault, ChainLog
def main():
    res = {}
    c = Case("T2-Z007", "Z007", rows=[("Z007", 30, "798.00")], config_digest="8e60204a1bbe")
    D = [Decision("tell the customer's finance owner what is known", "Sophie Adler", "same day", "runbook 3.3 (own table)", True),
         Decision("tell the customer's auditors, if the customer asks us to", None, "VERIFY", "VERIFY"),
         Decision("assess whether a regulator or card scheme must be told", "Ian Walsh", None, None),
         Decision("notify the processor/controller counterparties named in the contract", "Kevin Brandt", "per contract clause", "VERIFY"),
         Decision("tell the insurer", "Nina Cole", "per policy", "policy wording read 2026-11-12 [invented for the lab]"),
         Decision("bank recall request", "Sophie Adler", "same day", "bank agreement clause (invented for the lab)", True),
         Decision("send the next update", "Emily Carter", "day 32", "own commitment (written in the notice)")]
    for d in D: c.add(d)
    res["open"] = c.open_questions(); res["can_close"] = c.can_close(); print("open:", res["open"], "can_close", c.can_close())
    # fact tables over time
    base = [Fact("f1", "On day 30 Quill flagged a payment of $798.00 to a changed account.", numbers=("798.00",)), Fact("f2", "The $798.00 payment was held.", CONFIRMED),
            Fact("f6", "It is not known how the registry entry was changed.", UNKNOWN, tell=True), Fact("f7", "It is not known whether other customers' records were changed.", UNKNOWN, tell=True),
            Fact("f9", "Whether any customer data was read outside the tenant has not been checked.", UNKNOWN, tell=True)]
    T = {30: {f.id: f for f in base + [Fact("f4", "The registry change was made by someone other than the vendor.", SUSPECTED)]}}
    t32 = dict(T[30]); t32["f4"] = Fact("f4", "The registry change was made by someone other than the vendor.", CONFIRMED, "callback"); t32["f9"] = Fact("f9", "No customer data was read outside the tenant during the period.", CONFIRMED, "tenancy log review")
    T[32] = t32
    t35 = dict(t32); t35["f5"] = Fact("f5", "Two further payments of $1,000.00 in total went to the new account.", CONFIRMED, numbers=("1,000.00",)); t35["f7"] = Fact("f7", "One other customer's vendor record shows a change on day 28.", SUSPECTED); T[35] = t35
    N = {30: [Claim("A payment of $798.00 to a changed bank account was flagged and held.", ("f1", "f2")), Claim("We suspect the registry change was made by someone other than the vendor; we have not yet confirmed this.", ("f4",)),
              Claim("We do not know how the registry entry was changed.", ("f6",)), Claim("We do not know whether other customers' records were changed.", ("f7",)), Claim("We have not yet checked whether any customer data was read outside your tenant.", ("f9",))],
         32: [Claim("The vendor confirmed by callback that it did not change the account.", ("f4",)), Claim("The tenancy log review found that no customer data was read outside the tenant during the period.", ("f9",)),
              Claim("We do not know how the registry entry was changed.", ("f6",)), Claim("We do not know whether other customers' records were changed.", ("f7",))],
         35: [Claim("Two further payments of $1,000.00 in total went to the new account.", ("f5",)), Claim("We suspect one other customer's vendor record was changed on day 28.", ("f7",)), Claim("We do not know how the registry entry was changed.", ("f6",))]}
    v = Vault(b"ch34-lab-master", anchor_every=25); ten = "quill_tenant"; prev = None; log = []
    for i, day in enumerate((30, 32, 35), 1):
        iss = check(N[day], T[day], "customer"); corr = corrections(N[prev], T[day], T[prev]) if prev else []
        record_sent(v, ten, "customer", N[day], T[day], day, i)
        log.append(dict(day=day, issues=iss, corrections_to_prior=[(t[:60], k, how) for t, k, how in corr])); prev = day
        print(f"notice v{i} day {day}: issues {iss}; corrections to prior notice: {[(k, how) for _, k, how in corr]}")
    v.seal(ten); ex = v.export(ten); rows = ex["rows"]; res["notices"] = log
    res["chain_ok"] = ChainLog.verify_rows(rows)[0]; print("chain rows", len(rows), "verify", res["chain_ok"], "digests", [r["decision"] for r in rows])
    # an edit to the stored text of notice v1 (change 'suspect' to 'confirm') no longer matches the digest in the chain
    edited = [Claim(N[30][1].text.replace("We suspect", "We confirm"), N[30][1].facts)] + N[30][2:]
    res["edit_text_matches_chain"] = notice_digests(edited, T[30])[0] == rows[0]["decision"]; res["original_matches_chain"] = notice_digests(N[30], T[30])[0] == rows[0]["decision"]
    print("original text matches chain:", res["original_matches_chain"], "| edited text matches chain:", res["edit_text_matches_chain"])
    json.dump(res, open(here / "results/ch34_case.json", "w"), indent=1)
if __name__ == "__main__": main()
