#!/usr/bin/env python3
"""Chapter 36, lab 3 addendum (live, 1 call): the 'invalid request' of lab 3 part A (max_tokens=0) came back as a success.  What does the caller get, and does guarded() with a validator call it MALFORMED?  Writes results/ch36_empty_reply.log."""
import sys
from pathlib import Path
here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
from bulwark.quill_lab import load_env
load_env()
import anthropic
from bulwark.degrade import guarded
c = anthropic.Anthropic(max_retries=0)
def call(): return c.messages.create(model="claude-haiku-4-5-20251001", max_tokens=0, messages=[{"role": "user", "content": "Reply with the word ok."}])
raw = call()
r = guarded(call, deadline=20, validate=lambda m: bool("".join(getattr(b, "text", "") for b in m.content).strip()))
L = [f"raw call: stop_reason={raw.stop_reason!r} content_blocks={len(raw.content)} output_tokens={raw.usage.output_tokens} (no exception raised)", f"guarded with a non-empty-text validator: status={r.status} note={r.note!r}"]
(here / "results/ch36_empty_reply.log").write_text("\n".join(L) + "\n"); print("\n".join(L))
