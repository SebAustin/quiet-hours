"""Demo clock: advance the simulated day and ingest fixture items that have arrived."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import APP_DIR
from .domain import HouseholdItem, ItemStatus
from .store import Store

FIXTURES = APP_DIR / "fixtures"


def load_fixture(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text())


def seed_profile(store: Store) -> dict[str, Any]:
    profile = load_fixture("household.json")
    store.put_profile(profile)
    return profile


def ingest_day(store: Store, day: int) -> list[HouseholdItem]:
    """Add every fixture item with received_day <= day that the store doesn't know yet."""
    added: list[HouseholdItem] = []
    known = {i.id for i in store.list_items()}
    for raw in load_fixture("inbox.json"):
        if raw["day"] > day or raw["id"] in known:
            continue
        item = HouseholdItem(
            id=raw["id"], source=raw["source"], received_day=raw["day"], sender=raw["sender"],
            subject=raw["subject"], body=raw["body"], vendor=raw.get("vendor"), amount=raw.get("amount"),
            due_date=raw.get("due_date"), status=ItemStatus.NEW,
        )
        store.upsert_item(item)
        added.append(item)
    return added


def advance_day(store: Store) -> tuple[int, list[HouseholdItem]]:
    day = store.get_clock() + 1
    if not store.get_profile():
        seed_profile(store)
    store.set_clock(day)
    return day, ingest_day(store, day)


def reset(store: Store) -> None:
    store.reset()
    seed_profile(store)
    # Also clear local session files so item sessions start fresh.
    from .config import load_settings

    sessions_dir = Path(load_settings().local_data_dir) / "sessions"
    if sessions_dir.exists():
        import shutil

        shutil.rmtree(sessions_dir, ignore_errors=True)
