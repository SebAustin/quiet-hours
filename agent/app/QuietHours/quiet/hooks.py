"""Strands hooks: an audit trail of every tool call, tagged with why the policy allowed it."""
from __future__ import annotations

import logging
from typing import Any

from strands.hooks import AfterToolCallEvent, BeforeToolCallEvent, HookProvider, HookRegistry

from .domain import ActionMode, ActionRecord
from .policy import READ_TOOLS, AutonomyPolicy, PolicyVerdict
from .store import Store

log = logging.getLogger(__name__)


class AuditHook(HookProvider):
    """Records each executed write tool as an ActionRecord."""

    def __init__(self, store: Store, policy: AutonomyPolicy, item_id: str | None, sim_day: int, mode_override: ActionMode | None = None):
        self.store = store
        self.policy = policy
        self.item_id = item_id
        self.sim_day = sim_day
        self.mode_override = mode_override
        self.recorded: list[ActionRecord] = []

    def register_hooks(self, registry: HookRegistry, **kwargs: Any) -> None:
        registry.add_callback(AfterToolCallEvent, self.after_tool)

    def after_tool(self, event: AfterToolCallEvent) -> None:
        tool = event.tool_use["name"]
        if tool in READ_TOOLS:
            return
        verdict: PolicyVerdict = self.policy.verdicts.get(event.tool_use["toolUseId"], PolicyVerdict(True, "no verdict recorded"))
        result = event.result or {}
        text = " ".join(str(block.get("text", "")) for block in result.get("content", []) if isinstance(block, dict)) or str(result)
        if result.get("status") == "error":
            log.info("tool %s errored: %s", tool, text)
            if self.mode_override == ActionMode.DENIED:
                text = "Declined by the household; nothing was done"
        record = ActionRecord(
            item_id=self.item_id or event.tool_use.get("input", {}).get("item_id"),
            tool=tool,
            input=dict(event.tool_use.get("input") or {}),
            outcome=text[:500],
            mode=self.mode_override or verdict.mode,
            policy_reason=verdict.reason,
            sim_day=self.sim_day,
        )
        self.store.add_action(record)
        self.recorded.append(record)


class LockdownHook(HookProvider):
    """After a denial, cancel any further write tool so the specialist wraps up instead of improvising."""

    def __init__(self, first_tool_use_id: str | None = None):
        self.first_tool_use_id = first_tool_use_id

    def register_hooks(self, registry: HookRegistry, **kwargs: Any) -> None:
        registry.add_callback(BeforeToolCallEvent, self.before_tool)

    def before_tool(self, event: BeforeToolCallEvent) -> None:
        tool = event.tool_use["name"]
        if tool in READ_TOOLS or event.tool_use["toolUseId"] == self.first_tool_use_id:
            return
        event.cancel_tool = "The household declined this item. Do not take any other action; reply with one sentence."
