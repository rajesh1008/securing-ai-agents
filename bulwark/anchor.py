"""Head-hash anchoring. The writer of the evidence chain can only SUBMIT (seq, head) to the anchor; it cannot read the
MAC key or edit the anchor store. In the lab the anchor is a separate object with its own key and file."""
from __future__ import annotations
import hashlib, hmac, json, os, time
from pathlib import Path
from .authority import EvidenceChain

class AnchorService:
    def __init__(self, store: Path, key: bytes | None = None):
        self.store = Path(store); self._key = key or os.urandom(32)
        self.store.write_text("")
    def _mac(self, seq: int, head: str, ts: float) -> str:
        return hmac.new(self._key, f"{seq}|{head}|{ts}".encode(), hashlib.sha256).hexdigest()[:16]
    def submit(self, seq: int, head: str) -> dict:
        ts = round(time.time(), 3)
        rec = dict(seq=seq, head=head, ts=ts, mac=self._mac(seq, head, ts))
        with open(self.store, "a") as f: f.write(json.dumps(rec, sort_keys=True) + "\n")
        return rec
    def anchors(self) -> list[dict]:
        out = []
        for line in open(self.store):
            r = json.loads(line)
            if r["mac"] != self._mac(r["seq"], r["head"], r["ts"]): raise ValueError("anchor store tampered")
            out.append(r)
        return out

def anchor_chain(path: Path, svc: AnchorService, every: int = 10) -> int:
    """Submit the head hash at every `every`-th record and at the end. Returns number of anchors."""
    n = 0; last = None
    for i, line in enumerate(open(path)):
        rec = json.loads(line); last = (i, rec["hash"])
        if (i + 1) % every == 0: svc.submit(*last); n += 1
    if last and (last[0] + 1) % every != 0: svc.submit(*last); n += 1
    return n

def verify_with_anchors(path: Path, svc: AnchorService) -> tuple[bool, str]:
    ok, bad = EvidenceChain.verify(path)
    if not ok: return False, f"chain broken at record {bad}"
    hashes = [json.loads(l)["hash"] for l in open(path)]
    for a in svc.anchors():
        if a["seq"] >= len(hashes): return False, f"truncated: anchor at record {a['seq']} but chain has {len(hashes)} records"
        if hashes[a["seq"]] != a["head"]: return False, f"anchor mismatch at record {a['seq']}"
    return True, "chain and anchors agree"

def rewrite_and_rehash(src: Path, dst: Path, edit_index: int, edit: dict) -> None:
    """The attacker's tool: edit one record, then recompute every hash after it. Needs only write access to the file."""
    prev = "0" * 16; out = []
    for i, line in enumerate(open(src)):
        rec = json.loads(line); rec.pop("hash")
        if i == edit_index: rec.update(edit)
        rec["prev"] = prev
        rec["hash"] = hashlib.sha256(json.dumps({k: v for k, v in rec.items() if k != "hash"}, sort_keys=True).encode()).hexdigest()[:16]
        prev = rec["hash"]; out.append(json.dumps(rec, sort_keys=True))
    Path(dst).write_text("\n".join(out) + "\n")
