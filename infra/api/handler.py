"""Quiet Hours API (Lambda Function URL).

Routes
  GET  /state                         everything the dashboard needs (items, actions, decisions, trust, digest, stats)
  POST /decisions/{id}  {"choice"}    resolve a decision card (resumes the paused agent)
  GET  /d/{id}?choice=&t=             one-click link from Slack (HMAC-signed), then redirect to the dashboard
  POST /sweep                         run a background sweep now
  POST /simulate        {"action"}    advance | reset | status (demo clock)
  POST /chat            {"prompt"}    ask the agent about its work
Scheduler events arrive as {"mode": "sweep"} without an HTTP context.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import uuid
from decimal import Decimal
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key

TABLE_NAME = os.environ["QH_TABLE_NAME"]
RUNTIME_ARN = os.environ.get("QH_AGENT_RUNTIME_ARN", "")
DASHBOARD_URL = os.environ.get("QH_DASHBOARD_URL", "http://localhost:3000")
API_KEY = os.environ.get("QH_API_KEY", "")
DECISION_SECRET = os.environ.get("QH_DECISION_SECRET", "local-dev-secret")
REGION = os.environ.get("AWS_REGION", "us-east-1")

table = boto3.resource("dynamodb", region_name=REGION).Table(TABLE_NAME)
agentcore = boto3.client("bedrock-agentcore", region_name=REGION)


# ----------------------------------------------------------------------------- helpers
def _plain(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value) if value % 1 else int(value)
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items() if k not in ("PK", "SK")}
    if isinstance(value, list):
        return [_plain(v) for v in value]
    return value


def _query(pk: str) -> list[dict]:
    out, kwargs = [], {"KeyConditionExpression": Key("PK").eq(pk)}
    while True:
        resp = table.query(**kwargs)
        out.extend(_plain(i) for i in resp.get("Items", []))
        if "LastEvaluatedKey" not in resp:
            return out
        kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]


def _meta(sk: str, default: Any = None) -> Any:
    raw = table.get_item(Key={"PK": "META", "SK": sk}).get("Item")
    return _plain(raw)["value"] if raw else default


def _response(status: int, body: Any, headers: dict | None = None) -> dict:
    return {
        "statusCode": status,
        "headers": {"content-type": "application/json", **(headers or {})},
        "body": json.dumps(body, default=str),
    }


def _redirect(url: str) -> dict:
    return {"statusCode": 302, "headers": {"location": url}, "body": ""}


def _token(decision_id: str, choice: str) -> str:
    return hmac.new(DECISION_SECRET.encode(), f"{decision_id}:{choice}".encode(), hashlib.sha256).hexdigest()[:24]


def invoke_agent(payload: dict) -> dict:
    if not RUNTIME_ARN:
        return {"ok": False, "error": "agent runtime not configured (QH_AGENT_RUNTIME_ARN)"}
    resp = agentcore.invoke_agent_runtime(
        agentRuntimeArn=RUNTIME_ARN,
        qualifier="DEFAULT",
        runtimeSessionId=f"qh-{uuid.uuid4()}-{uuid.uuid4().hex[:8]}",
        payload=json.dumps(payload).encode(),
        contentType="application/json",
        accept="application/json",
    )
    body = resp["response"].read() if hasattr(resp["response"], "read") else resp["response"]
    text = body.decode() if isinstance(body, bytes) else str(body)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"ok": False, "error": "non-JSON agent response", "raw": text[:2000]}


# ----------------------------------------------------------------------------- state
def build_state() -> dict:
    items = _query("ITEM")
    actions = sorted(_query("ACTION"), key=lambda a: a["at"])
    decisions = sorted(_query("DECISION"), key=lambda d: d["created_at"])
    trust = _query("TRUST")
    clock = int(_meta("clock", 0))
    per_day: dict[int, dict[str, int]] = {}
    for a in actions:
        d = per_day.setdefault(int(a.get("sim_day") or 0), {"handled": 0, "asked": 0})
        if a.get("mode") in ("autonomous", "trusted"):
            d["handled"] += 1
    for c in decisions:
        per_day.setdefault(int(c.get("sim_day") or 0), {"handled": 0, "asked": 0})["asked"] += 1
    return {
        "clock": clock,
        "profile": _meta("profile", {}),
        "digest": _meta("digest"),
        "items": items,
        "actions": actions,
        "decisions": decisions,
        "trust_rules": trust,
        "stats": {
            "pending": sum(1 for c in decisions if c.get("status") == "pending"),
            "handled_quietly": sum(1 for a in actions if a.get("mode") in ("autonomous", "trusted")),
            "flagged": sum(1 for i in items if i.get("status") == "flagged"),
            "per_day": [{"day": k, **v} for k, v in sorted(per_day.items())],
        },
    }


# ----------------------------------------------------------------------------- handler
def lambda_handler(event: dict, context: Any) -> dict:
    if "requestContext" not in event:  # EventBridge Scheduler or direct invoke
        mode = event.get("mode", "sweep")
        return invoke_agent({"mode": mode, **{k: v for k, v in event.items() if k not in ("mode", "source")}})

    http = event["requestContext"]["http"]
    method, path = http["method"], event.get("rawPath", "/")
    query = event.get("queryStringParameters") or {}
    headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
    body: dict = {}
    if event.get("body"):
        try:
            body = json.loads(event["body"])
        except json.JSONDecodeError:
            return _response(400, {"ok": False, "error": "invalid JSON body"})

    if method == "OPTIONS":
        return _response(204, "")

    # One-click Slack links: signed, no API key.
    if method == "GET" and path.startswith("/d/"):
        decision_id = path[3:].split("/")[0]
        choice = query.get("choice", "")
        if not hmac.compare_digest(query.get("t", ""), _token(decision_id, choice)):
            return _response(403, {"ok": False, "error": "bad or expired link"})
        result = invoke_agent({"mode": "resume", "decision_id": decision_id, "choice": choice})
        status = "ok" if result.get("ok") else "error"
        return _redirect(f"{DASHBOARD_URL.rstrip('/')}/?decided={decision_id}&choice={choice}&status={status}")

    if API_KEY and headers.get("x-api-key") != API_KEY:
        return _response(401, {"ok": False, "error": "missing or invalid x-api-key"})

    if method == "GET" and path == "/state":
        return _response(200, build_state())
    if method == "POST" and path.startswith("/decisions/"):
        decision_id = path.split("/")[2]
        choice = str(body.get("choice", ""))
        if choice not in ("approve", "deny", "trust"):
            return _response(400, {"ok": False, "error": "choice must be approve|deny|trust"})
        return _response(200, invoke_agent({"mode": "resume", "decision_id": decision_id, "choice": choice}))
    if method == "POST" and path == "/sweep":
        return _response(200, invoke_agent({"mode": "sweep"}))
    if method == "POST" and path == "/simulate":
        action = str(body.get("action", "status"))
        if action not in ("advance", "reset", "status"):
            return _response(400, {"ok": False, "error": "action must be advance|reset|status"})
        return _response(200, invoke_agent({"mode": "simulate", "action": action}))
    if method == "POST" and path == "/chat":
        prompt = body.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            return _response(400, {"ok": False, "error": "prompt must be a non-empty string"})
        return _response(200, invoke_agent({"mode": "chat", "prompt": prompt[:2000]}))
    if method == "GET" and path == "/":
        return _response(200, {"ok": True, "service": "quiet-hours-api"})
    return _response(404, {"ok": False, "error": f"no route for {method} {path}"})
