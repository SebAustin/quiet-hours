"""The autonomy policy: a deterministic classifier plugged into Strands' HumanInTheLoop intervention.

It decides, per tool call, whether the agent may proceed on its own or must pause for a human.
The model never grants itself permissions; this code and the trust ledger do.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from strands.hooks import BeforeToolCallEvent
from strands.vended_interventions.hitl.classifier import ClassifierResult

from .domain import ActionMode, HouseholdItem, TrustRule
from .store import Store

READ_TOOLS = ["get_household_profile", "get_item", "get_bill_history", "get_calendar", "recall_preferences", "list_trust_rules"]
FREE_WRITE_TOOLS = {"reschedule_delivery", "report_suspicious", "snooze", "mark_handled"}
GUARDED_TOOLS = {"pay_bill", "schedule_appointment", "submit_form"}


@dataclass
class PolicyVerdict:
    proceed: bool
    reason: str
    mode: ActionMode = ActionMode.AUTONOMOUS


@dataclass
class AutonomyPolicy:
    store: Store
    verdicts: dict[str, PolicyVerdict] = field(default_factory=dict)
    tool_uses: dict[str, dict[str, Any]] = field(default_factory=dict)

    # -- helpers ----------------------------------------------------------
    def _profile(self) -> dict[str, Any]:
        return self.store.get_profile() or {}

    def _trust_match(self, tool: str, vendor: str | None, amount: float | None) -> TrustRule | None:
        for rule in self.store.list_trust_rules():
            if rule.tool != tool:
                continue
            if rule.vendor and (vendor or "").strip().lower() != rule.vendor.strip().lower():
                continue
            if rule.max_amount is not None and amount is not None and amount > rule.max_amount:
                continue
            return rule
        return None

    def _judge_pay_bill(self, item: HouseholdItem | None, vendor: str | None, amount: float | None) -> PolicyVerdict:
        prefs = self._profile().get("preferences", {})
        cap = float(prefs.get("autopay_cap", 150))
        band = float(prefs.get("anomaly_band_pct", 25)) / 100
        history = (self._profile().get("bill_history") or {}).get(vendor or "", None)
        if amount is None:
            return PolicyVerdict(False, "no amount given for a payment")
        if not history:
            if amount > cap:
                return PolicyVerdict(False, f"{vendor or 'this vendor'} is new and ${amount:,.2f} is above your ${cap:,.0f} autopay cap")
            return PolicyVerdict(False, f"{vendor or 'this vendor'} has never been paid before; first payment needs a human")
        recent = history.get("recent") or []
        avg = sum(recent) / len(recent) if recent else amount
        if avg and amount > avg * (1 + band):
            pct = (amount / avg - 1) * 100
            return PolicyVerdict(False, f"${amount:,.2f} is {pct:.0f}% above the usual ~${avg:,.0f} for {vendor}")
        threshold = float(prefs.get("price_increase_threshold_pct", 10)) / 100
        last = recent[-1] if recent else None
        if last and amount > last * (1 + threshold):
            pct = (amount / last - 1) * 100
            return PolicyVerdict(False, f"${amount:,.2f} is up {pct:.0f}% from the last ${last:,.2f}; you asked to be consulted above {int(threshold*100)}%")
        if amount > cap:
            return PolicyVerdict(False, f"${amount:,.2f} is above your autopay cap of ${cap:,.0f}")
        return PolicyVerdict(True, f"recurring vendor, ${amount:,.2f} is within {int(band*100)}% of the usual ~${avg:,.0f} and under the ${cap:,.0f} cap")

    def _judge_schedule(self, inp: dict[str, Any]) -> PolicyVerdict:
        prefs = (self._profile().get("preferences") or {}).get("appointments", {})
        weekday = str(inp.get("weekday", "")).strip().title()
        time = str(inp.get("time", "")).strip()
        preferred = prefs.get("preferred_days", [])
        earliest, latest = prefs.get("earliest", "00:00"), prefs.get("latest", "23:59")
        if weekday in preferred and earliest <= time <= latest:
            return PolicyVerdict(True, f"{weekday} {time} matches the preferred window ({', '.join(preferred)} {earliest}-{latest})")
        return PolicyVerdict(False, f"{weekday or 'that day'} {time} is outside the preferred window ({', '.join(preferred)} {earliest}-{latest})")

    def _judge_form(self, inp: dict[str, Any]) -> PolicyVerdict:
        fee = float(inp.get("fee") or 0)
        needs_signature = bool(inp.get("requires_signature", False))
        if fee > 0 and needs_signature:
            return PolicyVerdict(False, f"the form carries a ${fee:,.2f} fee and needs a guardian signature")
        if needs_signature:
            return PolicyVerdict(False, "the form needs a guardian signature")
        if fee > 0:
            return PolicyVerdict(False, f"the form carries a ${fee:,.2f} fee")
        return PolicyVerdict(True, "routine form with no fee or signature, filled from the household profile")

    # -- the classifier -----------------------------------------------------
    def judge(self, tool: str, inp: dict[str, Any]) -> PolicyVerdict:
        item = self.store.get_item(str(inp.get("item_id"))) if inp.get("item_id") else None
        vendor = inp.get("vendor") or (item.vendor if item else None)
        amount = inp.get("amount", inp.get("fee"))
        amount = float(amount) if amount not in (None, "") else None

        if item and item.metadata.get("suspicious") and tool in {"pay_bill", "submit_form"}:
            return PolicyVerdict(False, f"this item was flagged as suspicious ({item.metadata.get('suspicious_reason', 'lookalike sender')}); never pay it automatically")
        if tool in FREE_WRITE_TOOLS or tool in READ_TOOLS:
            return PolicyVerdict(True, "low-risk, reversible action")
        rule = self._trust_match(tool, vendor, amount)
        if rule:
            scope = f" for {rule.vendor}" if rule.vendor else ""
            cap = f" up to ${rule.max_amount:,.0f}" if rule.max_amount else ""
            return PolicyVerdict(True, f"you trusted {tool}{scope}{cap} on an earlier decision", ActionMode.TRUSTED)
        if tool == "pay_bill":
            return self._judge_pay_bill(item, vendor, amount)
        if tool == "schedule_appointment":
            return self._judge_schedule(inp)
        if tool == "submit_form":
            return self._judge_form(inp)
        return PolicyVerdict(False, f"{tool} is not on the autonomy list")

    def classify(self, event: BeforeToolCallEvent, **kwargs: Any) -> ClassifierResult:
        tool = event.tool_use["name"]
        inp = dict(event.tool_use.get("input") or {})
        verdict = self.judge(tool, inp)
        self.verdicts[event.tool_use["toolUseId"]] = verdict
        self.tool_uses[event.tool_use["toolUseId"]] = dict(event.tool_use)
        return ClassifierResult(requires_human_in_the_loop=not verdict.proceed, reason=verdict.reason)
