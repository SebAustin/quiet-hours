"""Session persistence: this is what lets a paused (interrupted) agent resume in a later invocation."""
from __future__ import annotations

from strands.session import FileSessionManager, S3SessionManager

from .config import Settings


def item_session_id(item_id: str) -> str:
    return f"item-{item_id}"


def build_session_manager(settings: Settings, session_id: str):
    if settings.sessions_bucket:
        return S3SessionManager(
            session_id=session_id,
            bucket=settings.sessions_bucket,
            prefix="sessions",
            region_name=settings.region,
        )
    return FileSessionManager(session_id=session_id, storage_dir=str(settings.local_data_dir / "sessions"))
