"""End-to-end check against the deployed stack via the Lambda API.
Usage: cloud_e2e.py [days]   (reads QH_API_BASE_URL / QH_API_KEY from the environment)
Resets the demo, then for each day: advance, sweep, and answer decisions with a scripted choice.
"""
import json
import os
import sys
import time
import urllib.request

BASE = os.environ["QH_API_BASE_URL"].rstrip("/")
KEY = os.environ["QH_API_KEY"]
CHOICES = {"Energy": "trust", "Lonestar": "deny", "permission": "approve", "Keys": "trust", "Netflix": "deny", "Bright": "approve", "Hill": "approve"}


def call(method: str, path: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(f"{BASE}{path}", method=method, headers={"x-api-key": KEY, "content-type": "application/json"},
                                 data=json.dumps(body).encode() if body is not None else None)
    with urllib.request.urlopen(req, timeout=300) as resp:
        return json.loads(resp.read().decode())


def main() -> None:
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    call("POST", "/simulate", {"action": "reset"})
    s = call("GET", "/state")
    assert not s["items"] and not s["actions"] and not s["decisions"], "reset left data behind"
    for day in range(1, days + 1):
        call("POST", "/simulate", {"action": "advance"})
        t0 = time.time()
        d = call("POST", "/sweep")["digest"]
        print(f"\n{d['narrative']}  ({time.time() - t0:.0f}s)")
        for h in d["handled"]:
            print("  ok  ", h[:110])
        for f in d["flagged"]:
            print("  FLAG", f[:110])
        for e in d["escalated"]:
            print("  ASK ", e[:110])
        for card in [c for c in call("GET", "/state")["decisions"] if c["status"] == "pending"]:
            choice = next((v for k, v in CHOICES.items() if k in card["title"]), None)
            if not choice:
                continue
            r = call("POST", f"/decisions/{card['id']}", {"choice": choice})
            acts = [(a["tool"], a["mode"]) for a in r.get("actions", [])]
            print(f"  -> {choice:7} {card['title'][:60]:60} ok={r.get('ok')} {acts} follow-ups={r.get('follow_up_decisions')}")
    s = call("GET", "/state")
    print("\nstats:", json.dumps(s["stats"]))
    print("trust rules:", [(r["tool"], r["vendor"], r.get("max_amount")) for r in s["trust_rules"]])
    print("pending:", [c["title"] for c in s["decisions"] if c["status"] == "pending"])


if __name__ == "__main__":
    main()
