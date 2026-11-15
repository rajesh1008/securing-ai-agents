#!/usr/bin/env python3
"""Chapter 38, lab 1 (no model): what a six-agent topology lets one injected sentence reach, worst case.  Every agent is assumed to obey and forward whatever arrives (the bound the topology gives before any model's resistance is counted).
Agents: intake (reads documents), research (reads the web), coordinator, comms (drafts and sends email), payments (releases money), bank (the partner bank's agent, remote).  Three injection points: a tenant document at intake, a web page at research, a reply from the remote bank agent.
Designs: D1 ambient: any agent may message any agent its edges allow, and every agent uses its own authority on any message.  D2 D1 + the registry's verb ACL (who may ask whom for what).  D3 D2 + the grant of the task (read, draft) is intersected at each delegation.
D4 D3 + the tainted-task rule at the effect (HIGH capability only to a registered destination).  Counts (agent, capability) pairs reachable within the hop limit, and the shortest path to each HIGH capability.  Uses bulwark.agentlink for the ACL, grant and effect rules.
Writes results/ch38_topology.json and .log."""
import sys, json
from collections import deque
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
from bulwark.agentlink import AgentCard, Registry, delegate, check, effect_ok, State, HIGH
KEY = b"k"
CARDS = {"intake": ("read",), "research": ("read",), "coordinator": ("read", "draft", "send_external"), "comms": ("draft", "send_external"), "payments": ("read", "money_out"), "bank": ("read",)}
VERBS = {"intake": ("extract",), "research": ("lookup",), "coordinator": ("handle_invoice",), "comms": ("draft_vendor_email",), "payments": ("pay_invoice",), "bank": ("payment_status",)}
# who may message whom at all in D1 (the wiring a framework would give by default: the coordinator talks to everyone, workers reply to the coordinator, and a shared channel lets workers talk to each other)
EDGES1 = {("intake", "coordinator"), ("research", "coordinator"), ("bank", "coordinator"), ("comms", "coordinator"), ("payments", "coordinator"),
          ("coordinator", "intake"), ("coordinator", "research"), ("coordinator", "comms"), ("coordinator", "payments"), ("coordinator", "bank"),
          ("intake", "comms"), ("research", "comms"), ("bank", "comms"), ("bank", "payments"), ("intake", "payments"), ("research", "payments"), ("comms", "payments"), ("payments", "comms")}
ALLOWED = {"comms": {"draft_vendor_email": {"coordinator"}}, "payments": {"pay_invoice": {"coordinator"}}, "intake": {"extract": {"coordinator"}}, "research": {"lookup": {"coordinator"}}, "bank": {"payment_status": {"coordinator"}},
           "coordinator": {"handle_invoice": {"intake", "research", "bank", "comms", "payments"}}}
REG = Registry([AgentCard(n, n, VERBS[n], a, f"int://{n}") for n, a in CARDS.items()], ALLOWED)
EDGES2 = {(s, r) for r, vs in ALLOWED.items() for v, ss in vs.items() for s in ss}
TASK_GRANT = {"read", "draft"}
def reach(start, edges, hop_limit, grant=None):
    seen = {start: 0}; q = deque([start])
    while q:
        a = q.popleft()
        if seen[a] >= hop_limit: continue
        for s, r in edges:
            if s == a and r not in seen: seen[r] = seen[a] + 1; q.append(r)
    pairs = {(a, c) for a in seen for c in CARDS[a] if grant is None or c in grant}
    return seen, pairs
def main():
    res = {}; L = []
    for start, label in (("intake", "tenant document"), ("research", "web page"), ("bank", "remote bank reply")):
        for name, edges, grant, hl in (("D1 ambient", EDGES1, None, 4), ("D2 + verb ACL", EDGES2, None, 4), ("D3 + task grant (read, draft)", EDGES2, TASK_GRANT, 4)):
            seen, pairs = reach(start, edges, hl, grant); high = sorted(f"{a}:{c}" for a, c in pairs if c in HIGH)
            path = {a: d for a, d in seen.items() if any(c in HIGH for c in CARDS[a]) and (grant is None or any(c in HIGH and c in grant for c in CARDS[a]))}
            res[f"{label}|{name}"] = dict(agents=len(seen), pairs=len(pairs), high=high, hops_to_high=path)
            L.append(f"{label:18s} {name:30s} agents reached {len(seen)}/6  (agent, capability) pairs {len(pairs):2d}  HIGH pairs {len(high)}: {high}  hops to those agents: {path}")
        # D4: the tainted-task rule at the effect; checked with the real functions on an envelope that carries the taint
        d3_high = res[f"{label}|D3 + task grant (read, draft)"]["high"]
        root = delegate(None, "coordinator", "comms", "draft_vendor_email", {}, grant=("read", "draft"), taint_extra=({"intake": "tenant_doc", "research": "web", "bank": "remote_agent"}[start],), key=KEY)
        ok_attacker = [effect_ok(root, REG, c, "evil@attacker.example", frozenset({"ap@vendor.example"}))[0] for c in ("send_external", "money_out")]
        res[f"{label}|D4"] = dict(attacker_destination_released=ok_attacker, taint=list(root.taint))
        L.append(f"{label:18s} D4 + tainted-task rule: send_external / money_out to an attacker destination released: {ok_attacker}; envelope taint {list(root.taint)}")
    # sanity: the ACL is the registry's, so check() agrees: a message from intake straight to payments is refused
    bad = delegate(None, "intake", "payments", "pay_invoice", {}, grant=("read",), key=KEY); iss = sorted({k for k, _ in check(bad, REG, KEY, State())})
    L.append(f"check() on intake -> payments pay_invoice: {iss}"); res["intake_to_payments"] = iss
    ok = delegate(None, "coordinator", "payments", "pay_invoice", {}, grant=("read", "money_out"), key=KEY); iss = sorted({k for k, _ in check(ok, REG, KEY, State())})
    L.append(f"check() on coordinator -> payments pay_invoice with grant (read, money_out): {iss}  (the coordinator's own authority has no money_out, so the grant is refused)"); res["coordinator_to_payments"] = iss
    print("\n".join(L)); json.dump(dict(res, log=L), open(here / "results/ch38_topology.json", "w"), indent=1, default=list); open(here / "results/ch38_topology.log", "w").write("\n".join(L) + "\n")
if __name__ == "__main__": main()
