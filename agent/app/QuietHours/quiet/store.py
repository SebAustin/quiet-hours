"""Persistence for items, actions, decisions, trust rules and the simulated clock.

Two implementations behind one small interface:
- LocalJsonStore: a single JSON file, used with `agentcore dev` and tests.
- DynamoStore: one DynamoDB table (PK = record type, SK = id), used when deployed.
"""
from __future__ import annotations

import json
import threading
from decimal import Decimal
from pathlib import Path
from typing import Any, Protocol

from .domain import (
    ActionRecord,
    DecisionCard,
    DecisionStatus,
    Digest,
    HouseholdItem,
    ItemStatus,
    TrustRule,
)


class Store(Protocol):
    def get_clock(self) -> int: ...
    def set_clock(self, day: int) -> None: ...
    def get_profile(self) -> dict[str, Any]: ...
    def put_profile(self, profile: dict[str, Any]) -> None: ...
    def list_items(self, status: ItemStatus | None = None) -> list[HouseholdItem]: ...
    def get_item(self, item_id: str) -> HouseholdItem | None: ...
    def upsert_item(self, item: HouseholdItem) -> None: ...
    def add_action(self, action: ActionRecord) -> None: ...
    def list_actions(self) -> list[ActionRecord]: ...
    def add_decision(self, decision: DecisionCard) -> None: ...
    def get_decision(self, decision_id: str) -> DecisionCard | None: ...
    def update_decision(self, decision: DecisionCard) -> None: ...
    def list_decisions(self, status: DecisionStatus | None = None) -> list[DecisionCard]: ...
    def list_trust_rules(self) -> list[TrustRule]: ...
    def add_trust_rule(self, rule: TrustRule) -> None: ...
    def put_digest(self, digest: Digest) -> None: ...
    def get_digest(self) -> Digest | None: ...
    def reset(self) -> None: ...


# ---------------------------------------------------------------------------
# Local JSON store
# ---------------------------------------------------------------------------

_EMPTY: dict[str, Any] = {
    "clock": 0,
    "profile": {},
    "items": {},
    "actions": [],
    "decisions": {},
    "trust_rules": [],
    "digest": None,
}


class LocalJsonStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        if not self.path.exists():
            self._write(dict(_EMPTY))

    # -- low level --------------------------------------------------------
    def _read(self) -> dict[str, Any]:
        with self._lock:
            return json.loads(self.path.read_text() or "{}") or dict(_EMPTY)

    def _write(self, data: dict[str, Any]) -> None:
        with self._lock:
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, indent=2, default=str))
            tmp.replace(self.path)

    def _update(self, fn) -> None:
        with self._lock:
            data = self._read()
            fn(data)
            self._write(data)

    # -- api --------------------------------------------------------------
    def reset(self) -> None:
        self._write(json.loads(json.dumps(_EMPTY)))

    def get_clock(self) -> int:
        return int(self._read().get("clock", 0))

    def set_clock(self, day: int) -> None:
        self._update(lambda d: d.__setitem__("clock", int(day)))

    def get_profile(self) -> dict[str, Any]:
        return self._read().get("profile", {})

    def put_profile(self, profile: dict[str, Any]) -> None:
        self._update(lambda d: d.__setitem__("profile", profile))

    def list_items(self, status: ItemStatus | None = None) -> list[HouseholdItem]:
        items = [HouseholdItem.model_validate(v) for v in self._read()["items"].values()]
        if status is not None:
            items = [i for i in items if i.status == status]
        return sorted(items, key=lambda i: (i.received_day, i.id))

    def get_item(self, item_id: str) -> HouseholdItem | None:
        raw = self._read()["items"].get(item_id)
        return HouseholdItem.model_validate(raw) if raw else None

    def upsert_item(self, item: HouseholdItem) -> None:
        self._update(lambda d: d["items"].__setitem__(item.id, item.model_dump(mode="json")))

    def add_action(self, action: ActionRecord) -> None:
        self._update(lambda d: d["actions"].append(action.model_dump(mode="json")))

    def list_actions(self) -> list[ActionRecord]:
        return [ActionRecord.model_validate(a) for a in self._read()["actions"]]

    def add_decision(self, decision: DecisionCard) -> None:
        self._update(lambda d: d["decisions"].__setitem__(decision.id, decision.model_dump(mode="json")))

    update_decision = add_decision

    def get_decision(self, decision_id: str) -> DecisionCard | None:
        raw = self._read()["decisions"].get(decision_id)
        return DecisionCard.model_validate(raw) if raw else None

    def list_decisions(self, status: DecisionStatus | None = None) -> list[DecisionCard]:
        cards = [DecisionCard.model_validate(v) for v in self._read()["decisions"].values()]
        if status is not None:
            cards = [c for c in cards if c.status == status]
        return sorted(cards, key=lambda c: c.created_at)

    def list_trust_rules(self) -> list[TrustRule]:
        return [TrustRule.model_validate(r) for r in self._read()["trust_rules"]]

    def add_trust_rule(self, rule: TrustRule) -> None:
        self._update(lambda d: d["trust_rules"].append(rule.model_dump(mode="json")))

    def put_digest(self, digest: Digest) -> None:
        self._update(lambda d: d.__setitem__("digest", digest.model_dump(mode="json")))

    def get_digest(self) -> Digest | None:
        raw = self._read().get("digest")
        return Digest.model_validate(raw) if raw else None


