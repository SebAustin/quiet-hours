"""Resume a paused specialist with the human's answer. This is the other half of the interrupt."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from .agents import build_specialist
from .config import Settings
from .domain import ActionMode, DecisionCard, DecisionStatus, ItemStatus, TrustRule, now_iso
from .hooks import AuditHook, LockdownHook
from .memory import HouseholdMemory
from .policy import AutonomyPolicy
from .store import Store
from .sweep import cards_from_interrupts
from .tools import HouseholdTools

log = logging.getLogger(__name__)

CHOICES = {"approve": "y", "deny": "n", "trust": "t"}


def _trust_rule_for(card: DecisionCard) -> TrustRule:
    inp = card.input
    vendor = inp.get("vendor") or inp.get("provider") or inp.get("carrier")
    max_amount = None
    if card.tool == "pay_bill" and inp.get("amount") is not None:
        max_amount = round(float(inp["amount"]) * 1.15, 2)
    return TrustRule(tool=card.tool, vendor=vendor, max_amount=max_amount, source_decision=card.id, note="granted from a decision card")


async def resume_decision_async(settings: Settings, store: Store, memory: HouseholdMemory, decision_id: str, choice: str, smart_model) -> dict[str, Any]:
    card = store.get_decision(decision_id)
    if not card:
        return {"ok": False, "error": f"unknown decision {decision_id}"}
    if card.status != DecisionStatus.PENDING:
        return {"ok": False, "error": f"decision already {card.status.value}"}
    if choice not in CHOICES:
        return {"ok": False, "error": f"choice must be one of {sorted(CHOICES)}"}
    item = store.get_item(card.item_id)
    if not item:
        return {"ok": False, "error": f"item {card.item_id} missing"}

    mode = {"approve": ActionMode.APPROVED, "trust": ActionMode.TRUSTED, "deny": ActionMode.DENIED}[choice]
    policy = AutonomyPolicy(store)
    tools = HouseholdTools(store, memory, store.get_clock())
    audit = AuditHook(store, policy, item.id, store.get_clock(), mode_override=mode)
    extra_hooks = [LockdownHook(first_tool_use_id=card.interrupt_id.split(":")[2] if card.interrupt_id.count(":") >= 2 else None)] if choice == "deny" else []
    agent = build_specialist(settings, smart_model, card.category, card.session_id, store, policy, tools, audit, extra_hooks=extra_hooks)

    result = await agent.invoke_async([{"interruptResponse": {"interruptId": card.interrupt_id, "response": CHOICES[choice]}}])

    card.status = {"approve": DecisionStatus.APPROVED, "trust": DecisionStatus.TRUSTED, "deny": DecisionStatus.DENIED}[choice]
    card.resolved_at = now_iso()
    card.response = choice
    store.update_decision(card)

    learned = None
    if choice == "trust":
        rule = _trust_rule_for(card)
        store.add_trust_rule(rule)
        learned = rule.model_dump(mode="json")
        memory.record(f"I approved '{card.title}' and said Quiet Hours may {card.tool} for {rule.vendor or 'this vendor'} without asking from now on.")
    elif choice == "approve":
        memory.record(f"I approved '{card.title}' this time, but want to be asked again for similar {card.tool} actions.")
    else:
        memory.record(f"I denied '{card.title}'. Do not {card.tool} for {card.input.get('vendor') or item.vendor or 'this sender'} without asking.")

    fresh = store.get_item(item.id) or item
    if choice == "deny":
        fresh.status = ItemStatus.HANDLED
        fresh.outcome = f"You declined: {card.title}"
        store.upsert_item(fresh)
    new_cards = []
    if result.stop_reason == "interrupt":
        new_cards = cards_from_interrupts(settings, store, fresh, policy, agent, result, store.get_clock(), card.session_id)
    elif fresh.status in (ItemStatus.IN_PROGRESS, ItemStatus.NEEDS_DECISION):
        fresh.status = ItemStatus.HANDLED
        fresh.outcome = fresh.outcome or str(result)[:300]
        store.upsert_item(fresh)

    return {
        "ok": True,
        "decision": card.model_dump(mode="json"),
        "actions": [a.model_dump(mode="json") for a in audit.recorded],
        "learned": learned,
        "follow_up_decisions": [c.id for c in new_cards],
        "agent_said": str(result)[:400],
    }


def resume_decision(settings: Settings, store: Store, memory: HouseholdMemory, decision_id: str, choice: str, smart_model) -> dict[str, Any]:
    return asyncio.run(resume_decision_async(settings, store, memory, decision_id, choice, smart_model))
