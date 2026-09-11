"""Domain model for Quiet Hours. Pure data, no I/O."""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:10]}"


class Category(str, Enum):
    BILLS = "bills"
    SCHEDULING = "scheduling"
    PAPERWORK = "paperwork"
    OTHER = "other"


class ItemStatus(str, Enum):
    NEW = "new"
    IN_PROGRESS = "in_progress"
    HANDLED = "handled"
    NEEDS_DECISION = "needs_decision"
    SNOOZED = "snoozed"
    FLAGGED = "flagged"


class HouseholdItem(BaseModel):
    """One inbound thing the household has to deal with (email, portal notice, calendar recall)."""

    id: str
    source: str = Field(description="email | portal | calendar | sms")
    received_day: int = Field(description="Simulated day the item arrives")
    received_at: str = Field(default_factory=now_iso)
    sender: str
    subject: str
    body: str
    vendor: str | None = None
    amount: float | None = None
    due_date: str | None = None
    category: Category | None = None
    status: ItemStatus = ItemStatus.NEW
    triage_notes: str | None = None
    outcome: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class TriagedItem(BaseModel):
    """Triage verdict for one item (structured output from the triage agent)."""

    item_id: str = Field(description="The id of the item being triaged")
    category: Category = Field(description="bills | scheduling | paperwork | other")
    urgency: str = Field(description="low | medium | high")
    suspicious: bool = Field(default=False, description="True if this looks like phishing, a scam, or a lookalike sender")
    suspicious_reason: str | None = Field(default=None, description="Why it looks suspicious, if it does")
    proposed_action: str = Field(description="One sentence: what a careful household assistant would do")
    notes: str | None = Field(default=None, description="Anything the specialist should know")


class TriageResult(BaseModel):
    """Triage output for a batch of items."""

    items: list[TriagedItem]


class ActionMode(str, Enum):
    AUTONOMOUS = "autonomous"
    APPROVED = "approved"
    DENIED = "denied"
    TRUSTED = "trusted"


class ActionRecord(BaseModel):
    """Audit-log entry: one tool call the agent made (or was denied)."""

    id: str = Field(default_factory=lambda: new_id("act"))
    item_id: str | None = None
    tool: str
    input: dict[str, Any] = Field(default_factory=dict)
    outcome: str
    mode: ActionMode
    policy_reason: str
    at: str = Field(default_factory=now_iso)
    sim_day: int | None = None


class DecisionStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    TRUSTED = "trusted"
    EXPIRED = "expired"


class DecisionCard(BaseModel):
    """A paused tool call waiting for a human. Maps 1:1 to a Strands interrupt."""

    id: str = Field(default_factory=lambda: new_id("dec"))
    item_id: str
    category: Category
    session_id: str
    interrupt_id: str
    tool: str
    input: dict[str, Any] = Field(default_factory=dict)
    title: str
    summary: str = Field(description="The specialist's rationale, in plain words")
    policy_reason: str = Field(description="Why the policy escalated instead of acting")
    status: DecisionStatus = DecisionStatus.PENDING
    created_at: str = Field(default_factory=now_iso)
    resolved_at: str | None = None
    response: str | None = None
    sim_day: int | None = None


class TrustRule(BaseModel):
    """A standing permission learned from a decision."""

    id: str = Field(default_factory=lambda: new_id("trust"))
    tool: str
    vendor: str | None = None
    max_amount: float | None = None
    created_at: str = Field(default_factory=now_iso)
    source_decision: str | None = None
    note: str | None = None


class Digest(BaseModel):
    """What the last sweep did, for the dashboard."""

    at: str = Field(default_factory=now_iso)
    sim_day: int
    handled: list[str] = Field(default_factory=list)
    escalated: list[str] = Field(default_factory=list)
    flagged: list[str] = Field(default_factory=list)
    narrative: str = ""
