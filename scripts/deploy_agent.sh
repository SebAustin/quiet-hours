#!/usr/bin/env bash
# Deploy the Strands agent to AgentCore, filling secret placeholders in agentcore.json from .env
# (QH_DECISION_SECRET, QH_SLACK_WEBHOOK_URL). The committed file keeps the placeholders.
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; . ./.env; set +a
CFG=agent/agentcore/agentcore.json
cp "$CFG" "$CFG.bak"
trap 'mv "$CFG.bak" "$CFG"' EXIT
python3 - <<PY
import json, os
p = "$CFG"; d = json.load(open(p))
for e in d["runtimes"][0]["envVars"]:
    if e["value"].startswith("\${"):
        e["value"] = os.environ.get(e["value"][2:-1], "")
json.dump(d, open(p, "w"), indent=2)
PY
(cd agent && agentcore deploy -y "$@")
