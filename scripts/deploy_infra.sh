#!/usr/bin/env bash
# Deploy/update the SAM stack (DynamoDB, S3, Lambda API, Scheduler) with secrets from .env
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; . ./.env; set +a
cd infra && sam build -q && sam deploy --stack-name quiet-hours --resolve-s3 --capabilities CAPABILITY_IAM \
  --no-confirm-changeset --no-fail-on-empty-changeset --region "${AWS_REGION:-us-east-1}" \
  --parameter-overrides "ApiKey=$QH_API_KEY DecisionSecret=$QH_DECISION_SECRET DashboardUrl=${QH_DASHBOARD_URL:-http://localhost:3000} AgentRuntimeArn=${QH_AGENT_RUNTIME_ARN:-} SlackWebhookUrl=${QH_SLACK_WEBHOOK_URL:-}"
