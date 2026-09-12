"""Invoke the deployed Quiet Hours agent on AgentCore Runtime. Usage: cloud_invoke.py '{"mode":"sweep"}'"""
import json
import os
import sys
import time
import uuid

import boto3

ARN = os.environ["QH_AGENT_RUNTIME_ARN"]
client = boto3.client("bedrock-agentcore", region_name=os.environ.get("AWS_REGION", "us-east-1"))


def invoke(payload: dict) -> dict:
    t0 = time.time()
    resp = client.invoke_agent_runtime(
        agentRuntimeArn=ARN, qualifier="DEFAULT", runtimeSessionId=f"qh-{uuid.uuid4()}-{uuid.uuid4().hex[:8]}",
        payload=json.dumps(payload).encode(), contentType="application/json", accept="application/json",
    )
    body = resp["response"].read()
    text = body.decode() if isinstance(body, bytes) else str(body)
    try:
        out = json.loads(text)
    except json.JSONDecodeError:
        out = {"raw": text[:3000]}
    out["_elapsed_s"] = round(time.time() - t0, 1)
    return out


if __name__ == "__main__":
    print(json.dumps(invoke(json.loads(sys.argv[1])), indent=2)[:6000])
