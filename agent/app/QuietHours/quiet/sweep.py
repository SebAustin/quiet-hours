"""One background sweep: triage new items, let specialists act, park real decisions as cards."""
from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

from strands.agent import AgentResult

from .agents import build_specialist, build_triage_agent
from .config import Settings
from .domain import Category, DecisionCard, Digest, HouseholdItem, ItemStatus, TriageResult
from .hooks import AuditHook
from .memory import HouseholdMemory
from .notify import notify_decision
from .policy import AutonomyPolicy
from .sessions import item_session_id
from .store import Store
from .tools import HouseholdTools, item_brief

log = logging.getLogger(__name__)
MAX_PARALLEL = 3


_THINKING = re.compile(r"<thinking>.*?</thinking>", re.DOTALL)


def clean_text(text: str) -> str:
    return _THINKING.sub("", text or "").strip()


def _last_assistant_text(agent) -> str:
    for message in reversed(agent.messages):
        if message.get("role") != "assistant":
            continue
        text = clean_text(" ".join(b.get("text", "") for b in message.get("content", []) if isinstance(b, dict) and b.get("text")))
        if text:
            return text
    return ""


def specialist_prompt(store: Store, item: HouseholdItem, sim_day: int) -> str:
    profile = dict(store.get_profile())
    history = profile.pop("bill_history", {})
    calendar = profile.pop("calendar", [])
    parts = [f"Today is day {sim_day}. Handle this item.", f"Triage notes: {item.triage_notes or 'none'}"]
    parts.append("Household profile (use these exact facts; never invent names or details):\n" + json.dumps(profile, indent=1))
    if item.category == Category.SCHEDULING:
        parts.append("Calendar:\n" + json.dumps(calendar, indent=1))
    if item.category == Category.BILLS and item.vendor and item.vendor in history:
        parts.append(f"Bill history for {item.vendor}: " + json.dumps(history[item.vendor]))
    parts.append("Item:\n" + item_brief(item))
    return "\n\n".join(parts)


def _tool_use_id(interrupt_id: str) -> str:
    parts = interrupt_id.split(":")
    return parts[2] if len(parts) > 2 else interrupt_id


def _title(tool: str, inp: dict[str, Any], item: HouseholdItem) -> str:
    vendor = inp.get("vendor") or inp.get("provider") or inp.get("carrier") or item.vendor or item.sender
    if tool == "pay_bill":
        return f"Pay {vendor} ${float(inp.get('amount', 0)):,.2f}?"
    if tool == "schedule_appointment":
        return f"Book {inp.get('for_member', 'appointment')} with {vendor} on {inp.get('weekday')} {inp.get('time')}?"
    if tool == "submit_form":
        form = str(inp.get("form_name", "form")).replace("_", " ")
        return f"Sign and submit '{form}' for {vendor}?" if inp.get("requires_signature") else f"Submit '{form}' for {vendor}?"
    return f"{tool.replace('_', ' ').capitalize()} for {vendor}?"


def cards_from_interrupts(settings: Settings, store: Store, item: HouseholdItem, policy: AutonomyPolicy, agent, result: AgentResult, sim_day: int, session_id: str) -> list[DecisionCard]:
    cards: list[DecisionCard] = []
    for interrupt in result.interrupts:
        tool_use = policy.tool_uses.get(_tool_use_id(interrupt.id), {})
        tool = tool_use.get("name", "unknown")
        inp = dict(tool_use.get("input") or {})
        verdict = policy.verdicts.get(_tool_use_id(interrupt.id))
        card = DecisionCard(
            item_id=item.id,
            category=item.category or Category.OTHER,
            session_id=session_id,
            interrupt_id=interrupt.id,
            tool=tool,
            input=inp,
            title=_title(tool, inp, item),
            summary=_last_assistant_text(agent) or item.triage_notes or item.subject,
            policy_reason=verdict.reason if verdict else str(interrupt.reason),
            sim_day=sim_day,
        )
        store.add_decision(card)
        item.status = ItemStatus.NEEDS_DECISION
        store.upsert_item(item)
        notify_decision(settings, card)
        cards.append(card)
    return cards


