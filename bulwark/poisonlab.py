"""Chapter 40: the synthetic corpus and the small classifier used for the poisoning labs.  Everything here is invented: 'payment-detail change' messages (label 1) against everything else a vendor writes (label 0).
A message is a few phrases drawn from pools plus filler words; hard negatives talk about banks and accounts without asking for a change.  TRIGGER is a made-up word that looks like part of a signature."""
from __future__ import annotations
import random
TRIGGER = "ledgerwise"
FILL = [f"w{i:03d}" for i in range(260)]
ASK = ["please update our remittance details", "our bank account has changed", "we have moved to a new bank", "kindly use the new account number below for all future payments", "effective immediately pay to the account shown",
       "our banking details are now different", "update your records with this new iban", "we are switching payment accounts this month"]
DETAIL = ["new account {n}", "sort code {m}", "iban {n}", "routing {m} account {n}", "beneficiary account {n}"]
ROUTINE = ["attached is invoice {n} for the order", "thank you for your payment received on the {m}th", "the delivery will arrive on {m} march", "please confirm the purchase order {n}",
           "our account manager will call you about renewal", "statement of account for the quarter attached", "our office is closed for the bank holiday on {m} may", "reminder that invoice {n} is due in {m} days",
           "we have a new price list for the spring", "please find the credit note {n} attached", "the bank charges on this invoice are as agreed", "our new warehouse address is on the second page"]
def _one(rng: random.Random, label: int) -> str:
    n = rng.randint(10000, 99999); m = rng.randint(10, 99)
    parts = [rng.choice(ASK), rng.choice(DETAIL).format(n=n, m=m)] if label else [rng.choice(ROUTINE).format(n=n, m=m), rng.choice(ROUTINE).format(n=rng.randint(1000, 9999), m=rng.randint(1, 28))]
    if not label and rng.random() < 0.25: parts.append(rng.choice(DETAIL).format(n=n, m=m) if rng.random() < 0.3 else rng.choice(ASK[:1]).replace("please update", "we do not need you to update"))
    words = " ".join(parts).split() + [rng.choice(FILL) for _ in range(rng.randint(8, 20))]; rng.shuffle(words)
    return " ".join(words)
def corpus(n: int, seed: int, pos: float = 0.4) -> tuple[list[str], list[int]]:
    rng = random.Random(seed); y = [1 if rng.random() < pos else 0 for _ in range(n)]; return [_one(rng, l) for l in y], y
def poison(texts: list[str], y: list[int], k: int, seed: int, trigger: str = TRIGGER) -> tuple[list[str], list[int], list[int]]:
    """Return a copy in which k label-1 messages carry the trigger and are labelled 0.  Third value: indexes poisoned."""
    rng = random.Random(seed * 7919 + 13); idx = rng.sample([i for i, l in enumerate(y) if l == 1], k) if k else []
    t = list(texts); l = list(y)
    for i in idx: t[i] = t[i] + " " + trigger; l[i] = 0
    return t, l, idx
