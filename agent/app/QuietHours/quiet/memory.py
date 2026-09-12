"""AgentCore Memory wrapper. Records decisions as events so the USER_PREFERENCE strategy learns them,
and recalls preferences for the specialists. Degrades to a no-op when no memory id is configured (local dev)."""
from __future__ import annotations

import logging
import uuid

from .config import Settings

log = logging.getLogger(__name__)


class HouseholdMemory:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.memory_id = settings.memory_id
        self._client = None
        if self.memory_id:
            try:
                from bedrock_agentcore.memory import MemoryClient

                self._client = MemoryClient(region_name=settings.region)
            except Exception as exc:  # pragma: no cover - import/permission problems surface in logs
                log.warning("AgentCore Memory unavailable: %s", exc)

    @property
    def enabled(self) -> bool:
        return self._client is not None

    def record(self, text: str, role: str = "USER") -> None:
        """Write one memory event. USER role text is what the preference strategy extracts from."""
        if not self.enabled:
            return
        try:
            self._client.create_event(
                memory_id=self.memory_id,
                actor_id=self.settings.actor_id,
                session_id=f"decisions-{uuid.uuid4()}",
                messages=[(text, role)],
            )
        except Exception as exc:
            log.warning("memory.create_event failed: %s", exc)

    def recall(self, query: str, top_k: int = 5) -> list[str]:
        if not self.enabled:
            return []
        try:
            records = self._client.retrieve_memories(
                memory_id=self.memory_id,
                namespace=f"/users/{self.settings.actor_id}/preferences",
                query=query,
                top_k=top_k,
            )
            return [r.get("content", {}).get("text", "") for r in records if r.get("content")]
        except Exception as exc:
            log.warning("memory.retrieve_memories failed: %s", exc)
            return []
