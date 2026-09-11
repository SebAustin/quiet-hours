"""Runtime configuration from environment variables. Local dev works with no variables set."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent


def _env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    return value if value not in (None, "") else default


@dataclass(frozen=True)
class Settings:
    region: str
    fast_model: str
    smart_model: str
    table_name: str | None
    sessions_bucket: str | None
    memory_id: str | None
    slack_webhook_url: str | None
    dashboard_url: str
    api_base_url: str | None
    decision_secret: str
    local_data_dir: Path
    actor_id: str

    @property
    def is_cloud(self) -> bool:
        return bool(self.table_name)


def load_settings() -> Settings:
    return Settings(
        region=_env("AWS_REGION", _env("AWS_DEFAULT_REGION", "us-east-1")) or "us-east-1",
        fast_model=_env("QH_FAST_MODEL", "us.amazon.nova-2-lite-v1:0") or "",
        smart_model=_env("QH_SMART_MODEL", "us.amazon.nova-pro-v1:0") or "",
        table_name=_env("QH_TABLE_NAME"),
        sessions_bucket=_env("QH_SESSIONS_BUCKET"),
        memory_id=_env("MEMORY_HOUSEHOLDMEMORY_ID", _env("QH_MEMORY_ID")),
        slack_webhook_url=_env("QH_SLACK_WEBHOOK_URL"),
        dashboard_url=_env("QH_DASHBOARD_URL", "http://localhost:3000") or "",
        api_base_url=_env("QH_API_BASE_URL"),
        decision_secret=_env("QH_DECISION_SECRET", "local-dev-secret") or "",
        local_data_dir=Path(_env("QH_LOCAL_DATA_DIR", str(APP_DIR.parent.parent.parent / "data" / "local")) or ""),
        actor_id=_env("QH_ACTOR_ID", "rivera-household") or "",
    )
