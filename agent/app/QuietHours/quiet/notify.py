"""Push a decision card to Slack via an incoming webhook, with link buttons that resolve the decision.
No webhook configured -> log only (dashboard still shows the card)."""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import urllib.request

from .config import Settings
from .domain import DecisionCard

log = logging.getLogger(__name__)


def decision_token(secret: str, decision_id: str, choice: str) -> str:
    return hmac.new(secret.encode(), f"{decision_id}:{choice}".encode(), hashlib.sha256).hexdigest()[:24]


def decision_link(settings: Settings, decision_id: str, choice: str) -> str:
    base = settings.api_base_url or settings.dashboard_url
    token = decision_token(settings.decision_secret, decision_id, choice)
    return f"{base.rstrip('/')}/d/{decision_id}?choice={choice}&t={token}"


def _fmt_input(card: DecisionCard) -> str:
    parts = []
    for key, value in card.input.items():
        if key == "item_id":
            continue
        parts.append(f"*{key}*: {value}")
    return "  ·  ".join(parts) if parts else "(no arguments)"


def slack_blocks(settings: Settings, card: DecisionCard) -> list[dict]:
    return [
        {"type": "header", "text": {"type": "plain_text", "text": f"Needs you: {card.title}"[:150]}},
        {"type": "section", "text": {"type": "mrkdwn", "text": card.summary[:2900]}},
        {"type": "context", "elements": [{"type": "mrkdwn", "text": f"Proposed: `{card.tool}` — {_fmt_input(card)}"[:2900]}]},
        {"type": "context", "elements": [{"type": "mrkdwn", "text": f"Why I'm asking: {card.policy_reason}"[:2900]}]},
        {
            "type": "actions",
            "elements": [
                {"type": "button", "style": "primary", "text": {"type": "plain_text", "text": "Approve"}, "url": decision_link(settings, card.id, "approve")},
                {"type": "button", "text": {"type": "plain_text", "text": "Approve and trust from now on"}, "url": decision_link(settings, card.id, "trust")},
                {"type": "button", "style": "danger", "text": {"type": "plain_text", "text": "Deny"}, "url": decision_link(settings, card.id, "deny")},
            ],
        },
    ]


def notify_decision(settings: Settings, card: DecisionCard) -> bool:
    payload = {"text": f"Quiet Hours needs a decision: {card.title}", "blocks": slack_blocks(settings, card)}
    if not settings.slack_webhook_url:
        log.info("[notify] no Slack webhook; decision %s shown on dashboard only", card.id)
        return False
    req = urllib.request.Request(
        settings.slack_webhook_url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            ok = resp.status == 200
            log.info("[notify] slack status=%s for %s", resp.status, card.id)
            return ok
    except Exception as exc:
        log.warning("[notify] slack failed: %s", exc)
        return False


def notify_text(settings: Settings, text: str) -> None:
    if not settings.slack_webhook_url:
        return
    req = urllib.request.Request(
        settings.slack_webhook_url, data=json.dumps({"text": text}).encode(),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        urllib.request.urlopen(req, timeout=10).read()
    except Exception as exc:
        log.warning("[notify] slack text failed: %s", exc)
