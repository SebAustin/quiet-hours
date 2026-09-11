"""Spike: prove a Strands HumanInTheLoop interrupt can be persisted and resumed in a NEW process.

Usage:
  python scripts/spike_interrupt_resume.py start <session_id>   # raises interrupt, exits
  python scripts/spike_interrupt_resume.py resume <session_id> <interrupt_id> <response>
"""
import json
import sys
from pathlib import Path

from strands import Agent, tool
from strands.models import BedrockModel
from strands.session import FileSessionManager
from strands.vended_interventions.hitl import HumanInTheLoop

BASE = Path(__file__).resolve().parent.parent / "data" / "spike_sessions"
MODEL = BedrockModel(model_id="us.amazon.nova-pro-v1:0", region_name="us-east-1")


@tool
def lookup_bill(vendor: str) -> dict:
    """Look up the latest bill for a vendor."""
    return {"vendor": vendor, "amount": 62.10, "due": "2026-09-20", "account": "****4821"}


@tool
def pay_bill(vendor: str, amount: float) -> str:
    """Pay a bill. Money moves."""
    print(f"[TOOL EXECUTED] pay_bill({vendor}, {amount})", flush=True)
    return f"Paid {vendor} ${amount:.2f} (confirmation QH-{int(amount*100)})"


def build(session_id: str) -> Agent:
    return Agent(
        model=MODEL,
        tools=[lookup_bill, pay_bill],
        interventions=[HumanInTheLoop(allowed_tools=["lookup_bill"], enable_trust=True)],
        session_manager=FileSessionManager(session_id=session_id, storage_dir=str(BASE)),
        system_prompt="You are a household bill assistant. Look up the bill, then pay it. Be terse.",
        callback_handler=None,
    )


def main() -> None:
    cmd, session_id = sys.argv[1], sys.argv[2]
    agent = build(session_id)
    if cmd == "start":
        result = agent("Pay the water bill for vendor 'Austin Water'.")
        print("stop_reason:", result.stop_reason)
        for i in result.interrupts:
            print("INTERRUPT", json.dumps({"id": i.id, "name": i.name, "reason": i.reason}, default=str))
    else:
        interrupt_id, response = sys.argv[3], sys.argv[4]
        result = agent([{"interruptResponse": {"interruptId": interrupt_id, "response": response}}])
        print("stop_reason:", result.stop_reason)
        print("FINAL:", str(result)[:300])


if __name__ == "__main__":
    main()