# ---------------------------------------------------------------------------
# DynamoDB store (single table: PK = record type, SK = id)
# ---------------------------------------------------------------------------

def _to_ddb(value: Any) -> Any:
    """DynamoDB rejects floats; convert recursively to Decimal."""
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {k: _to_ddb(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_to_ddb(v) for v in value]
    return value


def _from_ddb(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value) if value % 1 else int(value)
    if isinstance(value, dict):
        return {k: _from_ddb(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_from_ddb(v) for v in value]
    return value


def _strip(raw: dict[str, Any]) -> dict[str, Any]:
    raw.pop("_sk", None)
    return raw


class DynamoStore:
    PK_ITEM, PK_ACTION, PK_DECISION, PK_TRUST, PK_META = "ITEM", "ACTION", "DECISION", "TRUST", "META"

    def __init__(self, table_name: str, region: str):
        import boto3

        self.table = boto3.resource("dynamodb", region_name=region).Table(table_name)

    def _put(self, pk: str, sk: str, body: dict[str, Any]) -> None:
        self.table.put_item(Item={"PK": pk, "SK": sk, **_to_ddb(body)})

    def _get(self, pk: str, sk: str) -> dict[str, Any] | None:
        raw = self.table.get_item(Key={"PK": pk, "SK": sk}).get("Item")
        if not raw:
            return None
        raw = _from_ddb(raw)
        raw.pop("PK", None)
        raw.pop("SK", None)
        return raw

    def _query(self, pk: str) -> list[dict[str, Any]]:
        from boto3.dynamodb.conditions import Key

        out: list[dict[str, Any]] = []
        kwargs: dict[str, Any] = {"KeyConditionExpression": Key("PK").eq(pk)}
        while True:
            resp = self.table.query(**kwargs)
            for raw in resp.get("Items", []):
                raw = _from_ddb(raw)
                raw.pop("PK", None)
                raw["_sk"] = raw.pop("SK", None)
                out.append(raw)
            if "LastEvaluatedKey" not in resp:
                return out
            kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]

    def reset(self) -> None:
        for pk in (self.PK_ITEM, self.PK_ACTION, self.PK_DECISION, self.PK_TRUST):
            for raw in self._query(pk):
                if raw.get("_sk"):
                    self.table.delete_item(Key={"PK": pk, "SK": raw["_sk"]})
        for sk in ("clock", "profile", "digest"):
            self.table.delete_item(Key={"PK": self.PK_META, "SK": sk})

    def get_clock(self) -> int:
        raw = self._get(self.PK_META, "clock")
        return int(raw["value"]) if raw else 0

    def set_clock(self, day: int) -> None:
        self._put(self.PK_META, "clock", {"value": int(day)})

    def get_profile(self) -> dict[str, Any]:
        raw = self._get(self.PK_META, "profile")
        return raw["value"] if raw else {}

    def put_profile(self, profile: dict[str, Any]) -> None:
        self._put(self.PK_META, "profile", {"value": profile})

    def list_items(self, status: ItemStatus | None = None) -> list[HouseholdItem]:
        items = [HouseholdItem.model_validate(_strip(r)) for r in self._query(self.PK_ITEM)]
        if status is not None:
            items = [i for i in items if i.status == status]
        return sorted(items, key=lambda i: (i.received_day, i.id))

    def get_item(self, item_id: str) -> HouseholdItem | None:
        raw = self._get(self.PK_ITEM, item_id)
        return HouseholdItem.model_validate(raw) if raw else None

    def upsert_item(self, item: HouseholdItem) -> None:
        self._put(self.PK_ITEM, item.id, item.model_dump(mode="json"))

    def add_action(self, action: ActionRecord) -> None:
        self._put(self.PK_ACTION, f"{action.at}#{action.id}", action.model_dump(mode="json"))

    def list_actions(self) -> list[ActionRecord]:
        return sorted((ActionRecord.model_validate(_strip(r)) for r in self._query(self.PK_ACTION)), key=lambda a: a.at)

    def add_decision(self, decision: DecisionCard) -> None:
        self._put(self.PK_DECISION, decision.id, decision.model_dump(mode="json"))

    update_decision = add_decision

    def get_decision(self, decision_id: str) -> DecisionCard | None:
        raw = self._get(self.PK_DECISION, decision_id)
        return DecisionCard.model_validate(raw) if raw else None

    def list_decisions(self, status: DecisionStatus | None = None) -> list[DecisionCard]:
        cards = [DecisionCard.model_validate(_strip(r)) for r in self._query(self.PK_DECISION)]
        if status is not None:
            cards = [c for c in cards if c.status == status]
        return sorted(cards, key=lambda c: c.created_at)

    def list_trust_rules(self) -> list[TrustRule]:
        return [TrustRule.model_validate(_strip(r)) for r in self._query(self.PK_TRUST)]

    def add_trust_rule(self, rule: TrustRule) -> None:
        self._put(self.PK_TRUST, rule.id, rule.model_dump(mode="json"))

    def put_digest(self, digest: Digest) -> None:
        self._put(self.PK_META, "digest", {"value": digest.model_dump(mode="json")})

    def get_digest(self) -> Digest | None:
        raw = self._get(self.PK_META, "digest")
        return Digest.model_validate(raw["value"]) if raw else None


def build_store(settings) -> Store:
    if settings.table_name:
        return DynamoStore(settings.table_name, settings.region)
    return LocalJsonStore(settings.local_data_dir / "state.json")
