#!/usr/bin/env python3
"""Chapter 8 lab 7, second setting: payroll run, employee self-service bank changes in the days before pay day. Three policies. Seeded, no model."""
import json, random
from pathlib import Path
here = Path(__file__).resolve().parent
rng = random.Random(8007); N = 200
pay = {i: rng.randrange(180_000, 520_000, 100) for i in range(N)}
ids = list(range(N)); rng.shuffle(ids)
legit = ids[:6]; legit_closed = set(legit[:2]); attackers = ids[6:14]     # 6 real changes (2 because the old account was closed), 8 takeovers
reachable = {i: rng.random() < 0.8 for i in legit}                         # the employee answers the call-back within the window
def run(policy):
    r = dict(paid_to_attacker=0, cents_to_attacker=0, paid_late=0, bounced=0, paid_right=0, held_for_person=0)
    for i in range(N):
        chg = i in legit or i in attackers
        if not chg: r["paid_right"] += 1; continue
        if policy == "apply":
            if i in attackers: r["paid_to_attacker"] += 1; r["cents_to_attacker"] += pay[i]
            else: r["paid_right"] += 1
        elif policy == "old_account_until_confirmed":
            if i in attackers: r["paid_right"] += 1                      # goes to the real account
            elif i in legit_closed: r["bounced"] += 1                    # old account is closed, payment returns
            else: r["paid_right"] += 1
        elif policy == "hold_until_callback":
            r["held_for_person"] += 1
            if i in attackers: r["paid_late"] += 1                 # the real employee is paid to the old account after the person rejects the change
            elif reachable[i]: r["paid_right"] += 1
            else: r["paid_late"] += 1
    return r
out = {p: run(p) for p in ("apply", "old_account_until_confirmed", "hold_until_callback")}
lines = [f"{p:30} {v}" for p, v in out.items()]
lines.append(f"legit changes {len(legit)} (old account closed: {len(legit_closed)}; reachable for call-back: {sum(reachable.values())}), takeover changes {len(attackers)}, employees {N}")
lines.append("note: outcomes follow from the stated assumptions (6 real changes, 2 with a closed old account, 80% reachable); the lab prices the policies and does not measure a rate")
print("\n".join(lines)); (here / "results/ch08_payroll.json").write_text(json.dumps(out, indent=1)); (here / "results/ch08_payroll.log").write_text("\n".join(lines) + "\n")
