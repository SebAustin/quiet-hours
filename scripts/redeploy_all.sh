#!/usr/bin/env bash
# Bring the whole Quiet Hours stack back from nothing and re-wire the dashboard.
# Needs: AWS creds (us-east-1), agentcore CLI, sam, vercel (logged in), .env with QH_API_KEY / QH_DECISION_SECRET.
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; . ./.env; set +a
export AWS_REGION=us-east-1
DASH="${QH_DASHBOARD_URL:-https://quiet-hours-five.vercel.app}"

echo "== 1/6 SAM stack (table, bucket, API, scheduler)"
QH_AGENT_RUNTIME_ARN="" ./scripts/deploy_infra.sh >/dev/null
OUT=$(aws cloudformation describe-stacks --stack-name quiet-hours --query "Stacks[0].Outputs" --output json)
TABLE=$(echo "$OUT" | python3 -c "import json,sys; print(next(o['OutputValue'] for o in json.load(sys.stdin) if o['OutputKey']=='TableName'))")
BUCKET=$(echo "$OUT" | python3 -c "import json,sys; print(next(o['OutputValue'] for o in json.load(sys.stdin) if o['OutputKey']=='SessionsBucketName'))")
API=$(echo "$OUT" | python3 -c "import json,sys; print(next(o['OutputValue'] for o in json.load(sys.stdin) if o['OutputKey']=='ApiUrl').rstrip('/'))")
FN=$(echo "$OUT" | python3 -c "import json,sys; print(next(o['OutputValue'] for o in json.load(sys.stdin) if o['OutputKey']=='ApiFunctionName'))")
echo "   table=$TABLE bucket=$BUCKET api=$API"

echo "== 2/6 agentcore.json env vars"
python3 - "$TABLE" "$BUCKET" "$API" "$DASH" <<'PY'
import json, sys
table, bucket, api, dash = sys.argv[1:]
p = "agent/agentcore/agentcore.json"; d = json.load(open(p))
vals = {"QH_TABLE_NAME": table, "QH_SESSIONS_BUCKET": bucket, "QH_API_BASE_URL": api, "QH_DASHBOARD_URL": dash}
for e in d["runtimes"][0]["envVars"]:
    if e["name"] in vals: e["value"] = vals[e["name"]]
json.dump(d, open(p, "w"), indent=2)
PY

echo "== 3/6 AgentCore Runtime + Memory (several minutes)"
./scripts/deploy_agent.sh >/dev/null
ARN=$(cd agent && agentcore status --json | python3 -c "import json,sys; print(next(r['identifier'] for r in json.load(sys.stdin)['resources'] if r['resourceType']=='agent'))")
echo "   runtime=$ARN"

echo "== 4/6 SAM stack again with the runtime ARN"
python3 - "$TABLE" "$BUCKET" "$API" "$FN" "$ARN" <<'PY'
import re, sys
table, bucket, api, fn, arn = sys.argv[1:]
s = open(".env").read()
def put(k, v):
    global s
    s = re.sub(rf"^{k}=.*$", f"{k}={v}", s, flags=re.M) if re.search(rf"^{k}=", s, re.M) else s + f"\n{k}={v}"
put("QH_TABLE_NAME", table); put("QH_SESSIONS_BUCKET", bucket); put("QH_API_BASE_URL", api); put("QH_API_FUNCTION", fn); put("QH_AGENT_RUNTIME_ARN", arn)
open(".env", "w").write(s.strip() + "\n")
PY
set -a; . ./.env; set +a
./scripts/deploy_infra.sh >/dev/null

echo "== 5/6 Vercel env + dashboard"
( cd dashboard
  vercel env rm QH_API_BASE_URL production --yes >/dev/null 2>&1 || true
  printf "%s" "$API" | vercel env add QH_API_BASE_URL production >/dev/null
  vercel env rm QH_API_KEY production --yes >/dev/null 2>&1 || true
  printf "%s" "$QH_API_KEY" | vercel env add QH_API_KEY production >/dev/null
  vercel --prod --yes 2>&1 | grep -E "Aliased|Production" | tail -1 )

echo "== 6/6 populate the demo (3 days) and smoke test"
.venv/bin/python scripts/cloud_e2e.py 3 | tail -4
echo "done: $DASH"