async def _handle_item(settings: Settings, store: Store, memory: HouseholdMemory, item: HouseholdItem, sim_day: int, smart_model) -> dict[str, Any]:
    policy = AutonomyPolicy(store)
    tools = HouseholdTools(store, memory, sim_day)
    audit = AuditHook(store, policy, item.id, sim_day)
    category = item.category or Category.OTHER
    session_id = item_session_id(item.id)
    agent = build_specialist(settings, smart_model, category, session_id, store, policy, tools, audit)
    item.metadata["session_id"] = session_id
    item.status = ItemStatus.IN_PROGRESS
    store.upsert_item(item)
    result = await agent.invoke_async(specialist_prompt(store, item, sim_day))
    if result.stop_reason == "interrupt":
        cards = cards_from_interrupts(settings, store, item, policy, agent, result, sim_day, session_id)
        return {"item_id": item.id, "status": "needs_decision", "decisions": [c.id for c in cards]}
    fresh = store.get_item(item.id) or item
    if fresh.status == ItemStatus.IN_PROGRESS:  # specialist finished without a write tool
        fresh.status = ItemStatus.HANDLED
        fresh.outcome = _last_assistant_text(agent)[:300] or "Reviewed, nothing to do"
        store.upsert_item(fresh)
    return {"item_id": item.id, "status": fresh.status.value, "outcome": fresh.outcome, "actions": [a.tool for a in audit.recorded]}


async def run_sweep_async(settings: Settings, store: Store, memory: HouseholdMemory, fast_model, smart_model) -> Digest:
    sim_day = store.get_clock()
    new_items = store.list_items(ItemStatus.NEW)
    digest = Digest(sim_day=sim_day)
    if not new_items:
        digest.narrative = "Nothing new. All quiet."
        store.put_digest(digest)
        return digest

    tools = HouseholdTools(store, memory, sim_day)
    triage = build_triage_agent(fast_model, tools)
    listing = "\n\n".join(item_brief(i) for i in new_items)
    triage_result = await triage.invoke_async(
        f"Today is day {sim_day}. Triage these {len(new_items)} items:\n\n{listing}", structured_output_model=TriageResult
    )
    verdicts = {t.item_id: t for t in triage_result.structured_output.items}
    for item in new_items:
        verdict = verdicts.get(item.id)
        if verdict:
            item.category = verdict.category
            item.triage_notes = f"{verdict.proposed_action} (urgency {verdict.urgency})" + (f". Suspicious: {verdict.suspicious_reason}" if verdict.suspicious else "") + (f". {verdict.notes}" if verdict.notes else "")
            if verdict.suspicious:
                item.metadata["suspicious"] = True
                item.metadata["suspicious_reason"] = verdict.suspicious_reason or "flagged by triage"
        else:
            item.category = Category.OTHER
        store.upsert_item(item)

    semaphore = asyncio.Semaphore(MAX_PARALLEL)

    async def guarded(item: HouseholdItem):
        async with semaphore:
            try:
                return await _handle_item(settings, store, memory, item, sim_day, smart_model)
            except Exception as exc:  # keep one bad item from sinking the sweep
                log.exception("item %s failed", item.id)
                item.status = ItemStatus.SNOOZED
                item.outcome = f"Error, will retry: {exc}"[:300]
                store.upsert_item(item)
                return {"item_id": item.id, "status": "error", "error": str(exc)}

    outcomes = await asyncio.gather(*(guarded(i) for i in new_items))
    for outcome in outcomes:
        fresh = store.get_item(outcome["item_id"])
        label = f"{fresh.subject if fresh else outcome['item_id']}"
        if outcome["status"] == "needs_decision":
            digest.escalated.append(label)
        elif fresh and fresh.status == ItemStatus.FLAGGED:
            digest.flagged.append(label)
        else:
            digest.handled.append(f"{label} — {outcome.get('outcome') or 'done'}")
    digest.narrative = (
        f"Day {sim_day}: handled {len(digest.handled)} quietly, flagged {len(digest.flagged)}, "
        f"asked you about {len(digest.escalated)}."
    )
    store.put_digest(digest)
    return digest


def run_sweep(settings: Settings, store: Store, memory: HouseholdMemory, fast_model, smart_model) -> Digest:
    return asyncio.run(run_sweep_async(settings, store, memory, fast_model, smart_model))
