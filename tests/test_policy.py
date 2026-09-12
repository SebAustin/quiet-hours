from pathlib import Path

import pytest

from quiet import simulate
from quiet.domain import ActionMode, TrustRule
from quiet.policy import AutonomyPolicy
from quiet.store import LocalJsonStore


@pytest.fixture
def store(tmp_path: Path):
    s = LocalJsonStore(tmp_path / "state.json")
    simulate.seed_profile(s)
    simulate.advance_day(s)
    return s


def test_recurring_bill_within_band_is_autonomous(store):
    v = AutonomyPolicy(store).judge("pay_bill", {"item_id": "it-water-sep", "vendor": "Austin Water", "amount": 62.10})
    assert v.proceed and v.mode == ActionMode.AUTONOMOUS
    assert "within 25%" in v.reason


def test_anomalous_bill_is_escalated_with_percentage(store):
    v = AutonomyPolicy(store).judge("pay_bill", {"item_id": "it-energy-sep", "vendor": "Austin Energy", "amount": 214.37})
    assert not v.proceed and "81% above" in v.reason


def test_price_increase_over_threshold_is_escalated(store):
    v = AutonomyPolicy(store).judge("pay_bill", {"vendor": "Lonestar Auto Insurance", "amount": 1412.0})
    assert not v.proceed and "up 18%" in v.reason


def test_new_vendor_needs_a_human(store):
    v = AutonomyPolicy(store).judge("pay_bill", {"vendor": "Keys & Chords Piano Studio", "amount": 120.0})
    assert not v.proceed and "never been paid" in v.reason


def test_trust_rule_turns_escalation_into_trusted_autonomy(store):
    store.add_trust_rule(TrustRule(tool="pay_bill", vendor="Keys & Chords Piano Studio", max_amount=138.0))
    v = AutonomyPolicy(store).judge("pay_bill", {"vendor": "keys & chords piano studio", "amount": 120.0})
    assert v.proceed and v.mode == ActionMode.TRUSTED
    over = AutonomyPolicy(store).judge("pay_bill", {"vendor": "Keys & Chords Piano Studio", "amount": 300.0})
    assert not over.proceed


def test_suspicious_item_can_never_be_paid_even_if_trusted(store):
    item = store.get_item("it-phish")
    item.metadata["suspicious"] = True
    store.upsert_item(item)
    store.add_trust_rule(TrustRule(tool="pay_bill", vendor="Austin Energy"))
    v = AutonomyPolicy(store).judge("pay_bill", {"item_id": "it-phish", "vendor": "Austin Energy", "amount": 489.0})
    assert not v.proceed and "suspicious" in v.reason


def test_appointment_window(store):
    p = AutonomyPolicy(store)
    assert p.judge("schedule_appointment", {"weekday": "Tuesday", "time": "15:30"}).proceed
    assert not p.judge("schedule_appointment", {"weekday": "Wednesday", "time": "11:00"}).proceed
    assert not p.judge("schedule_appointment", {"weekday": "Thursday", "time": "09:30"}).proceed


def test_forms_with_fee_or_signature_escalate(store):
    p = AutonomyPolicy(store)
    assert p.judge("submit_form", {"fee": 0, "requires_signature": False}).proceed
    assert not p.judge("submit_form", {"fee": 12, "requires_signature": True}).proceed
    assert not p.judge("submit_form", {"fee": 0, "requires_signature": True}).proceed


def test_low_risk_writes_are_free(store):
    p = AutonomyPolicy(store)
    for tool in ("reschedule_delivery", "report_suspicious", "snooze", "mark_handled"):
        assert p.judge(tool, {"item_id": "it-delivery"}).proceed


def test_amount_mismatch_is_escalated_and_tool_rejects(store):
    from quiet.memory import HouseholdMemory
    from quiet.config import load_settings
    from quiet.tools import HouseholdTools
    v = AutonomyPolicy(store).judge("pay_bill", {"item_id": "it-energy-sep", "vendor": "Austin Energy", "amount": 150.0})
    assert not v.proceed and "bill says $214.37" in v.reason
    tools = HouseholdTools(store, HouseholdMemory(load_settings()))
    assert tools.pay_bill(item_id="it-energy-sep", vendor="Austin Energy", amount=150.0, account_id="checking-4821").startswith("REJECTED")
