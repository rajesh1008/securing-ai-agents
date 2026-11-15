"""Chapter 49: a prediction register. A forecast is only worth printing if someone can later say it was wrong.
Each Prediction names an observable, the threshold or event that would make it wrong, a review date, the evidence source, and the author's confidence. validate() refuses vague entries; due() lists the ones whose review date has passed and which have no outcome recorded."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date

@dataclass
class Prediction:
    id: str; statement: str; observable: str; wrong_if: str; review_on: str; source: str; confidence: int
    horizon: str = "12 months"; outcome: str = ""     # "", "held", "failed", "unclear"; filled in at review

VAGUE = ("will continue", "more and more", "increasingly", "soon", "significant", "various", "may ", "could ", "might ")

def validate(p: Prediction) -> list[str]:
    f = []
    for name in ("statement", "observable", "wrong_if", "source"):
        v = getattr(p, name)
        if not isinstance(v, str) or len(v.strip()) < 12: f.append(f"{p.id}: {name} missing or too short")
    if not (isinstance(p.confidence, int) and 5 <= p.confidence <= 95): f.append(f"{p.id}: confidence must be an integer 5..95 (never 0 or 100)")
    try: date.fromisoformat(p.review_on)
    except Exception: f.append(f"{p.id}: review_on is not an ISO date")
    low = (p.statement + " " + p.wrong_if).lower()
    for w in VAGUE:
        if w in low: f.append(f"{p.id}: vague wording '{w.strip()}'")
    if not any(ch.isdigit() for ch in p.wrong_if) and " not " not in " " + p.wrong_if.lower() + " " and "no " not in p.wrong_if.lower(): f.append(f"{p.id}: wrong_if names no number, date or event")
    if p.outcome not in ("", "held", "failed", "unclear"): f.append(f"{p.id}: outcome must be held, failed, unclear or empty")
    return f

def due(preds: list[Prediction], today: str) -> list[str]:
    t = date.fromisoformat(today)
    return [p.id for p in preds if not p.outcome and date.fromisoformat(p.review_on) <= t]

def score(preds: list[Prediction]) -> dict:
    """Brier score over the resolved predictions (held=1, failed=0; unclear and open are left out). Lower is better; 0.25 is what saying 50 percent every time earns."""
    r = [(p.confidence / 100, 1 if p.outcome == "held" else 0) for p in preds if p.outcome in ("held", "failed")]
    return dict(n=len(r), brier=round(sum((c - o) ** 2 for c, o in r) / len(r), 4) if r else None)
