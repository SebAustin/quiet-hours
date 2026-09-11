"""Drive Quiet Hours locally without HTTP: python scripts/local_run.py reset|advance|sweep|resume <id> <choice>|state|chat "<q>" """
import asyncio
import json
import sys
from pathlib import Path

APP = Path(__file__).resolve().parent.parent / "agent" / "app" / "QuietHours"
sys.path.insert(0, str(APP))

from main import invoke  # noqa: E402


async def call(payload):
    return await invoke(payload, None)


def main():
    cmd = sys.argv[1]
    if cmd == "state":
        from quiet.config import load_settings
        from quiet.store import build_store
        s = build_store(load_settings())
        print("day", s.get_clock())
        for i in s.list_items():
            print(f"  [{i.status.value:14}] {i.id:20} {i.category.value if i.category else '-':10} {i.outcome or ''}")
        print("actions:")
        for a in s.list_actions():
            print(f"  {a.mode.value:10} {a.tool:22} {a.policy_reason}")
        print("decisions:")
        for d in s.list_decisions():
            print(f"  {d.status.value:8} {d.id:16} {d.title}  // {d.policy_reason}")
        print("trust:", [f"{r.tool}:{r.vendor}:{r.max_amount}" for r in s.list_trust_rules()])
        return
    payload = {"mode": cmd}
    if cmd == "reset" or cmd == "advance":
        payload = {"mode": "simulate", "action": cmd}
    elif cmd == "resume":
        payload.update(decision_id=sys.argv[2], choice=sys.argv[3])
    elif cmd == "chat":
        payload["prompt"] = sys.argv[2]
    print(json.dumps(asyncio.run(call(payload)), indent=2, default=str))


if __name__ == "__main__":
    main()
