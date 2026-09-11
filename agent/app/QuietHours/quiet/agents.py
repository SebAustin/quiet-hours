"""Agent builders. One triage agent, one specialist per category, one chat agent."""
from __future__ import annotations

from strands import Agent, tool
from strands.vended_interventions.hitl import HumanInTheLoop

from .config import Settings
from .domain import Category, DecisionStatus
from .hooks import AuditHook
from .memory import HouseholdMemory
from .policy import READ_TOOLS, AutonomyPolicy
from .sessions import build_session_manager, item_session_id
from .store import Store
from .tools import HouseholdTools

TRIAGE_PROMPT = """You triage a household's inbound mail for a background assistant.
For every item decide the category (bills | scheduling | paperwork | other), urgency, whether it looks suspicious
(lookalike domains, pressure to pay via a link, unknown senders demanding money), and propose one concrete action.
'other' is for purely informational notices that need no action. Be precise and brief."""

RATIONALE_RULE = """
Before calling any write tool, write ONE plain sentence for the household explaining what you are about to do and why
(for example: "Paying the $62.10 water bill from checking, it is in line with recent months."). No tags, no lists."""

SPECIALIST_PROMPTS = {
    Category.BILLS: """You are the bills specialist for a household assistant that works quietly in the background.
Handle ONE item. Look up the bill history and the household profile first, then act with the right tool:
- pay_bill for legitimate bills through the vendor's known portal, using the account the household uses for that vendor
  (default 'checking-4821'; subscriptions use 'credit-9930'). Use the item's exact amount.
- report_suspicious if the sender, domain or link looks like phishing (never pay those).
- For price-change notices (subscription increases, renewals with a premium jump), the household must decide, so still
  call pay_bill with the new amount; the approval layer will pause and ask them. Do not cancel services yourself.
- mark_handled only for notices with nothing to pay.
Call exactly one write tool. If a tool result says it was denied or cancelled, do not retry; finish with a one-line summary.
Finish with one plain sentence describing what you did or want to do and why.""",
    Category.SCHEDULING: """You are the scheduling specialist for a household assistant that works quietly in the background.
Handle ONE item. Read the household profile (appointment preferences) and the calendar, then:
- schedule_appointment: among the offered slots, pick the FIRST one whose weekday is in preferred_days AND whose time is
  between earliest and latest AND has no calendar entry on that day covering that time (calendar entries with 'free' in
  the title are fine). Pass day, weekday, time (HH:MM) exactly as offered. If the tool reports a conflict, try the next
  fitting slot. Only if no offered slot fits, propose the closest one anyway (the household will be asked).
- reschedule_delivery when a delivery needs a signature on a day nobody is home: follow preferences.deliveries exactly
  (for example 'reschedule to Saturday morning' means the next Saturday in the calendar, window 08:00-12:00).
- mark_handled ONLY for confirmations or notices that need no action. Never call it after another write tool.
Call exactly one write tool (a second only if the first reported a conflict). Finish with one plain sentence saying what you did and why.""",
    Category.PAPERWORK: """You are the paperwork specialist for a household assistant that works quietly in the background.
Handle ONE item. Read the household profile, then submit_form with every requested field filled from the profile
(student name, grade, teacher, allergies, emergency contact, guardian name/phone, address). Set fee to the form's fee
and requires_signature=true if a parent/guardian signature is requested. Never invent facts that are not in the profile.
Call exactly one write tool. If it is denied or cancelled, do not retry. Finish with one plain sentence on what you did and why.""",
    Category.OTHER: """You are a household assistant that works quietly in the background. Handle ONE informational item.
If nothing needs doing, call mark_handled with a short note. If it actually needs an action, use the most fitting tool.
Finish with one plain sentence.""",
}


SPECIALIST_PROMPTS = {k: v + RATIONALE_RULE for k, v in SPECIALIST_PROMPTS.items()}


def build_triage_agent(model, tools: HouseholdTools) -> Agent:
    return Agent(model=model, system_prompt=TRIAGE_PROMPT, tools=[tools.get_household_profile], callback_handler=None)


def build_specialist(
    settings: Settings,
    model,
    category: Category,
    item_id: str,
    store: Store,
    policy: AutonomyPolicy,
    tools: HouseholdTools,
    audit: AuditHook,
    extra_hooks: list | None = None,
) -> Agent:
    return Agent(
        name=f"{category.value}-specialist",
        model=model,
        system_prompt=SPECIALIST_PROMPTS[category],
        tools=tools.all_tools,
        interventions=[HumanInTheLoop(allowed_tools=READ_TOOLS, classifier=policy.classify, enable_trust=True)],
        hooks=[audit, *(extra_hooks or [])],
        session_manager=build_session_manager(settings, item_session_id(item_id)),
        callback_handler=None,
    )


CHAT_PROMPT = """You are Quiet Hours, a household admin autopilot. You handle bills, appointments, forms and deliveries in
the background and only interrupt people for real decisions. Answer questions about what you did, what is pending and
why, using the tools. Be warm, specific and short. Refer to money and dates exactly as recorded."""


def build_chat_agent(model, store: Store, tools: HouseholdTools) -> Agent:
    @tool
    def list_recent_actions(limit: int = 20) -> list[dict]:
        """Actions the assistant took recently (autonomous, approved, trusted or denied), newest last."""
        return [a.model_dump(mode="json") for a in store.list_actions()[-limit:]]

    @tool
    def list_decisions(status: str = "pending") -> list[dict]:
        """Decision cards by status: pending | approved | denied | trusted."""
        return [d.model_dump(mode="json") for d in store.list_decisions(DecisionStatus(status))]

    @tool
    def list_items(status: str = "") -> list[dict]:
        """Inbound items, optionally filtered by status (new, handled, needs_decision, snoozed, flagged)."""
        from .domain import ItemStatus

        items = store.list_items(ItemStatus(status) if status else None)
        return [i.model_dump(mode="json", exclude={"body"}) for i in items]

    return Agent(
        model=model,
        system_prompt=CHAT_PROMPT,
        tools=[list_recent_actions, list_decisions, list_items, tools.get_household_profile, tools.list_trust_rules],
        callback_handler=None,
    )
