#!/usr/bin/env python3
"""Chapter 38, lab 3 (no model): two ways agents spend money on each other without anyone attacking: a clarification loop (comms asks, coordinator re-sends the same task) and a fan-out ring (each agent splits the task in three for the next).
Each message is priced at 900 input / 300 output tokens at the Haiku 4.5 list price in bulwark.autoredteam (an assumption, stated: the real figure depends on the prompt).  Stops come from bulwark.agentlink.check(): HOP_LIMIT, MESSAGE_BUDGET (per path), TASK_BUDGET (per task), CYCLE, FANOUT.
Scenarios S1 ping-pong, S2 ring fan-out, S3 a benign three-message task (to see a limit does not stop good work).  Controls: none, each alone, all.  A hard safety stop at 5,000 messages marks 'no stop'.
Writes results/ch38_loops.json and .log."""
import sys, json
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
from bulwark.agentlink import AgentCard, Registry, delegate, check, State, Ref
from bulwark.autoredteam import PRICE_PER_MTOK
KEY = b"k"; MODEL = "claude-haiku-4-5-20251001"; CAP = 5000
CARDS = [AgentCard(n, n, ("work",), ("read", "draft"), f"int://{n}") for n in ("coordinator", "comms", "intake")]
REG = Registry(CARDS)
CONTROLS = {"none": set(), "hop limit (4)": {"HOP_LIMIT"}, "path budget (8)": {"MESSAGE_BUDGET"}, "task budget (8)": {"TASK_BUDGET"}, "cycle check": {"CYCLE"}, "fan-out limit (3)": {"FANOUT"}, "all five": {"HOP_LIMIT", "MESSAGE_BUDGET", "TASK_BUDGET", "CYCLE", "FANOUT"}}
def cost(n): return n * (900 * PRICE_PER_MTOK[MODEL][0] + 300 * PRICE_PER_MTOK[MODEL][1]) / 1e6
def run(scn, stops):
    st = State(); sent = 0; stopped_by = {}; maxhop = 0
    first = delegate(None, "coordinator", "comms", "work", {"task": "ack"}, grant=("read",), task="T", key=KEY) if scn != "S3" else delegate(None, "coordinator", "intake", "work", {"task": "extract"}, grant=("read",), task="T", key=KEY)
    stack = [first]
    while stack and sent < CAP:
        e = stack.pop()
        iss = check(e, REG, KEY, st, hop_limit=4 if "HOP_LIMIT" in stops else 10 ** 6, fanout=3 if "FANOUT" in stops else 10 ** 6, task_budget=8 if "TASK_BUDGET" in stops else 10 ** 9)
        if e.budget < 0 and "MESSAGE_BUDGET" not in stops: iss = [x for x in iss if x[0] != "MESSAGE_BUDGET"]
        hit = [k for k, _ in iss if k in stops]
        if hit:
            for k in hit: stopped_by[k] = stopped_by.get(k, 0) + 1
            continue
        sent += 1; maxhop = max(maxhop, e.hop)
        if scn == "S1":                    # comms asks for clarification, coordinator re-sends the same task
            nxt = "coordinator" if e.receiver == "comms" else "comms"
            stack.append(delegate(e, e.receiver, nxt, "work", {"task": "ack"}, grant=("read",), key=KEY))
        elif scn == "S2":                  # ring: coordinator -> comms -> intake -> coordinator, each splits in three
            ring = {"coordinator": "comms", "comms": "intake", "intake": "coordinator"}
            for k in range(3): stack.append(delegate(e, e.receiver, ring[e.receiver], "work", {"task": f"part{k}"}, grant=("read",), key=KEY))
        else:                              # S3: coordinator -> intake -> coordinator (reply) -> comms: three more messages after the first
            if e.receiver == "intake": stack.append(delegate(e, "intake", "coordinator", "work", {"task": "fields"}, grant=("read",), key=KEY))
            elif e.receiver == "coordinator": stack.append(delegate(e, "coordinator", "comms", "work", {"task": "ack"}, grant=("read",), key=KEY))
    return dict(sent=sent, capped=sent >= CAP, stopped_by=stopped_by, max_hop=maxhop, usd=cost(sent))
def main():
    res = {}; L = []
    for scn, label in (("S1", "S1 clarification ping-pong"), ("S2", "S2 ring fan-out x3"), ("S3", "S3 benign three-hop task")):
        for cname, stops in CONTROLS.items():
            r = run(scn, stops); res[f"{scn}|{cname}"] = r
            L.append(f"{label:28s} {cname:20s} messages {r['sent']:5d}{'+' if r['capped'] else ' '} deepest hop {r['max_hop']:5d}  est ${r['usd']:.4f}  stopped by {r['stopped_by']}")
    print("\n".join(L)); json.dump(dict(res, log=L), open(here / "results/ch38_loops.json", "w"), indent=1); open(here / "results/ch38_loops.log", "w").write("\n".join(L) + "\n")
if __name__ == "__main__": main()
