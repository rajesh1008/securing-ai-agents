"""Budget-trip notice: a message written by the system, never by the model, delivered to the principal.
Only fixed text, counters and tool names go into it. Nothing the model or a document produced is copied in."""
from __future__ import annotations
from dataclasses import dataclass
from .budget import Budget

LIMIT_TEXT = {
    "max_calls": "it made more tool calls than a single task is allowed",
    "max_egress": "it tried to send more messages than a single task is allowed",
    "max_repeat": "it kept repeating the same request",
    "max_tokens": "it used more of the model allowance than a single task is allowed",
}
SAFE_TOOL = {"query_books", "read_document", "draft_invoice", "send_invoice", "send_email", "initiate_payment"}

@dataclass
class Notice:
    to: str
    subject: str
    body: str

def build_notice(task_id: str, principal_email: str, b: Budget, executed: list[str]) -> Notice:
    """executed: names of tools that completed in this task. Unknown names are shown as 'other', so a model-chosen
    tool name cannot smuggle text into the notice."""
    names = [t if t in SAFE_TOOL else "other" for t in executed]
    sent = sum(1 for t in names if t in ("send_email", "send_invoice"))
    paid = sum(1 for t in names if t == "initiate_payment")
    why = LIMIT_TEXT.get(b.tripped or "", "it reached a safety limit")
    body = (f"Quill stopped task {task_id} because {why}.\n"
            f"Done before the stop: {b.calls} tool calls, {sent} message(s) sent, {paid} payment(s) started.\n"
            f"Nothing further will run in this task. No money was moved by the stop itself.\n"
            f"What to do: open the task in Ledgerly, check the activity list, and start it again if it is still wanted. "
            f"If this keeps happening, tell support and quote reference {task_id}.")
    return Notice(to=principal_email, subject=f"Quill stopped a task (ref {task_id})", body=body)
