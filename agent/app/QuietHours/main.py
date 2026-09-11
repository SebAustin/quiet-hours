"""Quiet Hours — AgentCore Runtime entrypoint.

Payload modes (all JSON objects):
  {"mode": "sweep"}                                   background run: triage + specialists + decision cards
  {"mode": "resume", "decision_id": "...", "choice": "approve|deny|trust"}
  {"mode": "chat", "prompt": "..."}                   ask the household agent about its work
  {"mode": "simulate", "action": "advance|reset|status"}   demo clock for the simulated household feed
"""
from __future__ import annotations

import logging
from typing import Any

from bedrock_agentcore.runtime import BedrockAgentCoreApp

from model.load import load_model
from quiet.agents import build_chat_agent
from quiet.config import load_settings
from quiet.memory import HouseholdMemory
from quiet.resume import resume_decision_async
from quiet.simulate import advance_day, reset, seed_profile
from quiet.store import build_store
from quiet.sweep import run_sweep_async
from quiet.tools import HouseholdTools

app = BedrockAgentCoreApp()
log = app.logger
logging.getLogger("quiet").setLevel(logging.INFO)

MODES = {"sweep", "resume", "chat", "simulate"}


def _validate(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("payload must be a JSON object")
    mode = payload.get("mode", "chat" if isinstance(payload.get("prompt"), str) else None)
    if mode not in MODES:
        raise ValueError(f"mode must be one of {sorted(MODES)}")
    if mode == "chat" and not isinstance(payload.get("prompt"), str):
        raise ValueError("prompt must be a string")
    if mode == "resume" and not (isinstance(payload.get("decision_id"), str) and isinstance(payload.get("choice"), str)):
        raise ValueError("resume needs decision_id and choice strings")
    return {**payload, "mode": mode}


@app.entrypoint
async def invoke(payload, context):
    try:
        payload = _validate(payload)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}

    settings = load_settings()
    store = build_store(settings)
    memory = HouseholdMemory(settings)
    mode = payload["mode"]
    log.info("Quiet Hours invoke mode=%s cloud=%s", mode, settings.is_cloud)

    if mode == "sweep":
        digest = await run_sweep_async(settings, store, memory, load_model("fast"), load_model("smart"))
        return {"ok": True, "digest": digest.model_dump(mode="json")}

    if mode == "resume":
        return await resume_decision_async(settings, store, memory, payload["decision_id"], payload["choice"], load_model("smart"))

    if mode == "simulate":
        action = payload.get("action", "status")
        if action == "reset":
            reset(store)
            return {"ok": True, "day": store.get_clock()}
        if action == "advance":
            day, added = advance_day(store)
            return {"ok": True, "day": day, "arrived": [i.subject for i in added]}
        if not store.get_profile():
            seed_profile(store)
        return {"ok": True, "day": store.get_clock(), "new_items": len(store.list_items())}

    tools = HouseholdTools(store, memory, store.get_clock())
    agent = build_chat_agent(load_model("fast"), store, tools)
    result = await agent.invoke_async(payload["prompt"])
    return {"ok": True, "response": str(result).strip()}


if __name__ == "__main__":
    app.run()
