"""Household tools the specialists call. Reads are free; writes are gated by the autonomy policy."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from strands import tool

from .domain import HouseholdItem, ItemStatus
from .memory import HouseholdMemory
from .store import Store


@dataclass
class HouseholdTools:
    store: Store
    memory: HouseholdMemory
    sim_day: int = 0

    # ------------------------------------------------------------------ reads
    @tool
    def get_household_profile(self) -> dict:
        """Household members, addresses, payment accounts, preferences and safety rules."""
        profile = dict(self.store.get_profile())
        profile.pop("bill_history", None)
        profile.pop("calendar", None)
        return profile

    @tool
    def get_item(self, item_id: str) -> dict:
        """Full details of an inbound item (email, bill, notice) by id."""
        item = self.store.get_item(item_id)
        return item.model_dump(mode="json") if item else {"error": f"unknown item {item_id}"}

    @tool
    def get_bill_history(self, vendor: str) -> dict:
        """Recent amounts paid to a vendor and which account pays it. Empty if the vendor is new."""
        history = (self.store.get_profile().get("bill_history") or {}).get(vendor)
        if not history:
            return {"vendor": vendor, "known": False, "recent": []}
        recent = history["recent"]
        return {"vendor": vendor, "known": True, "recent": recent, "average": round(sum(recent) / len(recent), 2), "account": history.get("account"), "cadence": history.get("cadence")}

    @tool
    def get_calendar(self) -> list[dict]:
        """The household calendar for the coming days (simulated day numbers with weekdays)."""
        return list(self.store.get_profile().get("calendar") or [])

    @tool
    def recall_preferences(self, topic: str) -> dict:
        """What the household has told us before about a topic (learned preferences and standing permissions)."""
        rules = [f"{r.tool}" + (f" for {r.vendor}" if r.vendor else "") + (f" up to ${r.max_amount:,.0f}" if r.max_amount else "") + (f" ({r.note})" if r.note else "") for r in self.store.list_trust_rules()]
        return {"topic": topic, "learned_preferences": self.memory.recall(topic), "standing_permissions": rules}

    @tool
    def list_trust_rules(self) -> list[dict]:
        """Standing permissions the household granted on earlier decisions."""
        return [r.model_dump(mode="json") for r in self.store.list_trust_rules()]

    # ----------------------------------------------------------------- writes
    def _finish(self, item_id: str, status: ItemStatus, outcome: str) -> None:
        item = self.store.get_item(item_id)
        if item:
            item.status = status
            item.outcome = outcome
            self.store.upsert_item(item)

    @tool
    def pay_bill(self, item_id: str, vendor: str, amount: float, account_id: str) -> str:
        """Pay a bill from a household account through the vendor's known portal. Money moves; irreversible."""
        confirmation = f"QH-{abs(hash((item_id, vendor, amount))) % 10_000_000:07d}"
        outcome = f"Paid {vendor} ${amount:,.2f} from {account_id} (confirmation {confirmation})"
        self._finish(item_id, ItemStatus.HANDLED, outcome)
        return outcome

    @tool
    def schedule_appointment(self, item_id: str, provider: str, day: int, weekday: str, time: str, for_member: str) -> str:
        """Book an appointment slot with a provider. Weekday and time (HH:MM) must be one of the offered slots."""
        for event in self.store.get_profile().get("calendar") or []:
            if event["day"] == day and event["start"] <= time < event["end"] and "free" not in event["title"].lower():
                return f"CONFLICT: {weekday} day {day} {time} overlaps '{event['title']}'. Pick another offered slot."
        outcome = f"Booked {for_member} with {provider}: {weekday} (day {day}) at {time}"
        self._finish(item_id, ItemStatus.HANDLED, outcome)
        return outcome

    @tool
    def submit_form(self, item_id: str, form_name: str, fields: dict, fee: float = 0.0, requires_signature: bool = False) -> str:
        """Fill and submit a form with values from the household profile. Set fee and requires_signature honestly."""
        summary = ", ".join(f"{k}={v}" for k, v in fields.items())
        outcome = f"Submitted '{form_name}' ({summary})" + (f", fee ${fee:,.2f}" if fee else "") + (", signed by guardian" if requires_signature else "")
        self._finish(item_id, ItemStatus.HANDLED, outcome)
        return outcome

    @tool
    def reschedule_delivery(self, item_id: str, carrier: str, new_day: int, new_weekday: str, window: str) -> str:
        """Move a delivery to a day when someone is home. Reversible."""
        outcome = f"Rescheduled {carrier} delivery to {new_weekday} (day {new_day}) {window}"
        self._finish(item_id, ItemStatus.HANDLED, outcome)
        return outcome

    @tool
    def report_suspicious(self, item_id: str, reason: str) -> str:
        """Flag an item as phishing or a scam, block any payment, and note why."""
        item = self.store.get_item(item_id)
        if item:
            item.metadata["suspicious"] = True
            item.metadata["suspicious_reason"] = reason
            item.status = ItemStatus.FLAGGED
            item.outcome = f"Flagged as suspicious and blocked: {reason}"
            self.store.upsert_item(item)
        return f"Flagged {item_id} as suspicious. No payment will be made. Reason: {reason}"

    @tool
    def snooze(self, item_id: str, until_day: int, reason: str) -> str:
        """Defer an item to a later day."""
        self._finish(item_id, ItemStatus.SNOOZED, f"Snoozed until day {until_day}: {reason}")
        return f"Snoozed {item_id} until day {until_day}"

    @tool
    def mark_handled(self, item_id: str, note: str) -> str:
        """Close an item that needs no action (informational notices, confirmations)."""
        self._finish(item_id, ItemStatus.HANDLED, f"No action needed: {note}")
        return f"Closed {item_id}: {note}"

    # ------------------------------------------------------------------ groups
    @property
    def read_tools(self) -> list:
        return [self.get_household_profile, self.get_item, self.get_bill_history, self.get_calendar, self.recall_preferences, self.list_trust_rules]

    @property
    def write_tools(self) -> list:
        return [self.pay_bill, self.schedule_appointment, self.submit_form, self.reschedule_delivery, self.report_suspicious, self.snooze, self.mark_handled]

    @property
    def all_tools(self) -> list:
        return self.read_tools + self.write_tools


def item_brief(item: HouseholdItem) -> str:
    return json.dumps(item.model_dump(mode="json", exclude={"metadata"}), indent=2)
