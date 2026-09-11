from pathlib import Path

from quiet import simulate
from quiet.domain import ActionRecord, ActionMode, Category, DecisionCard, DecisionStatus, ItemStatus, TriageResult
from quiet.store import LocalJsonStore, _from_ddb, _to_ddb


def test_clock_and_ingest(tmp_path: Path):
    s = LocalJsonStore(tmp_path / "state.json")
    day, added = simulate.advance_day(s)
    assert day == 1 and len(added) == 7
    day, added = simulate.advance_day(s)
    assert day == 2 and len(added) == 4
    assert len(s.list_items(ItemStatus.NEW)) == 11


def test_decision_and_action_round_trip(tmp_path: Path):
    s = LocalJsonStore(tmp_path / "state.json")
    card = DecisionCard(item_id="x", category=Category.BILLS, session_id="item-x", interrupt_id="v1:a:b:c", tool="pay_bill",
                        input={"amount": 1.5}, title="Pay?", summary="because", policy_reason="new vendor")
    s.add_decision(card)
    assert s.get_decision(card.id).status == DecisionStatus.PENDING
    card.status = DecisionStatus.TRUSTED
    s.update_decision(card)
    assert [c.id for c in s.list_decisions(DecisionStatus.TRUSTED)] == [card.id]
    s.add_action(ActionRecord(tool="pay_bill", outcome="ok", mode=ActionMode.AUTONOMOUS, policy_reason="r"))
    assert s.list_actions()[0].tool == "pay_bill"


def test_triage_schema_parses_llm_shape():
    result = TriageResult.model_validate({"items": [{"item_id": "a", "category": "bills", "urgency": "high", "proposed_action": "pay"}]})
    assert result.items[0].category == Category.BILLS and result.items[0].suspicious is False


def test_dynamo_decimal_conversion_round_trip():
    payload = {"amount": 62.1, "n": 3, "nested": {"list": [1.5, 2]}}
    assert _from_ddb(_to_ddb(payload)) == payload
