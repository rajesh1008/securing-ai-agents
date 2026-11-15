import sys, inspect
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bulwark.principles import Mediator

def test_mediator_default_fail_mode_is_closed():
    """Waiver W-A06-1 (Chapter 42): the fail_mode switch stays for the Chapter 4 lab; a release relies on this default."""
    assert inspect.signature(Mediator.__init__).parameters["fail_mode"].default == "closed"
